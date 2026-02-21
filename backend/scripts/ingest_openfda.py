"""
ingest_openfda.py
=================
Pull HUMAN PRESCRIPTION DRUG and HUMAN OTC DRUG products from the openFDA NDC
API and upsert them into the local SQLite database (`medicine_records` table).

After this script finishes, run `sync_to_pinecone.py` to push the new rows
into the Pinecone vector index.

Usage
-----
    cd backend
    python scripts/ingest_openfda.py [--limit N] [--skip-existing] [--product-types HUMAN PRESCRIPTION DRUG]

Defaults: pulls ALL human drug products (~120K+).  Use --limit for testing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv
from sqlalchemy import func, select

from app.core.config import settings
from app.core.db_setup import AsyncSessionLocal, init_db
from app.models.sql_models import MedicineRecord

load_dotenv(settings.project_root / ".env")
load_dotenv(settings.project_root / "backend" / ".env")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPENFDA_NDC_URL = "https://api.fda.gov/drug/ndc.json"
PAGE_SIZE = 100  # openFDA max per request
MAX_RETRIES = 5
RETRY_DELAY_SECS = 2.0
# Rate-limit: <=240 requests/min without key.  We stay well under.
REQUEST_PAUSE_SECS = 0.35

# Dosage form normalisation map (openFDA UPPERCASE -> our lowercase canonical)
FORM_MAP: Dict[str, str] = {
    "TABLET": "tablet",
    "TABLET, COATED": "tablet",
    "TABLET, FILM COATED": "tablet",
    "TABLET, FILM COATED, EXTENDED RELEASE": "tablet",
    "TABLET, EXTENDED RELEASE": "tablet",
    "TABLET, DELAYED RELEASE": "tablet",
    "TABLET, CHEWABLE": "tablet",
    "TABLET, EFFERVESCENT": "tablet",
    "TABLET, ORALLY DISINTEGRATING": "tablet",
    "CAPSULE": "capsule",
    "CAPSULE, LIQUID FILLED": "capsule",
    "CAPSULE, GELATIN COATED": "capsule",
    "CAPSULE, DELAYED RELEASE": "capsule",
    "CAPSULE, EXTENDED RELEASE": "capsule",
    "CAPSULE, COATED, EXTENDED RELEASE": "capsule",
    "SOLUTION": "solution",
    "SOLUTION, CONCENTRATE": "solution",
    "SUSPENSION": "suspension",
    "FOR SUSPENSION": "suspension",
    "SUSPENSION, EXTENDED RELEASE": "suspension",
    "SYRUP": "syrup",
    "INJECTION": "injection",
    "INJECTION, SOLUTION": "injection",
    "INJECTION, SUSPENSION": "injection",
    "INJECTION, POWDER, FOR SOLUTION": "injection",
    "INJECTION, POWDER, LYOPHILIZED, FOR SOLUTION": "injection",
    "CREAM": "cream",
    "OINTMENT": "ointment",
    "GEL": "gel",
    "LOTION": "lotion",
    "POWDER": "powder",
    "SPRAY": "spray",
    "SPRAY, METERED": "inhaler",
    "AEROSOL, METERED": "inhaler",
    "AEROSOL": "inhaler",
    "INHALER": "inhaler",
    "INHALANT": "inhaler",
    "PATCH": "patch",
    "PATCH, EXTENDED RELEASE": "patch",
    "SUPPOSITORY": "suppository",
    "SHAMPOO": "shampoo",
    "DROPS": "drops",
    "LIQUID": "liquid",
    "EMULSION": "emulsion",
    "GRANULE": "granule",
    "PELLET": "pellet",
    "PASTE": "paste",
    "FOAM": "foam",
    "KIT": "kit",
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _fetch_page(skip: int, limit: int, product_type_filter: str) -> Optional[Dict[str, Any]]:
    """Fetch one page from the openFDA NDC endpoint with retry."""
    search = f'product_type:"{product_type_filter}"'
    params = urllib.parse.urlencode({"search": search, "limit": limit, "skip": skip})
    url = f"{OPENFDA_NDC_URL}?{params}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = RETRY_DELAY_SECS * attempt
                print(f"  [rate-limit] 429 received, waiting {wait:.1f}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            elif exc.code == 404:
                return None  # no more results
            else:
                print(f"  [http-error] {exc.code} on attempt {attempt}: {exc.reason}")
                time.sleep(RETRY_DELAY_SECS)
        except Exception as exc:
            print(f"  [error] attempt {attempt}: {exc}")
            time.sleep(RETRY_DELAY_SECS)
    return None


def _normalise_form(raw_form: str) -> str:
    """Convert openFDA dosage_form to our canonical lowercase form."""
    upper = raw_form.strip().upper()
    if upper in FORM_MAP:
        return FORM_MAP[upper]
    # Fallback: lowercase the first word
    return raw_form.strip().lower().split(",")[0].split()[0] if raw_form else "other"


def _build_strength(ingredients: List[Dict[str, str]]) -> str:
    """Combine active_ingredients[].strength into a single string.

    Single ingredient:  '500 mg/1'  ->  '500 mg'
    Combination:        [{strength:'500 mg/1'}, {strength:'125 mg/1'}]  ->  '500/125 mg'
    """
    if not ingredients:
        return "unknown"

    parts: List[Tuple[str, str]] = []
    for ing in ingredients:
        raw = ing.get("strength", "").strip()
        if not raw:
            parts.append(("", ""))
            continue
        # openFDA often uses "500 mg/1" meaning 500 mg per 1 unit.
        # Also seen: "600 mg/5mL", "42.9 mg/5mL"
        # Keep the full string if it has a meaningful denominator.
        if "/" in raw:
            num_part, denom_part = raw.split("/", 1)
            num_part = num_part.strip()
            denom_part = denom_part.strip()
            # "500 mg/1" -> just "500 mg"
            if denom_part in ("1", "1 ", "1.0"):
                parts.append((num_part, ""))
            else:
                # "600 mg/5mL" -> keep as-is
                parts.append((raw, ""))
        else:
            parts.append((raw, ""))

    if len(parts) == 1:
        return parts[0][0] or "unknown"

    # For combinations: try to merge numeric values if units match.
    # e.g. "500 mg" + "125 mg" -> "500/125 mg"
    values: List[str] = []
    units: List[str] = []
    for val_str, _ in parts:
        # Split "500 mg" -> ("500", "mg")
        tokens = val_str.split(None, 1)
        if len(tokens) == 2:
            values.append(tokens[0])
            units.append(tokens[1].strip().lower())
        else:
            # Can't parse cleanly — fall back to joining with " + "
            return " + ".join(p[0] for p in parts if p[0])

    # If all units are the same, merge: "500/125 mg"
    unique_units = set(units)
    if len(unique_units) == 1:
        return "/".join(values) + " " + units[0]
    else:
        return " + ".join(f"{v} {u}" for v, u in zip(values, units))


def _build_brand_name(record: Dict[str, Any]) -> str:
    """Build the brand_name from openFDA fields.

    Uses brand_name + first active_ingredients[].strength for uniqueness.
    """
    brand = (record.get("brand_name") or "").strip()
    if not brand:
        brand = (record.get("brand_name_base") or "").strip() or (record.get("generic_name") or "").strip()

    # Title-case it (openFDA is often ALL-CAPS)
    brand = brand.title()

    # Append strength to make brand_name unique (as required by the schema)
    strength = _build_strength(record.get("active_ingredients", []))
    form = _normalise_form(record.get("dosage_form", ""))

    # Compose: "Augmentin 500/125 mg Tablet"
    return f"{brand} {strength} {form}".strip()


def _parse_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert one openFDA NDC result into a MedicineRecord-compatible dict.

    Returns None if the record is incomplete or should be skipped.
    """
    brand_name_raw = (record.get("brand_name") or "").strip()
    generic_name_raw = (record.get("generic_name") or "").strip()
    dosage_form_raw = (record.get("dosage_form") or "").strip()
    ingredients = record.get("active_ingredients") or []

    # Skip records with missing critical fields
    if not generic_name_raw or not dosage_form_raw or not ingredients:
        return None

    brand_name = _build_brand_name(record)
    generic_name = generic_name_raw.lower()
    strength = _build_strength(ingredients)
    form = _normalise_form(dosage_form_raw)
    combination_flag = len(ingredients) > 1

    if not brand_name or not strength or strength == "unknown":
        return None

    return {
        "brand_name": brand_name,
        "generic_name": generic_name,
        "official_strength": strength,
        "form": form,
        "combination_flag": combination_flag,
    }


# ---------------------------------------------------------------------------
# Database insertion
# ---------------------------------------------------------------------------

async def upsert_medicines(records: List[Dict[str, Any]], skip_existing: bool) -> Tuple[int, int, int]:
    """Insert parsed medicine dicts into SQLite.

    Returns (inserted, skipped_duplicate, skipped_error).
    """
    inserted = 0
    skipped_dup = 0
    skipped_err = 0

    async with AsyncSessionLocal() as session:
        for rec in records:
            try:
                if skip_existing:
                    existing = await session.execute(
                        select(MedicineRecord.id)
                        .where(MedicineRecord.brand_name == rec["brand_name"])
                        .limit(1)
                    )
                    if existing.scalars().first() is not None:
                        skipped_dup += 1
                        continue

                session.add(MedicineRecord(**rec))
                await session.flush()
                inserted += 1
            except Exception:
                await session.rollback()
                skipped_err += 1
                # Re-open a fresh transaction after rollback
                continue

        await session.commit()

    return inserted, skipped_dup, skipped_err


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def ingest(
    max_records: Optional[int] = None,
    skip_existing: bool = True,
    product_types: Optional[List[str]] = None,
) -> None:
    """Pull from openFDA and insert into SQLite."""
    if product_types is None:
        product_types = ["HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"]

    # Ensure DB tables exist
    await init_db()

    # Check current count
    async with AsyncSessionLocal() as session:
        count_result = await session.execute(select(func.count(MedicineRecord.id)))
        existing_count = count_result.scalar() or 0
    print(f"[ingest] SQLite currently has {existing_count} medicine records")

    total_inserted = 0
    total_skipped_dup = 0
    total_skipped_err = 0
    total_fetched = 0

    for product_type in product_types:
        print(f"\n[ingest] === Fetching product_type: {product_type} ===")
        skip = 0
        page_num = 0

        while True:
            if max_records and total_fetched >= max_records:
                print(f"[ingest] Reached --limit {max_records}, stopping.")
                break

            page_limit = min(PAGE_SIZE, (max_records - total_fetched) if max_records else PAGE_SIZE)
            page_num += 1

            print(f"[ingest] Page {page_num}: skip={skip}, limit={page_limit} ...", end=" ", flush=True)
            data = _fetch_page(skip, page_limit, product_type)

            if data is None or "results" not in data:
                print("no more results.")
                break

            results = data["results"]
            if not results:
                print("empty page.")
                break

            # Parse records
            parsed: List[Dict[str, Any]] = []
            for raw in results:
                rec = _parse_record(raw)
                if rec is not None:
                    parsed.append(rec)

            # Deduplicate within the batch by brand_name
            seen: set = set()
            unique_parsed: List[Dict[str, Any]] = []
            for rec in parsed:
                if rec["brand_name"] not in seen:
                    seen.add(rec["brand_name"])
                    unique_parsed.append(rec)

            ins, dup, err = await upsert_medicines(unique_parsed, skip_existing)
            total_inserted += ins
            total_skipped_dup += dup
            total_skipped_err += err
            total_fetched += len(results)

            print(f"fetched={len(results)}, parsed={len(unique_parsed)}, inserted={ins}, dup={dup}, err={err}")

            # openFDA caps skip+limit at 26,000 for deep pagination.
            # Beyond that, we need to use search_after or different filters.
            skip += len(results)
            if skip >= 26000:
                print(f"[ingest] Reached openFDA pagination limit (26K) for '{product_type}'.")
                break

            meta_total = data.get("meta", {}).get("results", {}).get("total", 0)
            if skip >= meta_total:
                print(f"[ingest] All {meta_total} records fetched for '{product_type}'.")
                break

            time.sleep(REQUEST_PAUSE_SECS)

    # Final stats
    async with AsyncSessionLocal() as session:
        count_result = await session.execute(select(func.count(MedicineRecord.id)))
        final_count = count_result.scalar() or 0

    print(f"\n{'='*60}")
    print(f"[ingest] DONE")
    print(f"  API records fetched : {total_fetched}")
    print(f"  Inserted into SQLite: {total_inserted}")
    print(f"  Skipped (duplicate) : {total_skipped_dup}")
    print(f"  Skipped (error)     : {total_skipped_err}")
    print(f"  Total in SQLite now : {final_count}")
    print(f"{'='*60}")
    print(f"\nNext step: run  python scripts/sync_to_pinecone.py  to push to Pinecone.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest openFDA NDC data into MedMap SQLite")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of API records to fetch (default: all available, up to 26K per product type)",
    )
    parser.add_argument(
        "--skip-existing", action="store_true", default=True,
        help="Skip records whose brand_name already exists in SQLite (default: True)",
    )
    parser.add_argument(
        "--no-skip-existing", action="store_false", dest="skip_existing",
        help="Do NOT skip existing records (may cause unique constraint errors)",
    )
    parser.add_argument(
        "--product-types", nargs="+",
        default=["HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"],
        help="Product types to fetch (default: HUMAN PRESCRIPTION DRUG, HUMAN OTC DRUG)",
    )
    args = parser.parse_args()

    asyncio.run(ingest(
        max_records=args.limit,
        skip_existing=args.skip_existing,
        product_types=args.product_types,
    ))


if __name__ == "__main__":
    main()

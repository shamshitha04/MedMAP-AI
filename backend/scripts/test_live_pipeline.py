from __future__ import annotations

import asyncio
import json

import httpx

API_URL = "http://127.0.0.1:8000/extract"


async def main() -> None:
    payload = {
        "raw_text": "Patient prescribed Augmentin 625 Tab bid",
    }

    timeout = httpx.Timeout(90.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(API_URL, json=payload)
        response.raise_for_status()
        data = response.json()

    print("\n=== Live Pipeline Response ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    medicines = data.get("medicines", [])
    if not medicines:
        print("\nNo medicines returned in response.")
        return

    first = medicines[0]
    extracted = first.get("extracted", {})
    matched = first.get("matched_medicine", {})

    variant_value = extracted.get("variant") or extracted.get("brand_variant")
    injected_strength = matched.get("official_strength")
    logs = first.get("guardrail_logs") or data.get("guardrail_logs") or []

    print("\n=== Quick Validation Checks ===")
    print(f"Phase 1 variant field value: {variant_value}")
    print(f"Phase 2 injected official strength: {injected_strength}")
    print(f"Guardrail logs captured: {len(logs)}")

    if logs:
        print("\n=== Guardrail Logs ===")
        for index, log in enumerate(logs, start=1):
            print(f"{index}. {log}")


if __name__ == "__main__":
    asyncio.run(main())

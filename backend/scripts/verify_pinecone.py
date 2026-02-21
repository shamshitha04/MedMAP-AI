from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

from dotenv import load_dotenv
from sqlalchemy import func, select

CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
	sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.db_setup import AsyncSessionLocal
from app.models.sql_models import MedicineRecord

load_dotenv(settings.project_root / ".env")

try:
	from pinecone import PineconeAsyncio
except Exception as exc:  # pragma: no cover
	raise RuntimeError("pinecone[asyncio] is required for this script") from exc

try:
	from pinecone_text.sparse import BM25Encoder
except Exception as exc:  # pragma: no cover
	raise RuntimeError("pinecone-text is required for this script") from exc

try:
	from sentence_transformers import SentenceTransformer
except Exception as exc:  # pragma: no cover
	raise RuntimeError("sentence-transformers is required for this script") from exc


def build_record_text(record: MedicineRecord) -> str:
	return " ".join([record.brand_name.strip(), record.generic_name.strip(), record.form.strip()])


async def get_sqlite_count() -> int:
	async with AsyncSessionLocal() as session:
		result = await session.execute(select(func.count(MedicineRecord.id)))
		count_value = result.scalar_one()
		return int(count_value)


async def fetch_records() -> List[MedicineRecord]:
	async with AsyncSessionLocal() as session:
		result = await session.execute(select(MedicineRecord).order_by(MedicineRecord.id.asc()))
		return list(result.scalars().all())


async def resolve_index(pc: PineconeAsyncio, index_name: str) -> Any:
	description = await pc.describe_index(index_name)
	if asyncio.iscoroutine(description):
		description = await description
	host = description.host if hasattr(description, "host") else description["host"]
	index_factory = pc.IndexAsyncio(host=host)
	if asyncio.iscoroutine(index_factory):
		return await index_factory
	return index_factory


def _extract_namespace_count(stats: Any, namespace: str) -> int:
	if isinstance(stats, dict):
		namespaces = stats.get("namespaces", {})
		ns_info = namespaces.get(namespace, {})
		return int(ns_info.get("vector_count", 0))

	namespaces = getattr(stats, "namespaces", {})
	if isinstance(namespaces, dict):
		ns_info = namespaces.get(namespace)
		if ns_info is None:
			return 0
		if isinstance(ns_info, dict):
			return int(ns_info.get("vector_count", 0))
		return int(getattr(ns_info, "vector_count", 0))

	return 0


def _normalize_sparse_query(sparse_encoded: Any) -> Dict[str, List[float]]:
	if isinstance(sparse_encoded, list):
		sparse_dict = sparse_encoded[0] if sparse_encoded else {"indices": [], "values": []}
	else:
		sparse_dict = sparse_encoded if isinstance(sparse_encoded, dict) else {"indices": [], "values": []}

	indices = [int(index) for index in sparse_dict.get("indices", [])]
	values = [float(value) for value in sparse_dict.get("values", [])]
	return {"indices": indices, "values": values}


async def verify_pinecone() -> None:
	if not settings.pinecone_api_key:
		raise RuntimeError("Missing PINECONE_API_KEY in environment")
	if not settings.pinecone_index_name:
		raise RuntimeError("Missing PINECONE_INDEX_NAME in environment")

	namespace = settings.pinecone_namespace

	print(f"[verify] SQLite database URL: {settings.database_url}")
	sqlite_count = await get_sqlite_count()
	print(f"[verify] SQLite medicine_records count = {sqlite_count}")

	print(f"[verify] Connecting to Pinecone index: {settings.pinecone_index_name}")
	async with PineconeAsyncio(api_key=settings.pinecone_api_key) as pc:
		index = await resolve_index(pc, settings.pinecone_index_name)

		stats = await index.describe_index_stats()
		namespace_count = _extract_namespace_count(stats, namespace)
		print(f"[verify] Pinecone namespace '{namespace}' vector count = {namespace_count}")

		if namespace_count == sqlite_count:
			print("[verify] PASS Row count check PASSED (SQLite count matches Pinecone namespace count)")
		elif namespace_count >= sqlite_count:
			print(f"[verify] WARN Pinecone has {namespace_count} vectors vs {sqlite_count} SQLite rows (stale vectors may exist)")
		else:
			print(f"[verify] FAIL Row count check FAILED ({namespace_count} in Pinecone < {sqlite_count} in SQLite)")

		records = await fetch_records()
		corpus = [build_record_text(record) for record in records]
		if not corpus:
			print("[verify] No records available for query encoder setup; skipping hybrid query")
			return

		print("[verify] Loading dense model: all-MiniLM-L6-v2")
		dense_model = SentenceTransformer("all-MiniLM-L6-v2")
		print("[verify] Fitting BM25 sparse encoder on SQLite corpus")
		sparse_encoder = BM25Encoder()
		sparse_encoder.fit(corpus)

		dummy_query = "Amox"
		dense_vector = dense_model.encode(dummy_query).tolist()
		sparse_values = _normalize_sparse_query(sparse_encoder.encode_queries(dummy_query))

		print(f"[verify] Running dummy hybrid search for query: '{dummy_query}'")
		query_response = await index.query(
			vector=dense_vector,
			sparse_vector=sparse_values,
			top_k=5,
			namespace=namespace,
			include_metadata=True,
		)

		if isinstance(query_response, dict):
			matches = query_response.get("matches", [])
		else:
			matches = getattr(query_response, "matches", [])

		if not matches:
			print("[verify] No matches returned from dummy hybrid query")
		else:
			print("[verify] Dummy hybrid query results (id -> score):")
			for match in matches:
				if isinstance(match, dict):
					match_id = match.get("id")
					score = match.get("score")
				else:
					match_id = getattr(match, "id", None)
					score = getattr(match, "score", None)
				print(f"  - id={match_id}, score={score}")

	print("[verify] Pinecone verification complete (OK)")


if __name__ == "__main__":
	try:
		asyncio.run(verify_pinecone())
	except Exception as exc:  # pragma: no cover
		print(f"[verify] Verification failed: {exc}")
		raise

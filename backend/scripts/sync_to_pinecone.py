from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

from dotenv import load_dotenv
from sqlalchemy import select

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
	return " ".join(
		[
			record.brand_name.strip(),
			record.generic_name.strip(),
			record.form.strip(),
		]
	)


async def fetch_medicine_records() -> List[MedicineRecord]:
	async with AsyncSessionLocal() as session:
		result = await session.execute(select(MedicineRecord).order_by(MedicineRecord.id.asc()))
		return list(result.scalars().all())


def build_sparse_encoder(corpus: List[str]) -> BM25Encoder:
	encoder = BM25Encoder()
	encoder.fit(corpus)
	return encoder


def chunked(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
	return [items[index : index + size] for index in range(0, len(items), size)]


async def resolve_index(pc: PineconeAsyncio, index_name: str) -> Any:
	# Newer Pinecone SDK requires the host URL — retrieve it via describe_index
	description = await pc.describe_index(index_name)
	if asyncio.iscoroutine(description):
		description = await description
	host = description.host if hasattr(description, "host") else description["host"]
	index_factory = pc.IndexAsyncio(host=host)
	if asyncio.iscoroutine(index_factory):
		return await index_factory
	return index_factory


async def upsert_hybrid_vectors() -> None:
	if not settings.pinecone_api_key:
		raise RuntimeError("Missing PINECONE_API_KEY in environment")
	if not settings.pinecone_index_name:
		raise RuntimeError("Missing PINECONE_INDEX_NAME in environment")

	pinecone_namespace = settings.pinecone_namespace
	print(f"[sync] Loading medicines from SQLite: {settings.database_url}")
	records = await fetch_medicine_records()
	if not records:
		print("[sync] No MedicineRecord rows found. Nothing to sync.")
		return

	print(f"[sync] Found {len(records)} records")	
	print("[sync] Loading dense model: all-MiniLM-L6-v2")
	dense_model = SentenceTransformer("all-MiniLM-L6-v2")

	corpus = [build_record_text(record) for record in records]
	print("[sync] Fitting BM25 sparse encoder on local corpus")
	sparse_encoder = build_sparse_encoder(corpus)

	vectors: List[Dict[str, Any]] = []
	for index, record in enumerate(records, start=1):
		combined_text = build_record_text(record)
		dense_vector = dense_model.encode(combined_text).tolist()
		sparse_encoded = sparse_encoder.encode_documents(combined_text)
		if isinstance(sparse_encoded, list):
			sparse_values = sparse_encoded[0] if sparse_encoded else {"indices": [], "values": []}
		else:
			sparse_values = sparse_encoded

		vector_payload = {
			"id": str(record.id),
			"values": dense_vector,
			"sparse_values": {
				"indices": list(sparse_values.get("indices", [])),
				"values": [float(value) for value in sparse_values.get("values", [])],
			},
			"metadata": {
				"sqlite_id": record.id,
				"brand_name": record.brand_name,
				"generic_name": record.generic_name,
				"form": record.form,
				"official_strength": record.official_strength,
				"combination_flag": record.combination_flag,
			},
		}
		vectors.append(vector_payload)
		print(f"[sync] Prepared vector {index}/{len(records)} -> id={record.id} | text='{combined_text}'")

	print(f"[sync] Connecting to Pinecone index: {settings.pinecone_index_name}")
	pc = PineconeAsyncio(api_key=settings.pinecone_api_key)
	try:
		index = await resolve_index(pc, settings.pinecone_index_name)

		batches = chunked(vectors, size=50)
		print(f"[sync] Uploading {len(vectors)} vectors in {len(batches)} batch(es)")
		for batch_index, batch in enumerate(batches, start=1):
			response = await index.upsert(vectors=batch, namespace=pinecone_namespace)
			print(f"[sync] Upserted batch {batch_index}/{len(batches)} (size={len(batch)}) -> {response}")

		print("[sync] Pinecone sync complete - SUCCESS")
	finally:
		await pc.close()


if __name__ == "__main__":
	try:
		asyncio.run(upsert_hybrid_vectors())
	except Exception as exc:  # pragma: no cover
		print(f"[sync] Sync failed: {exc}")
		raise

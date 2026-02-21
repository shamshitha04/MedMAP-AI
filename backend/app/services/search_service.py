from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import numpy as np

from app.core.config import settings
from app.models.schemas import CandidateMatch, ExtractedMedicine
from app.models.sql_models import MedicineRecord, PrescriberMedicineHistory

# Named sentinel for "no DB match" — avoids collision with SQLite autoincrement IDs
NO_MATCH_ID: int = -1

try:
	from pinecone import PineconeAsyncio
except Exception:  # pragma: no cover
	PineconeAsyncio = None

try:
	from pinecone_text.sparse import BM25Encoder
except Exception:  # pragma: no cover
	BM25Encoder = None

try:
	from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
	SentenceTransformer = None

_dense_model: Any = None
_sparse_encoder: Any = None
_DENSE_DIM = 384


def _hash_dense_embedding(text: str, dimension: int = _DENSE_DIM) -> List[float]:
	seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
	rng = np.random.default_rng(seed)
	vector = rng.random(dimension, dtype=np.float32)
	norm = np.linalg.norm(vector)
	if norm == 0:
		return vector.tolist()
	return (vector / norm).tolist()


def _get_dense_model() -> Optional[Any]:
	global _dense_model
	if _dense_model is None and SentenceTransformer is not None:
		try:
			_dense_model = SentenceTransformer("all-MiniLM-L6-v2")
		except Exception:
			_dense_model = None
	return _dense_model


def _build_bm25_corpus() -> List[str]:
	"""Build a representative BM25 corpus from all seeded medicine records.

	This runs synchronously during lazy init so we construct the corpus from
	the known seed data in db_setup.SAMPLE_MEDICINES.  When Pinecone sync
	runs, its own BM25 is fit on the live SQLite corpus separately.
	"""
	try:
		from app.core.db_setup import SAMPLE_MEDICINES
		corpus = [
			" ".join([
				rec["brand_name"].strip(),
				rec["generic_name"].strip(),
				(rec.get("form") or "").strip(),
			])
			for rec in SAMPLE_MEDICINES
		]
		if corpus:
			return corpus
	except Exception:
		pass
	# Fallback minimal corpus if import fails
	return ["augmentin 625 tablet", "amoxiclav 625 tablet", "paracetamol 500 tablet"]


def _get_sparse_encoder() -> Optional[Any]:
	global _sparse_encoder
	if _sparse_encoder is None and BM25Encoder is not None:
		try:
			_sparse_encoder = BM25Encoder()
			_sparse_encoder.fit(_build_bm25_corpus())
		except Exception:
			_sparse_encoder = None
	return _sparse_encoder


def _build_query_text(extracted: ExtractedMedicine) -> str:
	parts = [extracted.brand_name]
	if extracted.brand_variant:
		parts.append(extracted.brand_variant)
	if extracted.form:
		parts.append(extracted.form)
	return " ".join([part for part in parts if part]).strip()


async def _local_sqlite_fallback(extracted: ExtractedMedicine, session: AsyncSession) -> CandidateMatch:
	# Build a ranked list of search terms to try: brand, generic, and individual tokens
	search_terms: List[str] = []
	if extracted.brand_name and extracted.brand_name.lower() != "unknown":
		search_terms.append(extracted.brand_name.lower())
	if extracted.generic_name:
		search_terms.append(extracted.generic_name.lower())
	# Split brand into individual word tokens (e.g. "co amoxiclav" → ["co", "amoxiclav"])
	for token in (extracted.brand_name or "").lower().split():
		if len(token) > 3 and token not in search_terms:
			search_terms.append(token)

	for term in search_terms:
		if not term:
			continue
		result = await session.execute(
			select(MedicineRecord)
			.where(
				MedicineRecord.brand_name.ilike(f"%{term}%")
				| MedicineRecord.generic_name.ilike(f"%{term}%")
			)
			.order_by(MedicineRecord.id)
			.limit(1)
		)
		medicine = result.scalar_one_or_none()
		if medicine:
			return CandidateMatch(id=medicine.id, score=0.78, metadata={"source": "sqlite_fallback", "matched_term": term})

	# No match found — return sentinel id=-1 so routes can provide a VLM-grounded graceful response
	return CandidateMatch(id=NO_MATCH_ID, score=0.0, metadata={"source": "vlm_only"})


async def _apply_prescriber_prior(
	candidate: CandidateMatch,
	prescriber_id: Optional[str],
	session: AsyncSession,
	guardrail_logs: List[str],
) -> CandidateMatch:
	if not prescriber_id:
		return candidate

	result = await session.execute(
		select(PrescriberMedicineHistory.mapping_count)
		.where(PrescriberMedicineHistory.prescriber_id == prescriber_id)
		.where(PrescriberMedicineHistory.medicine_id == candidate.id)
		.limit(1)
	)
	mapping_count = result.scalar_one_or_none()
	if mapping_count is None:
		guardrail_logs.append("Bayesian prescriber prior: no historical mapping found")
		return candidate

	boost = min(0.15, 0.03 * int(mapping_count))
	boosted_score = min(1.0, candidate.score + boost)
	guardrail_logs.append(
		f"Bayesian prescriber prior applied: +{round(boost, 4)} score boost from history"
	)

	return CandidateMatch(id=candidate.id, score=boosted_score, metadata=candidate.metadata)


async def query_top_candidate(
	extracted: ExtractedMedicine,
	session: AsyncSession,
	guardrail_logs: List[str],
	prescriber_id: Optional[str] = None,
) -> CandidateMatch:
	query_text = _build_query_text(extracted)

	dense_vector: Optional[List[float]] = None
	sparse_vector: Optional[Dict[str, List[float]]] = None

	dense_model = _get_dense_model()
	if dense_model is not None:
		dense_vector = dense_model.encode(query_text).tolist()
		guardrail_logs.append("Dense vector generated using all-MiniLM-L6-v2")
	else:
		dense_vector = _hash_dense_embedding(query_text)
		guardrail_logs.append("Dense vector generated using deterministic fallback embedding")

	sparse_encoder = _get_sparse_encoder()
	if sparse_encoder is not None:
		sparse_encoded = sparse_encoder.encode_queries(query_text)
		if isinstance(sparse_encoded, dict) and "indices" in sparse_encoded and "values" in sparse_encoded:
			sparse_vector = {
				"indices": sparse_encoded["indices"],
				"values": sparse_encoded["values"],
			}
		else:
			sparse_vector = None
		guardrail_logs.append("Sparse vector generated using BM25 encoder")
	else:
		guardrail_logs.append("Sparse encoder unavailable: lexical sparse component skipped")

	if PineconeAsyncio is not None and settings.pinecone_api_key and settings.pinecone_index_name and dense_vector is not None:
		try:
			pc = PineconeAsyncio(api_key=settings.pinecone_api_key)
			# Resolve index host — always await to handle both sync/async SDK versions
			description = pc.describe_index(settings.pinecone_index_name)
			if asyncio.iscoroutine(description) or asyncio.isfuture(description):
				description = await description
			index_host = getattr(description, "host", None) or description.get("host", "") if isinstance(description, dict) else getattr(description, "host", "")
			if not index_host:
				raise RuntimeError("Could not resolve Pinecone index host")
			index = pc.IndexAsyncio(host=index_host)
			if asyncio.iscoroutine(index) or asyncio.isfuture(index):
				index = await index

			query_kwargs: Dict[str, Any] = {
				"vector": dense_vector,
				"top_k": 1,
				"include_metadata": True,
				"namespace": settings.pinecone_namespace,
			}
			if sparse_vector is not None:
				query_kwargs["sparse_vector"] = sparse_vector

			result = await index.query(**query_kwargs)
			matches = result.get("matches", []) if isinstance(result, dict) else getattr(result, "matches", [])
			if matches:
				top_match = matches[0]
				pinecone_id = int(top_match.get("id"))
				pinecone_score = float(top_match.get("score", 0.0))
				pinecone_meta = top_match.get("metadata", {}) or {}

				# Validate the Pinecone-returned ID exists in the local SQLite ground truth.
				# If the DB was re-seeded (IDs changed) but Pinecone wasn't re-synced,
				# the ID will be stale. Fall through to SQLite fallback in that case.
				verify = await session.execute(
					select(MedicineRecord.id).where(MedicineRecord.id == pinecone_id).limit(1)
				)
				if verify.scalar_one_or_none() is not None:
					candidate = CandidateMatch(
						id=pinecone_id,
						score=pinecone_score,
						metadata=pinecone_meta,
					)
					guardrail_logs.append("Pinecone async hybrid query executed")
					return await _apply_prescriber_prior(candidate, prescriber_id, session, guardrail_logs)
				else:
					guardrail_logs.append(
						f"Pinecone returned stale id={pinecone_id} not in SQLite — falling back to local search"
					)
		except Exception:
			guardrail_logs.append("Pinecone unavailable: deterministic SQLite fallback engaged")

	fallback_candidate = await _local_sqlite_fallback(extracted, session)
	guardrail_logs.append("Hybrid retrieval fallback: SQLite candidate selected")
	return await _apply_prescriber_prior(fallback_candidate, prescriber_id, session, guardrail_logs)


async def get_medicine_by_id(record_id: int, session: AsyncSession) -> Optional[MedicineRecord]:
	result = await session.execute(select(MedicineRecord).where(MedicineRecord.id == record_id))
	return result.scalar_one_or_none()


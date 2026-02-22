from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_setup import get_db_session
from app.models.schemas import ExtractionRequest, ExtractionResponse, MatchedMedicine, ProcessedMedicine
from app.services.extraction_service import extract_medicines, get_cached_extraction_response
from app.services.guardrail_service import apply_post_match_guardrails, apply_pre_match_guardrails
from app.services.search_service import NO_MATCH_ID, get_medicine_by_id, query_top_candidate

router = APIRouter()


@router.post("/extract", response_model=ExtractionResponse)
async def extract_route(
	payload: ExtractionRequest,
	session: AsyncSession = Depends(get_db_session),
) -> ExtractionResponse:
	guardrail_logs: list[str] = []

	try:
		guardrail_logs.append("Workflow started: Cache Check -> Extraction -> Phase 1 -> Hybrid Search -> Phase 2")

		# 1) "Illusion of Edge" Cache Check (PRD §3.1)
		# This is the SOLE cache intercept point — returns the full pre-computed
		# ExtractionResponse when a demo image hash matches, bypassing all
		# downstream extraction, guardrails, and search.
		if payload.image_base64:
			cached_response = get_cached_extraction_response(payload.image_base64)
			if cached_response is not None:
				guardrail_logs.append("Workflow short-circuited by cache hit")
				cached_response.guardrail_logs = [*cached_response.guardrail_logs, *guardrail_logs]
				for item in cached_response.medicines:
					item.guardrail_logs = [*item.guardrail_logs, *guardrail_logs]
				return cached_response

		# 2) Extraction (raw AI output)
		raw_ai_extracted_items = await extract_medicines(payload, guardrail_logs)
		total_items = len(raw_ai_extracted_items)
		guardrail_logs.append(f"Detected {total_items} medicine entr{'y' if total_items == 1 else 'ies'} for analysis")

		processed_medicines: list[ProcessedMedicine] = []
		for index, raw_ai_extracted in enumerate(raw_ai_extracted_items, start=1):
			item_guardrail_logs = list(guardrail_logs)
			item_guardrail_logs.append(f"Processing medicine {index}/{total_items}")

			# 3) Phase 1 Guardrails (pre-match)
			pre_guardrailed = apply_pre_match_guardrails(raw_ai_extracted, item_guardrail_logs)

			# 4) Pinecone Hybrid Search
			top_candidate = await query_top_candidate(
				extracted=pre_guardrailed,
				session=session,
				guardrail_logs=item_guardrail_logs,
				prescriber_id=payload.prescriber_id,
			)

			# 5a) VLM-only graceful fallback — no DB record found for this drug
			if top_candidate.id == NO_MATCH_ID:
				item_guardrail_logs.append(
					"GUARDRAIL: No DB record found — returning VLM-grounded extraction; manual review required"
				)
				vlm_matched = MatchedMedicine(
					id=0,
					brand_name=pre_guardrailed.brand_name or "unknown",
					generic_name=pre_guardrailed.generic_name or "unknown",
					official_strength=pre_guardrailed.strength or "unknown",
					form=pre_guardrailed.form or "unknown",
					combination_flag=False,
					final_similarity_score=0.0,
					risk_classification="High",
					clinical_risk_tier="High",
					manual_review_required=True,
				)
				item_guardrail_logs.append(
					"Workflow completed: VLM-only payload — not grounded against SQLite ground truth"
				)
				processed_medicines.append(
					ProcessedMedicine(
						original_raw_input=raw_ai_extracted.raw_input,
						extracted=pre_guardrailed,
						matched_medicine=vlm_matched,
						guardrail_logs=list(item_guardrail_logs),
					)
				)
				continue

			# 5b) Normal Phase 2 Guardrails (post-match deterministic locking)
			db_record = await get_medicine_by_id(top_candidate.id, session)
			if db_record is None:
				# Pinecone returned a stale/orphaned ID that no longer exists in SQLite.
				# Fall back to VLM-only path rather than crashing with 404.
				item_guardrail_logs.append(
					f"GUARDRAIL: Pinecone candidate id={top_candidate.id} not found in SQLite — falling back to VLM-only payload"
				)
				vlm_matched = MatchedMedicine(
					id=0,
					brand_name=pre_guardrailed.brand_name or "unknown",
					generic_name=pre_guardrailed.generic_name or "unknown",
					official_strength=pre_guardrailed.strength or "unknown",
					form=pre_guardrailed.form or "unknown",
					combination_flag=False,
					final_similarity_score=0.0,
					risk_classification="High",
					clinical_risk_tier="High",
					manual_review_required=True,
				)
				item_guardrail_logs.append("Workflow completed: VLM-only payload — Pinecone/SQLite ID mismatch")
				processed_medicines.append(
					ProcessedMedicine(
						original_raw_input=raw_ai_extracted.raw_input,
						extracted=pre_guardrailed,
						matched_medicine=vlm_matched,
						guardrail_logs=list(item_guardrail_logs),
					)
				)
				continue

			matched = apply_post_match_guardrails(pre_guardrailed, top_candidate, db_record, item_guardrail_logs)
			item_guardrail_logs.append("Workflow completed: final grounded payload generated")
			processed_medicines.append(
				ProcessedMedicine(
					original_raw_input=raw_ai_extracted.raw_input,
					extracted=pre_guardrailed,
					matched_medicine=matched,
					guardrail_logs=list(item_guardrail_logs),
				)
			)

		guardrail_logs.append(f"Workflow completed: analyzed {len(processed_medicines)} medicine entr{'y' if len(processed_medicines) == 1 else 'ies'}")
		return ExtractionResponse(medicines=processed_medicines, guardrail_logs=list(guardrail_logs))

	except HTTPException:
		raise
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


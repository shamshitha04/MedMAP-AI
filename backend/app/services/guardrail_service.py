from __future__ import annotations

import re
from typing import List, Optional

from app.models.schemas import CandidateMatch, ExtractedMedicine, MatchedMedicine
from app.models.sql_models import MedicineRecord

FORM_MAP = {
	"tab": "tablet",
	"tablet": "tablet",
	"cap": "capsule",
	"caps": "capsule",
	"capsule": "capsule",
	"syp": "syrup",
	"syr": "syrup",
	"syrup": "syrup",
}

FREQUENCY_MAP = {
	"bd": "2 times per day",
	"bid": "2 times per day",
	"tid": "3 times per day",
	"od": "1 time per day",
}


def _extract_numeric_tokens(value: str) -> List[str]:
	return re.findall(r"\d+", value or "")


def _normalize_spaces(value: str) -> str:
	return " ".join((value or "").split()).strip()


def apply_pre_match_guardrails(extracted: ExtractedMedicine, guardrail_logs: List[str]) -> ExtractedMedicine:
	raw_brand = _normalize_spaces(extracted.brand_name)
	brand_numeric_tokens = _extract_numeric_tokens(raw_brand)
	detected_variant: Optional[str] = extracted.brand_variant
	if detected_variant is None and brand_numeric_tokens:
		detected_variant = brand_numeric_tokens[0]
		guardrail_logs.append("Variant token stripped")

	brand_without_numeric = re.sub(r"\b\d+[a-zA-Z]*\b", " ", raw_brand)
	normalized_brand = _normalize_spaces(brand_without_numeric).lower() or raw_brand.lower()

	raw_form = _normalize_spaces(extracted.form or "")
	raw_frequency = _normalize_spaces(extracted.frequency or "")
	normalized_form = FORM_MAP.get(raw_form.lower(), raw_form.lower() if raw_form else None)
	normalized_frequency = FREQUENCY_MAP.get(raw_frequency.lower(), raw_frequency.lower() if raw_frequency else None)

	if extracted.form and normalized_form != extracted.form.lower():
		guardrail_logs.append("Normalization rule applied for dosage form")
	if extracted.frequency and normalized_frequency != extracted.frequency.lower():
		guardrail_logs.append("Normalization rule applied for frequency")

	normalized_generic = extracted.generic_name.lower() if extracted.generic_name else None
	if extracted.brand_name != normalized_brand or extracted.generic_name != normalized_generic:
		guardrail_logs.append("Normalization rule applied: lowercased extraction fields")

	if detected_variant and extracted.strength is not None:
		guardrail_logs.append("Variant separation enforced: extracted strength cleared to prevent hallucinated mapping")

	return ExtractedMedicine(
		raw_input=extracted.raw_input,
		brand=normalized_brand,
		variant=detected_variant,
		generic_name=normalized_generic,
		strength=None if detected_variant else extracted.strength,
		form=normalized_form,
		frequency=normalized_frequency,
	)


def _classify_risk(score: float) -> tuple[str, bool]:
	if score >= 0.85:
		return "High", False
	if score >= 0.65:
		return "Medium", False
	return "Low", True


def apply_post_match_guardrails(
	extracted: ExtractedMedicine,
	candidate: CandidateMatch,
	db_record: MedicineRecord,
	guardrail_logs: List[str],
) -> MatchedMedicine:
	score = float(candidate.score)
	guardrail_logs.append(
		f"Post-match comparison executed: Pinecone candidate {candidate.id} checked against SQLite record {db_record.id}"
	)

	extracted_variant = (extracted.brand_variant or "").strip()
	db_variant_tokens = _extract_numeric_tokens(db_record.brand_name)
	db_variant = db_variant_tokens[0] if db_variant_tokens else ""

	if extracted_variant and db_variant and extracted_variant != db_variant:
		score -= 0.35
		guardrail_logs.append("Variant mismatch penalty applied")
	elif extracted_variant and not db_variant:
		score -= 0.15
		guardrail_logs.append("Variant mismatch penalty applied")

	db_form = (db_record.form or "").lower()
	if extracted.form and db_form and extracted.form.lower() != db_form:
		score -= 0.30
		guardrail_logs.append("Form mismatch penalty applied")
	elif extracted.form and not db_form:
		guardrail_logs.append("Form comparison skipped: database record has no form value")

	if db_record.combination_flag:
		guardrail_logs.append("Combination lock enforced")
		guardrail_logs.append("Generic splitting blocked due to combination_flag=True")

	final_strength = db_record.official_strength
	guardrail_logs.append("Official strength injected")
	guardrail_logs.append("AI extracted strength overwritten with SQLite official_strength")

	score = max(0.0, min(1.0, score))
	risk, manual_review = _classify_risk(score)
	guardrail_logs.append(f"Confidence classification computed: {risk}")
	if manual_review:
		guardrail_logs.append("Risk-based routing: Manual Review Required")

	return MatchedMedicine(
		id=db_record.id,
		brand_name=db_record.brand_name,
		generic_name=db_record.generic_name,
		official_strength=final_strength,
		form=db_record.form or "unknown",
		combination_flag=db_record.combination_flag,
		final_similarity_score=round(score, 4),
		risk_classification=risk,
		clinical_risk_tier=risk,
		manual_review_required=manual_review,
	)


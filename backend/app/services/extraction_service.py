from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import ExtractedData, ExtractedMedicine, ExtractionRequest, ExtractionResponse


def _compute_image_hash(image_base64: str) -> str:
	return hashlib.sha256(image_base64.encode("utf-8")).hexdigest()


def compute_image_hash(image_base64: str) -> str:
	return _compute_image_hash(image_base64)


def _load_golden_cache() -> Dict[str, Any]:
	cache_path: Path = settings.golden_cache_path
	if not cache_path.exists():
		return {}
	try:
		with cache_path.open("r", encoding="utf-8") as file:
			payload = json.load(file)
	except json.JSONDecodeError:
		return {}

	if isinstance(payload, dict) and "hashes" in payload and isinstance(payload["hashes"], dict):
		return payload["hashes"]
	if isinstance(payload, dict):
		return payload
	return {}


def intercept_golden_cache(image_base64: str) -> Optional[Dict[str, Any]]:
	image_hash = _compute_image_hash(image_base64)
	golden_cache = _load_golden_cache()
	entry = golden_cache.get(image_hash)
	if isinstance(entry, dict):
		return entry
	return None


def get_cached_extraction_response(image_base64: str) -> Optional[ExtractionResponse]:
	entry = intercept_golden_cache(image_base64)
	if not isinstance(entry, dict):
		return None

	if "medicines" in entry:
		return ExtractionResponse.model_validate(entry)

	if "response" in entry and isinstance(entry["response"], dict):
		return ExtractionResponse.model_validate(entry["response"])

	return None


def _coerce_cached_extraction(cached_payload: Dict[str, Any], raw_input: str) -> ExtractedMedicine:
	extracted = cached_payload.get("extracted", cached_payload)
	return ExtractedMedicine(
		raw_input=raw_input,
		brand=extracted.get("brand", extracted.get("brand_name", "unknown")),
		variant=extracted.get("variant", extracted.get("brand_variant")),
		generic_name=extracted.get("generic_name"),
		strength=extracted.get("strength"),
		form=extracted.get("form"),
		frequency=extracted.get("frequency"),
	)


# Recognised dosage-form tokens (lowercased) for the local NER parser
_FORM_TOKENS: set[str] = {
	"tab", "tablet", "tablets",
	"cap", "capsule", "capsules",
	"syrup", "inhaler", "injection",
	"cream", "ointment", "drops",
	"solution", "suspension",
}


def _extract_from_local_ner(raw_text: str) -> ExtractedMedicine:
	"""Multi-word-aware local NER parser.

	Tokenises the input and classifies each token as:
	  - **form** — known dosage-form keyword
	  - **strength** — ends with 'mg', 'ml', 'mcg', or contains 'mg/'
	  - **variant** — pure digit string or digit/digit fraction (e.g. '500/125')
	  - **brand word** — everything else

	This allows multi-word brand names like "Augmentin 625 Duo" to parse as
	brand="Augmentin Duo", variant="625".
	"""
	normalized = " ".join(raw_text.strip().split())
	tokens = normalized.split(" ")

	brand_parts: list[str] = []
	variant: str | None = None
	form: str | None = None
	strength: str | None = None

	for token in tokens:
		cleaned = token.lower().strip(",.;")

		# Dosage form
		if cleaned in _FORM_TOKENS and form is None:
			form = cleaned
			continue

		# Strength with unit suffix (e.g. '500mg', '250mg/5ml', '100mcg')
		if strength is None and (
			cleaned.endswith("mg") or cleaned.endswith("ml")
			or cleaned.endswith("mcg") or "mg/" in cleaned
		):
			strength = cleaned
			continue

		# Pure digit → variant (e.g. '625')
		if cleaned.isdigit() and variant is None:
			variant = cleaned
			continue

		# Digit fraction → variant (e.g. '500/125')
		if "/" in cleaned and variant is None:
			parts = cleaned.split("/")
			if all(p.isdigit() for p in parts if p):
				variant = cleaned
				continue

		# Otherwise treat as brand word
		brand_parts.append(token)

	brand = " ".join(brand_parts) if brand_parts else "unknown"

	return ExtractedMedicine(
		raw_input=raw_text,
		brand=brand,
		variant=variant,
		strength=strength,
		form=form,
	)


async def _extract_from_openai(image_base64: str) -> Optional[ExtractedMedicine]:
	if not settings.openai_api_key:
		return None

	def _build_image_data_url(payload: str) -> str:
		trimmed = payload.strip()
		if trimmed.startswith("data:image/") and ";base64," in trimmed:
			header, encoded = trimmed.split(",", 1)
			if not encoded:
				raise ValueError("Image payload contains empty base64 data")
			return f"{header},{encoded.strip()}"

		if trimmed.startswith("/9j/"):
			mime_type = "image/jpeg"
		elif trimmed.startswith("iVBORw0KGgo"):
			mime_type = "image/png"
		elif trimmed.startswith("UklGR"):
			mime_type = "image/webp"
		else:
			mime_type = "image/png"

		return f"data:{mime_type};base64,{trimmed}"

	client = AsyncOpenAI(api_key=settings.openai_api_key)
	prompt = (
		"Extract medicine details from this prescription image and return fields: "
		"raw_input, brand, variant, generic_name, strength, form, frequency."
	)
	image_data_url = _build_image_data_url(image_base64)

	try:
		response = await client.beta.chat.completions.parse(
			model=settings.openai_model,
			messages=[
				{"role": "system", "content": "You extract medication entities deterministically."},
				{
					"role": "user",
					"content": [
						{"type": "text", "text": prompt},
						{"type": "image_url", "image_url": {"url": image_data_url}},
					],
				},
			],
			response_format=ExtractedData,
		)
		parsed = response.choices[0].message.parsed
		if parsed:
			return parsed
		return None
	except Exception as exc:
		raise ValueError(f"OpenAI VLM extraction failed: {exc}") from exc


async def extract_with_vlm(image_base64: str) -> Optional[ExtractedMedicine]:
	return await _extract_from_openai(image_base64)


async def extract_medicine(request: ExtractionRequest, guardrail_logs: list[str]) -> ExtractedMedicine:
	# NOTE: Golden cache intercept is handled at the route level (routes.py)
	# which returns the full pre-computed ExtractionResponse.
	# This function only handles the actual extraction path.
	if request.image_base64:
		if not settings.openai_api_key:
			raise ValueError("OPENAI_API_KEY is not configured for image extraction")

		openai_extracted = await extract_with_vlm(request.image_base64)
		if openai_extracted:
			guardrail_logs.append("Image extracted via OpenAI structured outputs parse()")
			return openai_extracted

		raise ValueError("OpenAI extraction returned an empty response: no medicine data could be parsed from the image")

	if request.raw_text:
		guardrail_logs.append("Raw text extracted via local NER parser")
		return _extract_from_local_ner(request.raw_text)

	raise ValueError("No image_base64 or raw_text found")


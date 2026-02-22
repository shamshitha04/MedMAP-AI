from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import ExtractedData, ExtractedDataBatch, ExtractedMedicine, ExtractionRequest, ExtractionResponse


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


def _is_pdf_base64(payload: str) -> bool:
	"""Detect if a base64 payload is a PDF by checking the magic bytes."""
	trimmed = payload.strip()
	# data:application/pdf;base64,... prefix
	if trimmed.startswith("data:application/pdf"):
		return True
	# Raw base64 — PDF magic bytes %PDF- encode to JVBER
	raw = trimmed.split(",")[-1] if "," in trimmed else trimmed
	return raw.startswith("JVBER")


def _pdf_base64_to_png_base64_pages(pdf_base64: str) -> List[str]:
	"""Convert a PDF (base64-encoded) into a list of PNG base64 strings, one per page."""
	raw = pdf_base64.strip()
	if "," in raw:
		raw = raw.split(",", 1)[1]
	pdf_bytes = base64.b64decode(raw)

	doc = fitz.open(stream=pdf_bytes, filetype="pdf")
	png_pages: List[str] = []
	try:
		for page in doc:
			# Render at 2x zoom for better OCR quality
			pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
			png_bytes = pix.tobytes("png")
			png_pages.append(base64.b64encode(png_bytes).decode("ascii"))
	finally:
		doc.close()

	if not png_pages:
		raise ValueError("PDF contained no renderable pages")
	return png_pages


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


async def _extract_from_openai(image_base64: str) -> Optional[List[ExtractedMedicine]]:
	"""Call OpenAI VLM using ExtractedDataBatch structured output to extract
	ALL medicines from the prescription image in a single API call."""
	if not settings.openai_api_key:
		return None

	client = AsyncOpenAI(api_key=settings.openai_api_key)
	prompt = (
		"You are a clinical pharmacist assistant. "
		"Extract EVERY medicine listed in this prescription image. "
		"For each medicine, populate: raw_input (exact text as written), brand, variant "
		"(numeric-only dosage token if present, e.g. '625'), generic_name, strength "
		"(value with unit, e.g. '100mg'), form (tablet/capsule/etc.), frequency (BID/TID/etc.). "
		"Return ALL medicines found — do not stop after the first one."
	)
	image_data_url = _build_image_data_url(image_base64)

	try:
		response = await client.beta.chat.completions.parse(
			model=settings.openai_model,
			messages=[
				{"role": "system", "content": "You extract ALL medication entities from prescriptions deterministically."},
				{
					"role": "user",
					"content": [
						{"type": "text", "text": prompt},
						{"type": "image_url", "image_url": {"url": image_data_url}},
					],
				},
			],
			response_format=ExtractedDataBatch,
		)
		parsed: Optional[ExtractedDataBatch] = response.choices[0].message.parsed
		if parsed and parsed.medicines:
			return list(parsed.medicines)
		return None
	except Exception as exc:
		raise ValueError(f"OpenAI VLM extraction failed: {exc}") from exc


async def _extract_from_pdf(pdf_base64: str) -> Optional[List[ExtractedMedicine]]:
	"""Convert PDF to PNG page images, then run VLM extraction on the first page."""
	png_pages = _pdf_base64_to_png_base64_pages(pdf_base64)
	# Use the first page for extraction (most prescriptions are single-page)
	return await _extract_from_openai(png_pages[0])


async def extract_with_vlm(image_base64: str) -> Optional[List[ExtractedMedicine]]:
	return await _extract_from_openai(image_base64)


def _split_raw_text_medicines(raw_text: str) -> List[str]:
	"""Split raw prescription text into medicine-specific chunks.

	Priority:
	1) New-line separated entries (common in prescriptions)
	2) Comma/semicolon/pipe separated entries
	3) Fallback to the whole input as a single medicine entry
	"""
	normalized = " ".join((raw_text or "").split())
	if not normalized:
		return []

	line_chunks = [line.strip() for line in re.split(r"[\r\n]+", raw_text or "") if line.strip()]
	if len(line_chunks) > 1:
		chunks = line_chunks
	else:
		inline_chunks = [part.strip() for part in re.split(r"\s*(?:,|;|\|)\s*", normalized) if part.strip()]
		chunks = inline_chunks if len(inline_chunks) > 1 else [normalized]

	cleaned_chunks: List[str] = []
	for chunk in chunks:
		cleaned = re.sub(r"^\s*(?:[-*]\s*|\d+[)\.\-:]\s*)", "", chunk).strip()
		if cleaned:
			cleaned_chunks.append(cleaned)

	# Preserve deterministic order while removing exact duplicates
	seen: set[str] = set()
	unique_chunks: List[str] = []
	for chunk in cleaned_chunks:
		key = chunk.lower()
		if key in seen:
			continue
		seen.add(key)
		unique_chunks.append(chunk)

	return unique_chunks


async def extract_medicines(request: ExtractionRequest, guardrail_logs: list[str]) -> List[ExtractedMedicine]:
	# NOTE: Golden cache intercept is handled at the route level (routes.py)
	# which returns the full pre-computed ExtractionResponse.
	# This function only handles the actual extraction path.
	if request.image_base64:
		if not settings.openai_api_key:
			raise ValueError("OPENAI_API_KEY is not configured for image extraction")

		# Detect PDF and convert to PNG first
		is_pdf = (
			(request.file_mime_type or "").lower() == "application/pdf"
			or _is_pdf_base64(request.image_base64)
		)

		if is_pdf:
			guardrail_logs.append("PDF detected — converting to PNG for VLM extraction")
			openai_extracted_list = await _extract_from_pdf(request.image_base64)
		else:
			openai_extracted_list = await extract_with_vlm(request.image_base64)

		if openai_extracted_list:
			count = len(openai_extracted_list)
			guardrail_logs.append(
				f"Image extracted via OpenAI structured outputs parse(): {count} medicine entr{'y' if count == 1 else 'ies'} detected"
			)
			return openai_extracted_list

		raise ValueError("OpenAI extraction returned an empty response: no medicine data could be parsed from the image")

	if request.raw_text:
		raw_chunks = _split_raw_text_medicines(request.raw_text)
		if not raw_chunks:
			raise ValueError("No medicine text could be parsed from raw_text")

		guardrail_logs.append(f"Raw text parsed into {len(raw_chunks)} medicine entr{'y' if len(raw_chunks) == 1 else 'ies'}")
		return [_extract_from_local_ner(chunk) for chunk in raw_chunks]

	raise ValueError("No image_base64 or raw_text found")


async def extract_medicine(request: ExtractionRequest, guardrail_logs: list[str]) -> ExtractedMedicine:
	extracted_items = await extract_medicines(request, guardrail_logs)
	return extracted_items[0]


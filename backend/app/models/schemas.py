from __future__ import annotations

from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class ExtractionRequest(BaseModel):
	image_base64: Optional[str] = None
	raw_text: Optional[str] = None
	prescriber_id: Optional[str] = None
	file_mime_type: Optional[str] = None

	@model_validator(mode="after")
	def validate_input_present(self) -> "ExtractionRequest":
		if not self.image_base64 and not self.raw_text:
			raise ValueError("Either image_base64 or raw_text must be provided")
		return self


class ExtractedDataBatch(BaseModel):
	"""Wrapper schema for OpenAI structured outputs — extracts ALL medicines from
	a single prescription image in one API call."""
	medicines: List["ExtractedData"]


class ExtractedData(BaseModel):
	raw_input: str = ""
	brand: str = Field(validation_alias=AliasChoices("brand", "brand_name"))
	variant: Optional[str] = Field(default=None, validation_alias=AliasChoices("variant", "brand_variant"))
	generic_name: Optional[str] = None
	strength: Optional[str] = None
	form: Optional[str] = None
	frequency: Optional[str] = None

	@field_validator("brand", mode="before")
	@classmethod
	def normalize_brand(cls, value: str) -> str:
		"""Lightweight input cleaning: strip edges and collapse internal whitespace.

		Full clinical normalization (lowercasing, form standardization, frequency
		mapping) is intentionally delegated to guardrail_service.apply_pre_match_guardrails()
		so that each transformation is individually logged in the guardrail audit trail.
		"""
		return " ".join(value.split())

	@property
	def brand_name(self) -> str:
		return self.brand

	@property
	def brand_variant(self) -> Optional[str]:
		return self.variant


class CandidateMatch(BaseModel):
	id: int
	score: float
	metadata: dict = Field(default_factory=dict)


class MatchedMedicine(BaseModel):
	id: int
	brand_name: str
	generic_name: str
	official_strength: str
	form: str
	combination_flag: bool
	final_similarity_score: float
	risk_classification: str
	clinical_risk_tier: str
	manual_review_required: bool = False


class ProcessedMedicine(BaseModel):
	original_raw_input: str
	extracted: ExtractedData
	matched_medicine: MatchedMedicine
	guardrail_logs: List[str] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
	medicines: List[ProcessedMedicine]
	guardrail_logs: List[str] = Field(default_factory=list)


ExtractedMedicine = ExtractedData


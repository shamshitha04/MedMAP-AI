from __future__ import annotations

from app.models.schemas import CandidateMatch, ExtractedData
from app.models.sql_models import MedicineRecord
from app.services.guardrail_service import apply_post_match_guardrails, apply_pre_match_guardrails


def test_pre_match_guardrails_variant_separation_and_normalization() -> None:
    guardrail_logs: list[str] = []
    extracted = ExtractedData(
        raw_input="Augmentin 625 Tab",
        brand="Augmentin 625",
        form="Tab",
        strength="625 mg",
    )

    guarded = apply_pre_match_guardrails(extracted, guardrail_logs)

    assert guarded.brand == "augmentin"
    assert guarded.variant == "625"
    assert guarded.form == "tablet"
    assert guarded.strength is None
    assert any("Variant token stripped" in log for log in guardrail_logs)


def test_post_match_guardrails_combination_lock_and_strength_injection() -> None:
    guardrail_logs: list[str] = []
    extracted = ExtractedData(
        raw_input="Augmentin 625 Tab",
        brand="augmentin",
        variant="625",
        form="tablet",
        strength="500 mg",
    )
    candidate = CandidateMatch(id=101, score=0.88, metadata={"source": "pinecone"})
    db_record = MedicineRecord(
        id=101,
        brand_name="Augmentin 625 Duo",
        generic_name="amoxicillin + clavulanic acid",
        official_strength="625 mg",
        form="tablet",
        combination_flag=True,
    )

    matched = apply_post_match_guardrails(extracted, candidate, db_record, guardrail_logs)

    assert matched.combination_flag is True
    assert matched.official_strength == "625 mg"
    assert any("Combination lock enforced" in log for log in guardrail_logs)
    assert any("Official strength injected" in log for log in guardrail_logs)


def test_post_match_guardrails_variant_and_form_mismatch_penalties() -> None:
    guardrail_logs: list[str] = []
    extracted = ExtractedData(
        raw_input="Amoxiclav 625 Syrup",
        brand="amoxiclav",
        variant="625",
        form="syrup",
        strength="625 mg",
    )
    candidate = CandidateMatch(id=77, score=0.9, metadata={"source": "pinecone"})
    db_record = MedicineRecord(
        id=77,
        brand_name="Amoxiclav 375",
        generic_name="amoxicillin + clavulanic acid",
        official_strength="375 mg",
        form="tablet",
        combination_flag=False,
    )

    matched = apply_post_match_guardrails(extracted, candidate, db_record, guardrail_logs)

    assert matched.final_similarity_score < 0.9
    assert any("Variant mismatch penalty applied" in log for log in guardrail_logs)
    assert any("Form mismatch penalty applied" in log for log in guardrail_logs)
    assert any("Official strength injected" in log for log in guardrail_logs)

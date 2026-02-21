from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.db_setup import AsyncSessionLocal, init_db
from app.models.schemas import ExtractedData
from app.models.sql_models import MedicineRecord, PrescriberMedicineHistory
from app.services.search_service import query_top_candidate


@pytest.mark.asyncio
async def test_hybrid_retrieval_falls_back_to_sqlite_without_pinecone() -> None:
    await init_db()

    extracted = ExtractedData(
        raw_input="Augmentin 625 Tab",
        brand="augmentin",
        variant="625",
        form="tablet",
    )
    guardrail_logs: list[str] = []

    async with AsyncSessionLocal() as session:
        candidate = await query_top_candidate(
            extracted=extracted,
            session=session,
            guardrail_logs=guardrail_logs,
            prescriber_id=None,
        )

    assert candidate.id > 0
    assert candidate.score >= 0.0
    assert any("Dense vector generated" in log for log in guardrail_logs)
    assert any("Hybrid retrieval fallback" in log or "Pinecone async hybrid query executed" in log for log in guardrail_logs)


@pytest.mark.asyncio
async def test_bayesian_prescriber_prior_boosts_score_from_sqlite_history() -> None:
    await init_db()
    unique_brand = f"priorcheck-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        medicine = MedicineRecord(
            brand_name=unique_brand,
            generic_name="test-generic",
            official_strength="10 mg",
            form="tablet",
            combination_flag=False,
        )
        session.add(medicine)
        await session.commit()
        await session.refresh(medicine)

        history = PrescriberMedicineHistory(
            prescriber_id="dr-prior",
            medicine_id=medicine.id,
            mapping_count=4,
        )
        session.add(history)
        await session.commit()

        extracted = ExtractedData(
            raw_input=f"{unique_brand} tab",
            brand=unique_brand,
            variant=None,
            form="tablet",
        )
        guardrail_logs: list[str] = []

        candidate = await query_top_candidate(
            extracted=extracted,
            session=session,
            guardrail_logs=guardrail_logs,
            prescriber_id="dr-prior",
        )

        expected = await session.execute(select(MedicineRecord.id).where(MedicineRecord.id == medicine.id))
        assert expected.scalar_one_or_none() == candidate.id
        assert candidate.score > 0.78
        assert any("Bayesian prescriber prior applied" in log for log in guardrail_logs)

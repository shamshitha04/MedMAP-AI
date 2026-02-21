from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db_setup import AsyncSessionLocal, init_db
from app.models.schemas import ExtractionResponse
from app.models.sql_models import MedicineRecord


@pytest.mark.asyncio
async def test_phase1_ground_truth_and_response_contract() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        mock = MedicineRecord(
            brand_name="Augmentin 625 Duo",
            generic_name="amoxicillin + clavulanic acid",
            official_strength="625 mg",
            form="tablet",
            combination_flag=True,
        )
        session.add(mock)
        await session.commit()
        await session.refresh(mock)

        result = await session.execute(
            select(MedicineRecord).where(MedicineRecord.id == mock.id)
        )
        inserted = result.scalar_one_or_none()

    assert inserted is not None
    assert inserted.combination_flag is True

    app = FastAPI()

    @app.get("/contract")
    async def contract() -> dict:
        return {
            "medicines": [
                {
                    "original_raw_input": "Augmentin 625 Duo Tab",
                    "extracted": {
                        "raw_input": "Augmentin 625 Duo Tab",
                        "brand": "Augmentin",
                        "variant": "625",
                        "form": "tablet",
                    },
                    "matched_medicine": {
                        "id": inserted.id,
                        "brand_name": inserted.brand_name,
                        "generic_name": inserted.generic_name,
                        "official_strength": inserted.official_strength,
                        "form": inserted.form,
                        "combination_flag": inserted.combination_flag,
                        "final_similarity_score": 0.94,
                        "risk_classification": "High",
                        "clinical_risk_tier": "High",
                        "manual_review_required": False,
                    },
                    "guardrail_logs": [],
                }
            ],
            "guardrail_logs": [],
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/contract")

    assert response.status_code == 200

    validated = ExtractionResponse.model_validate(response.json())
    assert validated.guardrail_logs == []
    assert validated.medicines[0].guardrail_logs == []
    assert validated.medicines[0].matched_medicine is not None
    assert validated.medicines[0].matched_medicine.official_strength == "625 mg"

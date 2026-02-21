from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db_setup import AsyncSessionLocal, init_db
from app.main import app
from app.models.sql_models import MedicineRecord


@pytest.mark.asyncio
async def test_extract_grounded_output_payload_contract() -> None:
    await init_db()
    brand_token = f"grounded-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        session.add(
            MedicineRecord(
                brand_name=brand_token,
                generic_name="test generic",
                official_strength="111 mg",
                form="tablet",
                combination_flag=False,
            )
        )
        await session.commit()
        check = await session.execute(select(MedicineRecord.id).where(MedicineRecord.brand_name == brand_token))
        assert check.scalar_one_or_none() is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/extract",
            json={
                "raw_text": f"{brand_token} Tab BD",
                "prescriber_id": "dr-1",
            },
        )

    assert response.status_code == 200
    payload = response.json()

    assert "medicines" in payload
    assert isinstance(payload["medicines"], list)
    assert len(payload["medicines"]) >= 1
    assert "guardrail_logs" in payload
    assert isinstance(payload["guardrail_logs"], list)

    item = payload["medicines"][0]
    assert "original_raw_input" in item
    assert isinstance(item["original_raw_input"], str)

    assert "extracted" in item
    assert isinstance(item["extracted"], dict)

    assert "matched_medicine" in item
    matched = item["matched_medicine"]
    assert isinstance(matched, dict)

    required_matched_fields = {
        "id",
        "brand_name",
        "generic_name",
        "official_strength",
        "form",
        "final_similarity_score",
        "risk_classification",
    }
    assert required_matched_fields.issubset(matched.keys())
    assert isinstance(matched["id"], int)
    assert isinstance(matched["final_similarity_score"], float)
    assert matched["risk_classification"] in {"High", "Medium", "Low"}

    assert "guardrail_logs" in item
    assert isinstance(item["guardrail_logs"], list)

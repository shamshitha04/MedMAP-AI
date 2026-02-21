from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db_setup import init_db
from app.main import app


@pytest.mark.asyncio
async def test_extract_endpoint_returns_200() -> None:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/extract",
            json={
                "raw_text": "Augmentin 625 Tab BD",
                "prescriber_id": "dr-1",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "medicines" in payload
    assert isinstance(payload["medicines"], list)
    assert payload["medicines"][0]["guardrail_logs"]
    assert payload["guardrail_logs"]
    matched = payload["medicines"][0]["matched_medicine"]
    assert isinstance(matched["final_similarity_score"], float)
    assert matched["risk_classification"] in {"High", "Medium", "Low"}
    assert matched["clinical_risk_tier"] in {"High", "Medium", "Low"}

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db_setup import AsyncSessionLocal, init_db
from app.models.sql_models import MedicineRecord


@pytest.mark.asyncio
async def test_async_insert_and_retrieve_combination_flag_true() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        medicine = MedicineRecord(
            brand_name="test-combo",
            generic_name="drug a + drug b",
            official_strength="100/25 mg",
            form="tablet",
            combination_flag=True,
        )
        session.add(medicine)
        await session.commit()

        result = await session.execute(
            select(MedicineRecord).where(MedicineRecord.brand_name == "test-combo")
        )
        fetched = result.scalar_one_or_none()

    assert fetched is not None
    assert fetched.combination_flag is True

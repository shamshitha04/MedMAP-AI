from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.sql_models import Base, MedicineRecord, PrescriberMedicineHistory

engine = create_async_engine(settings.database_url, future=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


SAMPLE_MEDICINES: List[Dict[str, Any]] = [
	# Co-Amoxiclav / Augmentin variants
	{"brand_name": "Augmentin 625 Duo", "generic_name": "co-amoxiclav", "official_strength": "625 mg", "form": "tablet", "combination_flag": True},
	{"brand_name": "Augmentin 375", "generic_name": "co-amoxiclav", "official_strength": "375 mg", "form": "tablet", "combination_flag": True},
	{"brand_name": "Amoxiclav 500/125", "generic_name": "co-amoxiclav", "official_strength": "500/125 mg", "form": "tablet", "combination_flag": True},
	# Paracetamol
	{"brand_name": "Panadol 500mg", "generic_name": "paracetamol", "official_strength": "500 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Panadol 1g", "generic_name": "paracetamol", "official_strength": "1000 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Calpol 250mg/5ml", "generic_name": "paracetamol", "official_strength": "250 mg/5 ml", "form": "syrup", "combination_flag": False},
	# Amoxicillin
	{"brand_name": "Amoxicillin 250mg", "generic_name": "amoxicillin", "official_strength": "250 mg", "form": "capsule", "combination_flag": False},
	{"brand_name": "Amoxicillin 500mg", "generic_name": "amoxicillin", "official_strength": "500 mg", "form": "capsule", "combination_flag": False},
	{"brand_name": "Amoxil 500mg", "generic_name": "amoxicillin", "official_strength": "500 mg", "form": "capsule", "combination_flag": False},
	# Ibuprofen
	{"brand_name": "Brufen 400mg", "generic_name": "ibuprofen", "official_strength": "400 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Brufen 600mg", "generic_name": "ibuprofen", "official_strength": "600 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Nurofen 200mg", "generic_name": "ibuprofen", "official_strength": "200 mg", "form": "tablet", "combination_flag": False},
	# Metformin
	{"brand_name": "Glucophage 500mg", "generic_name": "metformin", "official_strength": "500 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Glucophage 850mg", "generic_name": "metformin", "official_strength": "850 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Glucophage 1000mg", "generic_name": "metformin", "official_strength": "1000 mg", "form": "tablet", "combination_flag": False},
	# Amlodipine
	{"brand_name": "Norvasc 5mg", "generic_name": "amlodipine", "official_strength": "5 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Norvasc 10mg", "generic_name": "amlodipine", "official_strength": "10 mg", "form": "tablet", "combination_flag": False},
	# Atorvastatin
	{"brand_name": "Lipitor 10mg", "generic_name": "atorvastatin", "official_strength": "10 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Lipitor 20mg", "generic_name": "atorvastatin", "official_strength": "20 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Lipitor 40mg", "generic_name": "atorvastatin", "official_strength": "40 mg", "form": "tablet", "combination_flag": False},
	# Omeprazole
	{"brand_name": "Losec 20mg", "generic_name": "omeprazole", "official_strength": "20 mg", "form": "capsule", "combination_flag": False},
	{"brand_name": "Prilosec 40mg", "generic_name": "omeprazole", "official_strength": "40 mg", "form": "capsule", "combination_flag": False},
	# Cetirizine
	{"brand_name": "Zyrtec 10mg", "generic_name": "cetirizine", "official_strength": "10 mg", "form": "tablet", "combination_flag": False},
	# Azithromycin
	{"brand_name": "Zithromax 250mg", "generic_name": "azithromycin", "official_strength": "250 mg", "form": "capsule", "combination_flag": False},
	{"brand_name": "Zithromax 500mg", "generic_name": "azithromycin", "official_strength": "500 mg", "form": "tablet", "combination_flag": False},
	# Ciprofloxacin
	{"brand_name": "Cipro 500mg", "generic_name": "ciprofloxacin", "official_strength": "500 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Cipro 750mg", "generic_name": "ciprofloxacin", "official_strength": "750 mg", "form": "tablet", "combination_flag": False},
	# Dexamethasone
	{"brand_name": "Decadron 4mg", "generic_name": "dexamethasone", "official_strength": "4 mg", "form": "tablet", "combination_flag": False},
	# Prednisolone
	{"brand_name": "Prednisolone 5mg", "generic_name": "prednisolone", "official_strength": "5 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Prednisolone 25mg", "generic_name": "prednisolone", "official_strength": "25 mg", "form": "tablet", "combination_flag": False},
	# Salbutamol
	{"brand_name": "Ventolin 100mcg", "generic_name": "salbutamol", "official_strength": "100 mcg", "form": "inhaler", "combination_flag": False},
	# Losartan
	{"brand_name": "Cozaar 50mg", "generic_name": "losartan", "official_strength": "50 mg", "form": "tablet", "combination_flag": False},
	{"brand_name": "Cozaar 100mg", "generic_name": "losartan", "official_strength": "100 mg", "form": "tablet", "combination_flag": False},
	# Pantoprazole
	{"brand_name": "Pantoloc 40mg", "generic_name": "pantoprazole", "official_strength": "40 mg", "form": "tablet", "combination_flag": False},
]


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
	async with AsyncSessionLocal() as session:
		yield session


async def init_db() -> None:
	async with engine.begin() as connection:
		await connection.run_sync(Base.metadata.create_all)


async def seed_db() -> None:
	async with AsyncSessionLocal() as session:
		for sample in SAMPLE_MEDICINES:
			existing = await session.execute(
				select(MedicineRecord.id).where(MedicineRecord.brand_name == sample["brand_name"]).limit(1)
			)
			if existing.scalars().first() is None:
				session.add(MedicineRecord(**sample))

		await session.commit()

		augmentin_result = await session.execute(
			select(MedicineRecord.id).where(MedicineRecord.brand_name == "Augmentin 625 Duo").limit(1)
		)
		augmentin_id = augmentin_result.scalars().first()
		if augmentin_id is not None:
			existing_mapping = await session.execute(
				select(PrescriberMedicineHistory.id)
				.where(PrescriberMedicineHistory.prescriber_id == "dr-1")
				.where(PrescriberMedicineHistory.medicine_id == augmentin_id)
				.limit(1)
			)
			if existing_mapping.scalars().first() is None:
				session.add(
					PrescriberMedicineHistory(
						prescriber_id="dr-1",
						medicine_id=augmentin_id,
						mapping_count=5,
					)
				)

		await session.commit()



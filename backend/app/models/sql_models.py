from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
	pass


class Base(DeclarativeBase):
	pass


class MedicineRecord(Base):
	__tablename__ = "medicine_records"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
	brand_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
	generic_name: Mapped[str] = mapped_column(String(255), nullable=False)
	official_strength: Mapped[str] = mapped_column(String(64), nullable=False)
	form: Mapped[str] = mapped_column(String(64), nullable=False)
	combination_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
	created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), nullable=True)
	updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

	# Reverse relationship: all prescriber history entries for this medicine
	prescriber_history: Mapped[List["PrescriberMedicineHistory"]] = relationship(
		"PrescriberMedicineHistory", back_populates="medicine", cascade="all, delete-orphan"
	)


class PrescriberMedicineHistory(Base):
	__tablename__ = "prescriber_medicine_history"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	prescriber_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
	medicine_id: Mapped[int] = mapped_column(ForeignKey("medicine_records.id", ondelete="CASCADE"), nullable=False, index=True)
	mapping_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
	created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), nullable=True)
	updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

	# Forward relationship: the medicine this history entry refers to
	medicine: Mapped["MedicineRecord"] = relationship(
		"MedicineRecord", back_populates="prescriber_history"
	)


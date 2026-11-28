from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.technician import Technician
    from app.models.work_order import WorkOrder


class ServiceRecord(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "service_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["work_order_id", "equipment_id"],
            ["work_orders.id", "work_orders.equipment_id"],
            name="fk_service_records_work_order_equipment",
            ondelete="RESTRICT",
        ),
        Index("ix_service_records_equipment_id", "equipment_id"),
        Index("ix_service_records_work_order_id", "work_order_id"),
        Index("ix_service_records_technician_id", "technician_id"),
        Index("ix_service_records_service_date", "service_date"),
    )

    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT"),
        nullable=False,
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    technician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("technicians.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=func.current_date(),
    )
    work_performed: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    parts_replaced: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment: Mapped[Equipment] = relationship(
        back_populates="service_records",
        foreign_keys=[equipment_id],
    )
    work_order: Mapped[WorkOrder | None] = relationship(
        back_populates="service_records",
        primaryjoin=(
            "and_(ServiceRecord.work_order_id == WorkOrder.id, "
            "ServiceRecord.equipment_id == WorkOrder.equipment_id)"
        ),
        foreign_keys="[ServiceRecord.work_order_id, ServiceRecord.equipment_id]",
        overlaps="equipment,service_records",
    )
    technician: Mapped[Technician] = relationship(
        back_populates="service_records",
    )

    def __repr__(self) -> str:
        return f"ServiceRecord(id={self.id!r}, equipment_id={self.equipment_id!r})"

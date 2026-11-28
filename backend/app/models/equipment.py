from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    EquipmentOperationalStatus,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.customer import Customer
    from app.models.equipment_document import EquipmentDocument
    from app.models.service_record import ServiceRecord
    from app.models.work_order import WorkOrder


class Equipment(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "equipment"
    __table_args__ = (
        UniqueConstraint(
            "manufacturer",
            "serial_number",
            name="uq_equipment_manufacturer_serial_number",
        ),
        UniqueConstraint(
            "id",
            "customer_id",
            name="uq_equipment_id_customer_id",
        ),
        Index("ix_equipment_customer_id", "customer_id"),
        Index("ix_equipment_serial_number", "serial_number"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    manufacturer: Mapped[str] = mapped_column(String(150), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    equipment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    installation_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    operational_status: Mapped[EquipmentOperationalStatus] = mapped_column(
        enum_type(
            EquipmentOperationalStatus,
            "equipment_operational_status",
            length=30,
        ),
        nullable=False,
        default=EquipmentOperationalStatus.ACTIVE,
        server_default=EquipmentOperationalStatus.ACTIVE.value,
    )

    customer: Mapped[Customer] = relationship(back_populates="equipment")
    complaints: Mapped[list[Complaint]] = relationship(
        back_populates="equipment",
        primaryjoin=(
            "and_(Complaint.equipment_id == Equipment.id, "
            "Complaint.customer_id == Equipment.customer_id)"
        ),
        foreign_keys="[Complaint.equipment_id, Complaint.customer_id]",
        overlaps="complaints,customer,equipment",
        passive_deletes="all",
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="equipment",
        primaryjoin=(
            "and_(WorkOrder.equipment_id == Equipment.id, "
            "WorkOrder.customer_id == Equipment.customer_id)"
        ),
        foreign_keys="[WorkOrder.equipment_id, WorkOrder.customer_id]",
        overlaps="complaint,customer,equipment,work_orders",
        passive_deletes="all",
    )
    service_records: Mapped[list[ServiceRecord]] = relationship(
        back_populates="equipment",
        passive_deletes="all",
    )
    documents: Mapped[list[EquipmentDocument]] = relationship(
        back_populates="equipment",
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"Equipment(id={self.id!r}, model={self.model!r})"

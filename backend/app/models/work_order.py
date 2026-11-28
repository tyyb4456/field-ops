from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    Priority,
    WorkOrderStatus,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.customer import Customer
    from app.models.equipment import Equipment
    from app.models.service_record import ServiceRecord
    from app.models.technician_assignment import TechnicianAssignment


class WorkOrder(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["complaint_id", "customer_id", "equipment_id"],
            [
                "complaints.id",
                "complaints.customer_id",
                "complaints.equipment_id",
            ],
            name="fk_work_orders_complaint_equipment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["equipment_id", "customer_id"],
            ["equipment.id", "equipment.customer_id"],
            name="fk_work_orders_equipment_customer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "complaint_id",
            name="uq_work_orders_complaint_id",
        ),
        UniqueConstraint(
            "id",
            "equipment_id",
            name="uq_work_orders_id_equipment_id",
        ),
        CheckConstraint(
            "status <> 'completed' OR completion_date IS NOT NULL",
            name="completed_requires_completion_date",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'assigned', 'in_progress', "
            "'on_hold', 'completed') OR "
            "(approved_by_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="approval_consistency",
        ),
        Index("ix_work_orders_customer_id", "customer_id"),
        Index("ix_work_orders_equipment_id", "equipment_id"),
        Index("ix_work_orders_status", "status"),
        Index("ix_work_orders_priority", "priority"),
        Index("ix_work_orders_scheduled_date", "scheduled_date"),
        Index("ix_work_orders_created_at", "created_at"),
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    equipment_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    work_order_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic_findings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    required_actions: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority, "work_order_priority", length=20),
        nullable=False,
        default=Priority.NORMAL,
        server_default=Priority.NORMAL.value,
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        enum_type(WorkOrderStatus, "work_order_status", length=30),
        nullable=False,
        default=WorkOrderStatus.DRAFT,
        server_default=WorkOrderStatus.DRAFT.value,
    )
    scheduled_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    completion_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    completion_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    complaint: Mapped[Complaint] = relationship(
        back_populates="work_order",
        primaryjoin=(
            "and_(WorkOrder.complaint_id == Complaint.id, "
            "WorkOrder.customer_id == Complaint.customer_id, "
            "WorkOrder.equipment_id == Complaint.equipment_id)"
        ),
        foreign_keys="[WorkOrder.complaint_id, WorkOrder.customer_id, "
        "WorkOrder.equipment_id]",
        overlaps="customer,equipment,work_orders",
    )
    customer: Mapped[Customer] = relationship(
        back_populates="work_orders",
        primaryjoin="WorkOrder.customer_id == Customer.id",
        foreign_keys="[WorkOrder.customer_id]",
        overlaps="complaint,equipment",
    )
    equipment: Mapped[Equipment] = relationship(
        back_populates="work_orders",
        primaryjoin=(
            "and_(WorkOrder.equipment_id == Equipment.id, "
            "WorkOrder.customer_id == Equipment.customer_id)"
        ),
        foreign_keys="[WorkOrder.equipment_id, WorkOrder.customer_id]",
        overlaps="complaint,customer,equipment",
    )
    assignments: Mapped[list[TechnicianAssignment]] = relationship(
        back_populates="work_order",
        passive_deletes="all",
        order_by="TechnicianAssignment.assigned_at",
    )
    service_records: Mapped[list[ServiceRecord]] = relationship(
        back_populates="work_order",
        primaryjoin=(
            "and_(ServiceRecord.work_order_id == WorkOrder.id, "
            "ServiceRecord.equipment_id == WorkOrder.equipment_id)"
        ),
        foreign_keys="[ServiceRecord.work_order_id, ServiceRecord.equipment_id]",
        overlaps="equipment,service_records",
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return (
            f"WorkOrder(id={self.id!r}, "
            f"number={self.work_order_number!r}, status={self.status!r})"
        )

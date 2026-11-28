from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
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
    Channel,
    ComplaintStatus,
    Priority,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.equipment import Equipment
    from app.models.work_order import WorkOrder


class Complaint(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["equipment_id", "customer_id"],
            ["equipment.id", "equipment.customer_id"],
            name="fk_complaints_equipment_customer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "customer_id",
            "equipment_id",
            name="uq_complaints_id_customer_equipment",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'under_investigation', "
            "'converted_to_work_order') OR "
            "(approved_by_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="approval_consistency",
        ),
        CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL",
            name="rejection_requires_reason",
        ),
        Index("ix_complaints_customer_id", "customer_id"),
        Index("ix_complaints_equipment_id", "equipment_id"),
        Index("ix_complaints_status", "status"),
        Index("ix_complaints_priority", "priority"),
        Index("ix_complaints_origin_conversation_id", "origin_conversation_id"),
        Index("ix_complaints_created_at", "created_at"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    origin_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reported_symptoms: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    reported_error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    channel: Mapped[Channel] = mapped_column(
        enum_type(Channel, "complaint_channel", length=20),
        nullable=False,
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        enum_type(ComplaintStatus, "complaint_status", length=40),
        nullable=False,
        default=ComplaintStatus.DRAFT,
        server_default=ComplaintStatus.DRAFT.value,
    )
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority, "complaint_priority", length=20),
        nullable=False,
        default=Priority.NORMAL,
        server_default=Priority.NORMAL.value,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    customer: Mapped[Customer] = relationship(
        back_populates="complaints",
        foreign_keys=[customer_id],
    )
    equipment: Mapped[Equipment | None] = relationship(
        back_populates="complaints",
        primaryjoin=(
            "and_(Complaint.equipment_id == Equipment.id, "
            "Complaint.customer_id == Equipment.customer_id)"
        ),
        foreign_keys="[Complaint.equipment_id, Complaint.customer_id]",
        overlaps="customer,equipment",
    )
    origin_conversation: Mapped[Conversation | None] = relationship(
        back_populates="complaints",
        foreign_keys=[origin_conversation_id],
    )
    work_order: Mapped[WorkOrder | None] = relationship(
        back_populates="complaint",
        foreign_keys="WorkOrder.complaint_id",
        uselist=False,
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"Complaint(id={self.id!r}, status={self.status!r})"

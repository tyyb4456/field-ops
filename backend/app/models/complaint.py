from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
    ComplaintChannel,
    ComplaintStatus,
    Priority,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.equipment import Equipment



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
            "equipment_id",
            name="uq_complaints_id_equipment_id",
        ),
        UniqueConstraint(
            "origin_conversation_id",
            name="uq_complaints_origin_conversation_id",
        ),
        Index("ix_complaints_customer_id", "customer_id"),
        Index("ix_complaints_equipment_id", "equipment_id"),
        Index("ix_complaints_status", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="RESTRICT"),
        nullable=True,
    )
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
    channel: Mapped[ComplaintChannel] = mapped_column(
        enum_type(ComplaintChannel, "complaint_channel", length=20),
        nullable=False,
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        enum_type(ComplaintStatus, "complaint_status"),
        nullable=False,
        default=ComplaintStatus.RECEIVED,
        server_default=ComplaintStatus.RECEIVED.value,
    )
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority, "complaint_priority", length=20),
        nullable=False,
        default=Priority.NORMAL,
        server_default=Priority.NORMAL.value,
    )

    customer: Mapped[Customer] = relationship(
        back_populates="complaints",
        foreign_keys=[customer_id],
    )
    equipment: Mapped[Equipment | None] = relationship(
        back_populates="complaints",
        foreign_keys=[equipment_id],
    )
    origin_conversation: Mapped[Conversation | None] = relationship(
        foreign_keys=[origin_conversation_id],
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"Complaint(id={self.id!r}, status={self.status!r})"

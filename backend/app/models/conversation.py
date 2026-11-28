from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    Channel,
    ConversationStatus,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.customer import Customer
    from app.models.message import Message


class Conversation(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index(
            "ix_conversations_customer_last_activity",
            "customer_id",
            "last_activity_at",
        ),
        Index("ix_conversations_status", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        enum_type(ConversationStatus, "conversation_status", length=30),
        nullable=False,
        default=ConversationStatus.ACTIVE,
        server_default=ConversationStatus.ACTIVE.value,
    )
    channel: Mapped[Channel] = mapped_column(
        enum_type(Channel, "conversation_channel", length=20),
        nullable=False,
        default=Channel.WEB,
        server_default=Channel.WEB.value,
    )
    external_conversation_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    conversation_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    customer: Mapped[Customer] = relationship(
        back_populates="conversations",
        foreign_keys=[customer_id],
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )
    complaints: Mapped[list[Complaint]] = relationship(
        back_populates="origin_conversation",
        foreign_keys="Complaint.origin_conversation_id",
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id!r}, customer_id={self.customer_id!r})"

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.customer import Customer


class Conversation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Minimal conversation record required by existing relationships.

    The full conversation/message domain is intentionally deferred to a later
    phase. This model exists so the current complaint and customer model
    registry can be configured safely.
    """

    __tablename__ = "conversations"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    customer: Mapped[Customer] = relationship(
        back_populates="conversations",
        foreign_keys=[customer_id],
    )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id!r}, customer_id={self.customer_id!r})"

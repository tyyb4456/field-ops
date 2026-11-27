from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.technician import Technician


class TechnicianAssignment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Minimal assignment record required by existing relationships.

    The full assignment/work-order domain is intentionally deferred to a later
    phase. This model exists so the technician model registry can be configured
    safely and account services can import it.
    """

    __tablename__ = "technician_assignments"

    technician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("technicians.id", ondelete="RESTRICT"),
        nullable=False,
    )

    technician: Mapped[Technician] = relationship(
        back_populates="assignments",
        foreign_keys=[technician_id],
    )

    def __repr__(self) -> str:
        return (
            f"TechnicianAssignment(id={self.id!r}, "
            f"technician_id={self.technician_id!r})"
        )

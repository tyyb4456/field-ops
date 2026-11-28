from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    TechnicianAssignmentStatus,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.technician import Technician
    from app.models.work_order import WorkOrder


class TechnicianAssignment(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "technician_assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_status <> 'accepted' OR accepted_at IS NOT NULL",
            name="accepted_requires_timestamp",
        ),
        CheckConstraint(
            "assignment_status <> 'rejected' OR rejected_at IS NOT NULL",
            name="rejected_requires_timestamp",
        ),
        Index("ix_technician_assignments_work_order_id", "work_order_id"),
        Index("ix_technician_assignments_technician_id", "technician_id"),
        Index("ix_technician_assignments_status", "assignment_status"),
        Index("ix_technician_assignments_assigned_at", "assigned_at"),
        Index(
            "ix_technician_assignments_technician_status",
            "technician_id",
            "assignment_status",
        ),
        Index(
            "uq_technician_assignments_active_work_order",
            "work_order_id",
            unique=True,
            postgresql_where=text("assignment_status IN ('offered', 'accepted')"),
        ),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    technician_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("technicians.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assignment_status: Mapped[TechnicianAssignmentStatus] = mapped_column(
        enum_type(
            TechnicianAssignmentStatus,
            "technician_assignment_status",
            length=20,
        ),
        nullable=False,
        default=TechnicianAssignmentStatus.OFFERED,
        server_default=TechnicianAssignmentStatus.OFFERED.value,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    assignment_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    work_order: Mapped[WorkOrder] = relationship(
        back_populates="assignments",
    )
    technician: Mapped[Technician] = relationship(
        back_populates="assignments",
    )

    def __repr__(self) -> str:
        return (
            f"TechnicianAssignment(id={self.id!r}, "
            f"work_order_id={self.work_order_id!r}, "
            f"status={self.assignment_status!r})"
        )

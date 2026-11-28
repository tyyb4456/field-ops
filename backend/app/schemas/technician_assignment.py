from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.models.enums import TechnicianAssignmentStatus
from app.schemas.common import ORMModel, StrictRequest


class TechnicianAssignmentCreate(StrictRequest):
    technician_id: uuid.UUID
    assignment_notes: str | None = Field(default=None, max_length=5_000)


class AssignmentReject(StrictRequest):
    rejection_reason: str | None = Field(default=None, max_length=5_000)


class ReassignRequest(StrictRequest):
    technician_id: uuid.UUID
    assignment_notes: str | None = Field(default=None, max_length=5_000)


class TechnicianAssignmentResponse(ORMModel):
    id: uuid.UUID
    work_order_id: uuid.UUID
    technician_id: uuid.UUID
    assignment_status: TechnicianAssignmentStatus
    assigned_at: datetime
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assignment_notes: str | None = None
    rejection_reason: str | None = None
    assigned_by_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class TechnicianAssignmentListResponse(ORMModel):
    items: list[TechnicianAssignmentResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "AssignmentReject",
    "ReassignRequest",
    "TechnicianAssignmentCreate",
    "TechnicianAssignmentListResponse",
    "TechnicianAssignmentResponse",
]

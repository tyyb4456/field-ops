from __future__ import annotations

import uuid
from datetime import datetime

from app.models.enums import TechnicianAssignmentStatus
from app.schemas.common import ORMModel, StrictRequest


class TechnicianAssignmentCreate(StrictRequest):
    work_order_id: uuid.UUID
    technician_id: uuid.UUID
    assignment_notes: str | None = None
    assigned_by_id: uuid.UUID | None = None


class TechnicianAssignmentUpdate(StrictRequest):
    assignment_status: TechnicianAssignmentStatus | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assignment_notes: str | None = None
    rejection_reason: str | None = None


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

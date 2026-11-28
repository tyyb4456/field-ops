from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import Channel, ComplaintStatus, Priority
from app.schemas.common import ORMModel, StrictRequest


class ComplaintCreate(StrictRequest):
    customer_id: uuid.UUID | None = Field(
        default=None,
        description="Administrators only: customer filing the complaint.",
    )
    equipment_id: uuid.UUID | None = None
    origin_conversation_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=10_000)
    reported_symptoms: list[Any] = Field(default_factory=list)
    reported_error_code: str | None = Field(default=None, max_length=100)
    channel: Channel
    priority: Priority = Priority.NORMAL


class ComplaintUpdate(StrictRequest):
    equipment_id: uuid.UUID | None = None
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    reported_symptoms: list[Any] | None = None
    reported_error_code: str | None = Field(default=None, max_length=100)
    priority: Priority | None = None


class ComplaintApprove(StrictRequest):
    notes: str | None = Field(default=None, max_length=5_000)


class ComplaintReject(StrictRequest):
    rejection_reason: str = Field(min_length=1, max_length=5_000)


class ComplaintResponse(ORMModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    origin_conversation_id: uuid.UUID | None = None
    description: str
    reported_symptoms: list[Any]
    reported_error_code: str | None = None
    channel: Channel
    status: ComplaintStatus
    priority: Priority
    submitted_at: datetime | None = None
    approved_by_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    approval_notes: str | None = None
    rejection_reason: str | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ComplaintListResponse(ORMModel):
    items: list[ComplaintResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "ComplaintApprove",
    "ComplaintCreate",
    "ComplaintListResponse",
    "ComplaintReject",
    "ComplaintResponse",
    "ComplaintUpdate",
]

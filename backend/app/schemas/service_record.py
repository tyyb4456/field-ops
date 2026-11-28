from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ORMModel, StrictRequest


class ServiceRecordCreate(StrictRequest):
    equipment_id: uuid.UUID
    work_order_id: uuid.UUID | None = None
    technician_id: uuid.UUID | None = Field(
        default=None,
        description="Administrators only: technician who performed the work.",
    )
    service_date: date | None = None
    work_performed: str | None = Field(default=None, max_length=20_000)
    findings: str | None = Field(default=None, max_length=20_000)
    parts_replaced: list[Any] = Field(default_factory=list)
    recommendations: str | None = Field(default=None, max_length=20_000)
    completion_notes: str | None = Field(default=None, max_length=20_000)


class ServiceRecordResponse(ORMModel):
    id: uuid.UUID
    equipment_id: uuid.UUID
    work_order_id: uuid.UUID | None = None
    technician_id: uuid.UUID
    service_date: date
    work_performed: str | None = None
    findings: str | None = None
    parts_replaced: list[Any]
    recommendations: str | None = None
    completion_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ServiceRecordListResponse(ORMModel):
    items: list[ServiceRecordResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "ServiceRecordCreate",
    "ServiceRecordListResponse",
    "ServiceRecordResponse",
]

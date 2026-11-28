from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ORMModel, StrictRequest


class ServiceRecordCreate(StrictRequest):
    equipment_id: uuid.UUID
    work_order_id: uuid.UUID | None = None
    technician_id: uuid.UUID
    service_date: date | None = None
    work_performed: str | None = None
    findings: str | None = None
    parts_replaced: list[Any] = Field(default_factory=list)
    recommendations: str | None = None
    completion_notes: str | None = None


class ServiceRecordUpdate(StrictRequest):
    work_order_id: uuid.UUID | None = None
    service_date: date | None = None
    work_performed: str | None = None
    findings: str | None = None
    parts_replaced: list[Any] | None = None
    recommendations: str | None = None
    completion_notes: str | None = None


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

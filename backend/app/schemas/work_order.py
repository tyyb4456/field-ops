from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field

from app.models.enums import Priority, WorkOrderStatus
from app.schemas.common import ORMModel, StrictRequest


class WorkOrderCreate(StrictRequest):
    complaint_id: uuid.UUID
    work_order_number: str | None = Field(default=None, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    diagnostic_findings: str | None = None
    required_actions: list[Any] = Field(default_factory=list)
    priority: Priority = Priority.NORMAL
    scheduled_date: date | None = None


class WorkOrderUpdate(StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=10_000,
    )
    diagnostic_findings: str | None = None
    required_actions: list[Any] | None = None
    priority: Priority | None = None
    scheduled_date: date | None = None


class WorkOrderComplete(StrictRequest):
    completion_summary: str = Field(min_length=1, max_length=10_000)
    completion_date: date | None = None


class WorkOrderResponse(ORMModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    customer_id: uuid.UUID
    equipment_id: uuid.UUID
    work_order_number: str
    title: str
    description: str
    diagnostic_findings: str | None = None
    required_actions: list[Any]
    priority: Priority
    status: WorkOrderStatus
    scheduled_date: date | None = None
    completion_date: date | None = None
    completion_summary: str | None = None
    approved_by_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkOrderListResponse(ORMModel):
    items: list[WorkOrderResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "WorkOrderComplete",
    "WorkOrderCreate",
    "WorkOrderListResponse",
    "WorkOrderResponse",
    "WorkOrderUpdate",
]

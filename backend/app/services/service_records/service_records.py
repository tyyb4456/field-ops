from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    TechnicianAssignmentStatus,
    WorkOrderStatus,
)
from app.models.equipment import Equipment
from app.models.service_record import ServiceRecord
from app.models.technician import Technician
from app.models.technician_assignment import TechnicianAssignment
from app.models.work_order import WorkOrder
from app.schemas.service_record import ServiceRecordCreate
from app.services.shared.access import (
    get_equipment_or_404,
    require_technician,
    technician_has_equipment_access,
)
from app.services.shared.actor import ActorContext
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.services.shared.transactions import flush

SERVICEABLE_WORK_ORDER_STATUSES = {
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.COMPLETED,
}


async def _resolve_technician_id(
    actor: ActorContext,
    requested_technician_id: uuid.UUID | None,
) -> uuid.UUID:
    if actor.is_technician:
        own_id = require_technician(actor)
        if (
            requested_technician_id is not None
            and requested_technician_id != own_id
        ):
            raise ForbiddenError(
                "Technicians can only record their own service work."
            )
        return own_id

    if actor.is_admin:
        if requested_technician_id is None:
            raise DomainValidationError(
                "technician_id is required when an administrator creates a "
                "service record."
            )
        return requested_technician_id

    raise ForbiddenError(
        "You do not have permission to create service records."
    )


async def _get_accepted_assignment(
    session: AsyncSession,
    work_order_id: uuid.UUID,
    technician_id: uuid.UUID,
) -> TechnicianAssignment | None:
    return (
        await session.execute(
            select(TechnicianAssignment)
            .where(
                TechnicianAssignment.work_order_id == work_order_id,
                TechnicianAssignment.technician_id == technician_id,
                TechnicianAssignment.assignment_status
                == TechnicianAssignmentStatus.ACCEPTED,
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def create_service_record(
    session: AsyncSession,
    actor: ActorContext,
    data: ServiceRecordCreate,
) -> ServiceRecord:
    technician_id = await _resolve_technician_id(
        actor,
        data.technician_id,
    )

    technician = await session.get(Technician, technician_id)
    if technician is None:
        raise NotFoundError("Technician not found.")
    if not technician.is_active:
        raise ConflictError("The technician account is inactive.")

    equipment = await get_equipment_or_404(session, data.equipment_id)

    if data.work_order_id is not None:
        work_order = await session.get(WorkOrder, data.work_order_id)
        if work_order is None:
            raise NotFoundError("Work order not found.")
        if work_order.equipment_id != equipment.id:
            raise DomainValidationError(
                "The work order does not reference this equipment."
            )
        if work_order.status not in SERVICEABLE_WORK_ORDER_STATUSES:
            raise InvalidStateTransitionError(
                "Service can only be recorded for in-progress or completed "
                "work orders."
            )

        assignment = await _get_accepted_assignment(
            session,
            work_order.id,
            technician_id,
        )
        if assignment is None:
            raise ForbiddenError(
                "The technician is not the accepted assignee for this work "
                "order."
            )
    elif not actor.is_admin:
        raise DomainValidationError(
            "Technician service records must reference a work order."
        )

    service_date = data.service_date or date.today()
    if service_date > date.today():
        raise DomainValidationError(
            "service_date must not be in the future."
        )

    record = ServiceRecord(
        equipment_id=equipment.id,
        work_order_id=data.work_order_id,
        technician_id=technician_id,
        service_date=service_date,
        work_performed=data.work_performed,
        findings=data.findings,
        parts_replaced=data.parts_replaced,
        recommendations=data.recommendations,
        completion_notes=data.completion_notes,
    )
    session.add(record)
    await flush(session)
    return record


async def get_service_record_for_actor(
    session: AsyncSession,
    service_record_id: uuid.UUID,
    actor: ActorContext,
) -> ServiceRecord:
    record = await session.get(ServiceRecord, service_record_id)
    if record is None:
        raise NotFoundError("Service record not found.")

    if actor.is_admin:
        return record
    if actor.is_technician:
        if record.technician_id != actor.technician_id:
            raise AccessDeniedError("Service record not found")
        return record
    if actor.is_customer:
        customer_id = await session.scalar(
            select(Equipment.customer_id).where(
                Equipment.id == record.equipment_id
            )
        )
        if customer_id != actor.customer_id:
            raise AccessDeniedError("Service record not found")
        return record

    raise AccessDeniedError("Service record not found")


async def _authorize_equipment_history(
    session: AsyncSession,
    equipment: Equipment,
    actor: ActorContext,
) -> None:
    if actor.is_admin:
        return
    if actor.is_customer:
        if equipment.customer_id != actor.customer_id:
            raise AccessDeniedError("Equipment not found")
        return
    if (
        actor.is_technician
        and actor.technician_id is not None
        and await technician_has_equipment_access(
            session,
            actor.technician_id,
            equipment.id,
        )
    ):
        return
    raise AccessDeniedError("Equipment not found")


async def list_equipment_service_records(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
) -> tuple[list[ServiceRecord], int]:
    equipment = await get_equipment_or_404(session, equipment_id)
    await _authorize_equipment_history(session, equipment, actor)

    conditions: list[Any] = [ServiceRecord.equipment_id == equipment.id]
    total = await session.scalar(
        select(func.count())
        .select_from(ServiceRecord)
        .where(*conditions)
    )
    items = (
        await session.scalars(
            select(ServiceRecord)
            .where(*conditions)
            .order_by(
                ServiceRecord.service_date.desc(),
                ServiceRecord.created_at.desc(),
                ServiceRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


async def list_technician_service_records(
    session: AsyncSession,
    technician_id: uuid.UUID,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
) -> tuple[list[ServiceRecord], int]:
    if actor.is_admin:
        pass
    elif actor.is_technician:
        if actor.technician_id != technician_id:
            raise AccessDeniedError("Technician not found")
    else:
        raise ForbiddenError(
            "You do not have permission to list technician service records."
        )

    conditions: list[Any] = [ServiceRecord.technician_id == technician_id]
    total = await session.scalar(
        select(func.count())
        .select_from(ServiceRecord)
        .where(*conditions)
    )
    items = (
        await session.scalars(
            select(ServiceRecord)
            .where(*conditions)
            .order_by(
                ServiceRecord.service_date.desc(),
                ServiceRecord.created_at.desc(),
                ServiceRecord.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


__all__ = [
    "SERVICEABLE_WORK_ORDER_STATUSES",
    "create_service_record",
    "get_service_record_for_actor",
    "list_equipment_service_records",
    "list_technician_service_records",
]

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    TechnicianAssignmentStatus,
    WorkOrderStatus,
)
from app.models.technician import Technician
from app.models.technician_assignment import TechnicianAssignment
from app.models.work_order import WorkOrder
from app.schemas.technician_assignment import (
    ReassignRequest,
    TechnicianAssignmentCreate,
)
from app.services.shared.access import require_admin, require_technician
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

ACTIVE_STATUSES = {
    TechnicianAssignmentStatus.OFFERED,
    TechnicianAssignmentStatus.ACCEPTED,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _get_work_order_for_update(
    session: AsyncSession,
    work_order_id: uuid.UUID,
) -> WorkOrder:
    work_order = (
        await session.execute(
            select(WorkOrder)
            .where(WorkOrder.id == work_order_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if work_order is None:
        raise NotFoundError("Work order not found.")
    return work_order


async def _validate_technician(
    session: AsyncSession,
    technician_id: uuid.UUID,
) -> Technician:
    technician = await session.get(Technician, technician_id)
    if technician is None:
        raise NotFoundError("Technician not found.")
    if not technician.is_active:
        raise ConflictError("The technician account is inactive.")
    if not technician.is_available:
        raise ConflictError("The technician is not currently available.")
    return technician


async def _get_active_assignment(
    session: AsyncSession,
    work_order_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> TechnicianAssignment | None:
    stmt = select(TechnicianAssignment).where(
        TechnicianAssignment.work_order_id == work_order_id,
        TechnicianAssignment.assignment_status.in_(ACTIVE_STATUSES),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_assignment(
    session: AsyncSession,
    actor: ActorContext,
    work_order_id: uuid.UUID,
    data: TechnicianAssignmentCreate,
) -> TechnicianAssignment:
    require_admin(actor)

    work_order = await _get_work_order_for_update(session, work_order_id)

    if work_order.status is not WorkOrderStatus.APPROVED:
        raise InvalidStateTransitionError(
            "Technicians can only be assigned to approved work orders."
        )

    await _validate_technician(session, data.technician_id)

    if await _get_active_assignment(session, work_order.id) is not None:
        raise ConflictError(
            "The work order already has an active assignment."
        )

    assignment = TechnicianAssignment(
        work_order_id=work_order.id,
        technician_id=data.technician_id,
        assignment_status=TechnicianAssignmentStatus.OFFERED,
        assignment_notes=data.assignment_notes,
        assigned_by_id=actor.user_id,
    )
    session.add(assignment)
    work_order.status = WorkOrderStatus.ASSIGNED

    await flush(session)
    return assignment


async def get_assignment_for_actor(
    session: AsyncSession,
    assignment_id: uuid.UUID,
    actor: ActorContext,
    *,
    for_update: bool = False,
) -> TechnicianAssignment:
    stmt = select(TechnicianAssignment).where(
        TechnicianAssignment.id == assignment_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    assignment = (await session.execute(stmt)).scalar_one_or_none()
    if assignment is None:
        raise NotFoundError("Assignment not found.")

    if actor.is_admin:
        return assignment
    if actor.is_technician:
        if assignment.technician_id != actor.technician_id:
            raise AccessDeniedError("Assignment not found")
        return assignment
    if actor.is_customer:
        customer_id = await session.scalar(
            select(WorkOrder.customer_id).where(
                WorkOrder.id == assignment.work_order_id
            )
        )
        if customer_id != actor.customer_id:
            raise AccessDeniedError("Assignment not found")
        return assignment

    raise AccessDeniedError("Assignment not found")


async def list_assignments(
    session: AsyncSession,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
    work_order_id: uuid.UUID | None = None,
    technician_id: uuid.UUID | None = None,
    status: TechnicianAssignmentStatus | None = None,
) -> tuple[list[TechnicianAssignment], int]:
    conditions: list[Any] = []

    if actor.is_admin:
        if work_order_id is not None:
            conditions.append(
                TechnicianAssignment.work_order_id == work_order_id
            )
        if technician_id is not None:
            conditions.append(
                TechnicianAssignment.technician_id == technician_id
            )
    elif actor.is_technician:
        conditions.append(
            TechnicianAssignment.technician_id == actor.technician_id
        )
        if work_order_id is not None:
            conditions.append(
                TechnicianAssignment.work_order_id == work_order_id
            )
    elif actor.is_customer:
        work_order_ids = select(WorkOrder.id).where(
            WorkOrder.customer_id == actor.customer_id
        )
        conditions.append(
            TechnicianAssignment.work_order_id.in_(work_order_ids)
        )
        if work_order_id is not None:
            conditions.append(
                TechnicianAssignment.work_order_id == work_order_id
            )
    else:
        raise ForbiddenError(
            "You do not have permission to list assignments."
        )

    if status is not None:
        conditions.append(TechnicianAssignment.assignment_status == status)

    total = await session.scalar(
        select(func.count())
        .select_from(TechnicianAssignment)
        .where(*conditions)
    )
    items = (
        await session.scalars(
            select(TechnicianAssignment)
            .where(*conditions)
            .order_by(
                TechnicianAssignment.assigned_at.desc(),
                TechnicianAssignment.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


async def accept_assignment(
    session: AsyncSession,
    assignment: TechnicianAssignment,
    actor: ActorContext,
) -> TechnicianAssignment:
    technician_id = require_technician(actor)
    if assignment.technician_id != technician_id:
        raise AccessDeniedError("Assignment not found")

    if assignment.assignment_status is not TechnicianAssignmentStatus.OFFERED:
        raise InvalidStateTransitionError(
            "Only offered assignments can be accepted."
        )

    work_order_status = await session.scalar(
        select(WorkOrder.status).where(WorkOrder.id == assignment.work_order_id)
    )
    if work_order_status is not WorkOrderStatus.ASSIGNED:
        raise InvalidStateTransitionError(
            "The work order is not in an assignable state."
        )

    assignment.assignment_status = TechnicianAssignmentStatus.ACCEPTED
    assignment.accepted_at = _utcnow()
    await flush(session)
    return assignment


async def reject_assignment(
    session: AsyncSession,
    assignment: TechnicianAssignment,
    actor: ActorContext,
    *,
    rejection_reason: str | None = None,
) -> TechnicianAssignment:
    technician_id = require_technician(actor)
    if assignment.technician_id != technician_id:
        raise AccessDeniedError("Assignment not found")

    if assignment.assignment_status is not TechnicianAssignmentStatus.OFFERED:
        raise InvalidStateTransitionError(
            "Only offered assignments can be rejected."
        )

    assignment.assignment_status = TechnicianAssignmentStatus.REJECTED
    assignment.rejected_at = _utcnow()
    if rejection_reason is not None:
        reason = rejection_reason.strip()
        assignment.rejection_reason = reason or None

    work_order = (
        await session.execute(
            select(WorkOrder)
            .where(WorkOrder.id == assignment.work_order_id)
            .with_for_update()
        )
    ).scalar_one()

    await flush(session)

    if work_order.status is WorkOrderStatus.ASSIGNED:
        remaining = await _get_active_assignment(session, work_order.id)
        if remaining is None:
            work_order.status = WorkOrderStatus.APPROVED
            await flush(session)

    return assignment


async def reassign_work_order(
    session: AsyncSession,
    actor: ActorContext,
    work_order_id: uuid.UUID,
    data: ReassignRequest,
) -> TechnicianAssignment:
    require_admin(actor)

    work_order = await _get_work_order_for_update(session, work_order_id)

    if work_order.status is not WorkOrderStatus.ASSIGNED:
        raise InvalidStateTransitionError(
            "Only assigned work orders can be reassigned."
        )

    previous = await _get_active_assignment(
        session,
        work_order.id,
        for_update=True,
    )
    if previous is None:
        raise ConflictError(
            "The work order has no active assignment to replace."
        )

    await _validate_technician(session, data.technician_id)

    if previous.technician_id == data.technician_id:
        raise DomainValidationError(
            "The work order is already assigned to this technician."
        )

    previous.assignment_status = TechnicianAssignmentStatus.WITHDRAWN
    await flush(session)

    replacement = TechnicianAssignment(
        work_order_id=work_order.id,
        technician_id=data.technician_id,
        assignment_status=TechnicianAssignmentStatus.OFFERED,
        assignment_notes=data.assignment_notes,
        assigned_by_id=actor.user_id,
    )
    session.add(replacement)
    await flush(session)
    return replacement


__all__ = [
    "accept_assignment",
    "create_assignment",
    "get_assignment_for_actor",
    "list_assignments",
    "reassign_work_order",
    "reject_assignment",
]

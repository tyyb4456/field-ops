from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.enums import (
    Priority,
    TechnicianAssignmentStatus,
    WorkOrderStatus,
)
from app.models.technician_assignment import TechnicianAssignment
from app.models.work_order import WorkOrder
from app.schemas.work_order import (
    WorkOrderComplete,
    WorkOrderCreate,
    WorkOrderUpdate,
)
from app.services.complaints.complaints import (
    WORK_ORDER_SOURCE_STATUSES,
    mark_converted_to_work_order,
)
from app.services.shared.access import (
    ensure_equipment_owned_by,
    require_admin,
    require_technician,
    technician_has_work_order_access,
)
from app.services.shared.actor import ActorContext
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import (
    ConflictError,
    DomainValidationError,
    DuplicateResourceError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.services.shared.transactions import flush

ACTIVE_ASSIGNMENT_STATUSES = {
    TechnicianAssignmentStatus.OFFERED,
    TechnicianAssignmentStatus.ACCEPTED,
}

OPEN_WORK_ORDER_STATUSES = {
    WorkOrderStatus.DRAFT,
    WorkOrderStatus.PENDING_APPROVAL,
    WorkOrderStatus.APPROVED,
    WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.IN_PROGRESS,
    WorkOrderStatus.ON_HOLD,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _generate_work_order_number() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:8].upper()
    return f"WO-{stamp}-{suffix}"


async def _find_active_assignment(
    session: AsyncSession,
    work_order_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> TechnicianAssignment | None:
    stmt = select(TechnicianAssignment).where(
        TechnicianAssignment.work_order_id == work_order_id,
        TechnicianAssignment.assignment_status.in_(ACTIVE_ASSIGNMENT_STATUSES),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _find_accepted_assignment(
    session: AsyncSession,
    work_order_id: uuid.UUID,
    technician_id: uuid.UUID | None,
) -> TechnicianAssignment | None:
    conditions = [
        TechnicianAssignment.work_order_id == work_order_id,
        TechnicianAssignment.assignment_status
        == TechnicianAssignmentStatus.ACCEPTED,
    ]
    if technician_id is not None:
        conditions.append(TechnicianAssignment.technician_id == technician_id)
    return (
        await session.execute(
            select(TechnicianAssignment)
            .where(*conditions)
            .order_by(TechnicianAssignment.assigned_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def create_work_order(
    session: AsyncSession,
    actor: ActorContext,
    data: WorkOrderCreate,
) -> WorkOrder:
    require_admin(actor)

    complaint = (
        await session.execute(
            select(Complaint)
            .where(Complaint.id == data.complaint_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if complaint is None:
        raise NotFoundError("Complaint not found.")

    if complaint.status not in WORK_ORDER_SOURCE_STATUSES:
        raise InvalidStateTransitionError(
            "A work order can only be created from an approved or "
            "under-investigation complaint."
        )

    if complaint.equipment_id is None:
        raise DomainValidationError(
            "The complaint must reference equipment before a work order "
            "can be created."
        )

    await ensure_equipment_owned_by(
        session,
        complaint.equipment_id,
        complaint.customer_id,
    )

    existing_work_order_id = await session.scalar(
        select(WorkOrder.id).where(WorkOrder.complaint_id == complaint.id)
    )
    if existing_work_order_id is not None:
        raise DuplicateResourceError(
            "A work order already exists for this complaint."
        )

    number = (
        data.work_order_number.strip()
        if data.work_order_number is not None
        else _generate_work_order_number()
    )
    if not number:
        raise DomainValidationError("work_order_number must not be blank.")

    existing_number = await session.scalar(
        select(WorkOrder.id).where(WorkOrder.work_order_number == number)
    )
    if existing_number is not None:
        raise DuplicateResourceError(
            "A work order with this number already exists."
        )

    work_order = WorkOrder(
        complaint_id=complaint.id,
        customer_id=complaint.customer_id,
        equipment_id=complaint.equipment_id,
        work_order_number=number,
        title=data.title,
        description=data.description,
        diagnostic_findings=data.diagnostic_findings,
        required_actions=data.required_actions,
        priority=data.priority,
        scheduled_date=data.scheduled_date,
        status=WorkOrderStatus.DRAFT,
    )
    session.add(work_order)
    mark_converted_to_work_order(complaint)

    await flush(session)
    return work_order


async def get_work_order_for_actor(
    session: AsyncSession,
    work_order_id: uuid.UUID,
    actor: ActorContext,
    *,
    for_update: bool = False,
) -> WorkOrder:
    stmt = select(WorkOrder).where(WorkOrder.id == work_order_id)
    if for_update:
        stmt = stmt.with_for_update()
    work_order = (await session.execute(stmt)).scalar_one_or_none()
    if work_order is None:
        raise NotFoundError("Work order not found.")

    if actor.is_admin:
        return work_order
    if actor.is_customer:
        if work_order.customer_id != actor.customer_id:
            raise AccessDeniedError("Work order not found")
        return work_order
    if (
        actor.is_technician
        and actor.technician_id is not None
        and await technician_has_work_order_access(
            session,
            actor.technician_id,
            work_order.id,
        )
    ):
        return work_order

    raise AccessDeniedError("Work order not found")


async def list_work_orders(
    session: AsyncSession,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
    customer_id: uuid.UUID | None = None,
    status: WorkOrderStatus | None = None,
    priority: Priority | None = None,
    equipment_id: uuid.UUID | None = None,
    complaint_id: uuid.UUID | None = None,
) -> tuple[list[WorkOrder], int]:
    conditions: list[Any] = []

    if actor.is_admin:
        if customer_id is not None:
            conditions.append(WorkOrder.customer_id == customer_id)
    elif actor.is_customer:
        conditions.append(WorkOrder.customer_id == actor.customer_id)
    elif actor.is_technician and actor.technician_id is not None:
        work_order_ids = select(TechnicianAssignment.work_order_id).where(
            TechnicianAssignment.technician_id == actor.technician_id
        )
        conditions.append(WorkOrder.id.in_(work_order_ids))
    else:
        raise ForbiddenError(
            "You do not have permission to list work orders."
        )

    if status is not None:
        conditions.append(WorkOrder.status == status)
    if priority is not None:
        conditions.append(WorkOrder.priority == priority)
    if equipment_id is not None:
        conditions.append(WorkOrder.equipment_id == equipment_id)
    if complaint_id is not None:
        conditions.append(WorkOrder.complaint_id == complaint_id)

    total = await session.scalar(
        select(func.count()).select_from(WorkOrder).where(*conditions)
    )
    items = (
        await session.scalars(
            select(WorkOrder)
            .where(*conditions)
            .order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


async def update_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
    data: WorkOrderUpdate,
) -> WorkOrder:
    require_admin(actor)

    if work_order.status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
        raise ConflictError(
            "Completed or cancelled work orders cannot be modified."
        )

    fields = data.model_fields_set
    if "title" in fields and data.title is not None:
        work_order.title = data.title
    if "description" in fields and data.description is not None:
        work_order.description = data.description
    if "diagnostic_findings" in fields:
        work_order.diagnostic_findings = data.diagnostic_findings
    if "required_actions" in fields and data.required_actions is not None:
        work_order.required_actions = data.required_actions
    if "priority" in fields and data.priority is not None:
        work_order.priority = data.priority
    if "scheduled_date" in fields:
        work_order.scheduled_date = data.scheduled_date

    await flush(session)
    return work_order


async def approve_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> WorkOrder:
    require_admin(actor)

    if work_order.status not in {
        WorkOrderStatus.DRAFT,
        WorkOrderStatus.PENDING_APPROVAL,
    }:
        raise InvalidStateTransitionError(
            "Only draft or pending-approval work orders can be approved."
        )

    work_order.status = WorkOrderStatus.APPROVED
    work_order.approved_by_id = actor.user_id
    work_order.approved_at = _utcnow()
    await flush(session)
    return work_order


async def cancel_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> WorkOrder:
    require_admin(actor)

    if work_order.status not in OPEN_WORK_ORDER_STATUSES:
        raise InvalidStateTransitionError(
            "Work order cannot be cancelled in its current state."
        )

    active_assignment = await _find_active_assignment(
        session,
        work_order.id,
        for_update=True,
    )
    if active_assignment is not None:
        active_assignment.assignment_status = TechnicianAssignmentStatus.WITHDRAWN

    work_order.status = WorkOrderStatus.CANCELLED
    await flush(session)
    return work_order


async def _require_technician_assignment(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> TechnicianAssignment:
    technician_id = require_technician(actor)
    assignment = await _find_accepted_assignment(
        session,
        work_order.id,
        technician_id,
    )
    if assignment is None:
        raise ForbiddenError(
            "You are not the accepted technician for this work order."
        )
    return assignment


async def start_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> WorkOrder:
    assignment = await _require_technician_assignment(
        session,
        work_order,
        actor,
    )

    if work_order.status is not WorkOrderStatus.ASSIGNED:
        raise InvalidStateTransitionError(
            "Only assigned work orders can be started."
        )

    work_order.status = WorkOrderStatus.IN_PROGRESS
    if assignment.started_at is None:
        assignment.started_at = _utcnow()
    await flush(session)
    return work_order


async def _authorize_work_execution(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> TechnicianAssignment | None:
    if actor.is_admin:
        assignment = await _find_accepted_assignment(
            session,
            work_order.id,
            None,
        )
        if assignment is None:
            raise ConflictError(
                "The work order has no accepted technician assignment."
            )
        return assignment
    if actor.is_technician:
        return await _require_technician_assignment(
            session,
            work_order,
            actor,
        )
    raise ForbiddenError(
        "You do not have permission to update work execution."
    )


async def hold_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> WorkOrder:
    await _authorize_work_execution(session, work_order, actor)

    if work_order.status is not WorkOrderStatus.IN_PROGRESS:
        raise InvalidStateTransitionError(
            "Only in-progress work orders can be placed on hold."
        )

    work_order.status = WorkOrderStatus.ON_HOLD
    await flush(session)
    return work_order


async def resume_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
) -> WorkOrder:
    await _authorize_work_execution(session, work_order, actor)

    if work_order.status is not WorkOrderStatus.ON_HOLD:
        raise InvalidStateTransitionError(
            "Only work orders on hold can be resumed."
        )

    work_order.status = WorkOrderStatus.IN_PROGRESS
    await flush(session)
    return work_order


async def complete_work_order(
    session: AsyncSession,
    work_order: WorkOrder,
    actor: ActorContext,
    data: WorkOrderComplete,
) -> WorkOrder:
    assignment = await _authorize_work_execution(
        session,
        work_order,
        actor,
    )

    if work_order.status is not WorkOrderStatus.IN_PROGRESS:
        raise InvalidStateTransitionError(
            "Only in-progress work orders can be completed."
        )

    summary = data.completion_summary.strip()
    if not summary:
        raise DomainValidationError("A completion summary is required.")

    completion_date = data.completion_date or date.today()
    if completion_date > date.today():
        raise DomainValidationError(
            "completion_date must not be in the future."
        )

    work_order.status = WorkOrderStatus.COMPLETED
    work_order.completion_date = completion_date
    work_order.completion_summary = summary
    if assignment is not None and assignment.completed_at is None:
        assignment.completed_at = _utcnow()

    await flush(session)
    return work_order


__all__ = [
    "ACTIVE_ASSIGNMENT_STATUSES",
    "OPEN_WORK_ORDER_STATUSES",
    "approve_work_order",
    "cancel_work_order",
    "complete_work_order",
    "create_work_order",
    "get_work_order_for_actor",
    "hold_work_order",
    "list_work_orders",
    "resume_work_order",
    "start_work_order",
    "update_work_order",
]

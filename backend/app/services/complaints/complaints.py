from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.customer import Customer
from app.models.enums import ComplaintStatus, Priority
from app.models.technician_assignment import TechnicianAssignment
from app.models.work_order import WorkOrder
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate
from app.services.shared.access import (
    ensure_conversation_owned_by,
    ensure_equipment_owned_by,
    require_admin,
    require_customer,
    technician_has_work_order_access,
)
from app.services.shared.actor import ActorContext
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from app.services.shared.transactions import flush

EDITABLE_STATUSES = {
    ComplaintStatus.DRAFT,
    ComplaintStatus.SUBMITTED,
    ComplaintStatus.PENDING_APPROVAL,
}

REVIEWABLE_STATUSES = {
    ComplaintStatus.SUBMITTED,
    ComplaintStatus.PENDING_APPROVAL,
}

WORK_ORDER_SOURCE_STATUSES = {
    ComplaintStatus.APPROVED,
    ComplaintStatus.UNDER_INVESTIGATION,
}

CANCELLABLE_STATUSES = {
    ComplaintStatus.DRAFT,
    ComplaintStatus.SUBMITTED,
    ComplaintStatus.PENDING_APPROVAL,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_customer_priority_allowed(
    actor: ActorContext,
    priority: Priority,
) -> None:
    if actor.is_customer and priority is Priority.URGENT:
        raise ForbiddenError(
            "Only administrators may set urgent priority."
        )


async def _resolve_customer_id(
    session: AsyncSession,
    actor: ActorContext,
    requested_customer_id: uuid.UUID | None,
) -> uuid.UUID:
    if actor.is_admin:
        if requested_customer_id is None:
            raise DomainValidationError(
                "customer_id is required when an administrator files a "
                "complaint."
            )
        customer = await session.get(Customer, requested_customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        return customer.id

    customer_id = require_customer(actor)
    if requested_customer_id is not None and requested_customer_id != customer_id:
        raise ForbiddenError(
            "You cannot file a complaint for another customer."
        )
    return customer_id


async def _technician_can_access_complaint(
    session: AsyncSession,
    actor: ActorContext,
    complaint: Complaint,
) -> bool:
    if actor.technician_id is None:
        return False
    work_order_id = await session.scalar(
        select(WorkOrder.id).where(WorkOrder.complaint_id == complaint.id)
    )
    if work_order_id is None:
        return False
    return await technician_has_work_order_access(
        session,
        actor.technician_id,
        work_order_id,
    )


async def _authorize_complaint(
    session: AsyncSession,
    actor: ActorContext,
    complaint: Complaint,
) -> None:
    if actor.is_admin:
        return
    if actor.is_customer:
        if complaint.customer_id != actor.customer_id:
            raise AccessDeniedError("Complaint not found")
        return
    if await _technician_can_access_complaint(session, actor, complaint):
        return
    raise AccessDeniedError("Complaint not found")


async def get_complaint_for_actor(
    session: AsyncSession,
    complaint_id: uuid.UUID,
    actor: ActorContext,
    *,
    for_update: bool = False,
) -> Complaint:
    stmt = select(Complaint).where(Complaint.id == complaint_id)
    if for_update:
        stmt = stmt.with_for_update()
    complaint = (await session.execute(stmt)).scalar_one_or_none()
    if complaint is None:
        raise NotFoundError("Complaint not found.")
    await _authorize_complaint(session, actor, complaint)
    return complaint


async def create_complaint(
    session: AsyncSession,
    actor: ActorContext,
    data: ComplaintCreate,
) -> Complaint:
    customer_id = await _resolve_customer_id(
        session,
        actor,
        data.customer_id,
    )
    _ensure_customer_priority_allowed(actor, data.priority)

    if data.equipment_id is not None:
        await ensure_equipment_owned_by(
            session,
            data.equipment_id,
            customer_id,
        )

    if data.origin_conversation_id is not None:
        await ensure_conversation_owned_by(
            session,
            data.origin_conversation_id,
            customer_id,
        )

    complaint = Complaint(
        customer_id=customer_id,
        equipment_id=data.equipment_id,
        origin_conversation_id=data.origin_conversation_id,
        description=data.description,
        reported_symptoms=data.reported_symptoms,
        reported_error_code=data.reported_error_code,
        channel=data.channel,
        priority=data.priority,
        status=ComplaintStatus.DRAFT,
    )
    session.add(complaint)
    await flush(session)
    return complaint


async def list_complaints(
    session: AsyncSession,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
    customer_id: uuid.UUID | None = None,
    status: ComplaintStatus | None = None,
    priority: Priority | None = None,
    equipment_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> tuple[list[Complaint], int]:
    conditions: list[Any] = []

    if actor.is_admin:
        if customer_id is not None:
            conditions.append(Complaint.customer_id == customer_id)
    elif actor.is_customer:
        conditions.append(Complaint.customer_id == actor.customer_id)
    elif actor.is_technician and actor.technician_id is not None:
        complaint_ids = (
            select(WorkOrder.complaint_id)
            .join(
                TechnicianAssignment,
                TechnicianAssignment.work_order_id == WorkOrder.id,
            )
            .where(TechnicianAssignment.technician_id == actor.technician_id)
        )
        conditions.append(Complaint.id.in_(complaint_ids))
    else:
        raise ForbiddenError(
            "You do not have permission to list complaints."
        )

    if status is not None:
        conditions.append(Complaint.status == status)
    if priority is not None:
        conditions.append(Complaint.priority == priority)
    if equipment_id is not None:
        conditions.append(Complaint.equipment_id == equipment_id)
    if created_from is not None:
        conditions.append(Complaint.created_at >= created_from)
    if created_to is not None:
        conditions.append(Complaint.created_at <= created_to)

    total = await session.scalar(
        select(func.count()).select_from(Complaint).where(*conditions)
    )
    items = (
        await session.scalars(
            select(Complaint)
            .where(*conditions)
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


async def update_complaint(
    session: AsyncSession,
    complaint: Complaint,
    actor: ActorContext,
    data: ComplaintUpdate,
) -> Complaint:
    await _authorize_complaint(session, actor, complaint)

    if actor.is_technician:
        raise ForbiddenError(
            "Technicians cannot modify complaints."
        )

    if complaint.status not in EDITABLE_STATUSES:
        raise ConflictError(
            "Complaint cannot be modified in its current state."
        )

    fields = data.model_fields_set

    if "equipment_id" in fields and data.equipment_id is not None:
        await ensure_equipment_owned_by(
            session,
            data.equipment_id,
            complaint.customer_id,
        )

    if "priority" in fields and data.priority is not None:
        _ensure_customer_priority_allowed(actor, data.priority)

    if "equipment_id" in fields:
        complaint.equipment_id = data.equipment_id
    if "description" in fields and data.description is not None:
        complaint.description = data.description
    if "reported_symptoms" in fields and data.reported_symptoms is not None:
        complaint.reported_symptoms = data.reported_symptoms
    if "reported_error_code" in fields:
        complaint.reported_error_code = data.reported_error_code
    if "priority" in fields and data.priority is not None:
        complaint.priority = data.priority

    await flush(session)
    return complaint


async def submit_complaint(
    session: AsyncSession,
    complaint: Complaint,
    actor: ActorContext,
) -> Complaint:
    await _authorize_complaint(session, actor, complaint)
    if actor.is_technician:
        raise ForbiddenError("Technicians cannot submit complaints.")

    if complaint.status not in {
        ComplaintStatus.DRAFT,
        ComplaintStatus.SUBMITTED,
    }:
        raise ConflictError(
            "Only draft or submitted complaints can be submitted for review."
        )

    complaint.status = ComplaintStatus.PENDING_APPROVAL
    if complaint.submitted_at is None:
        complaint.submitted_at = _utcnow()
    await flush(session)
    return complaint


async def approve_complaint(
    session: AsyncSession,
    complaint: Complaint,
    actor: ActorContext,
    *,
    notes: str | None = None,
) -> Complaint:
    require_admin(actor)

    if complaint.status not in REVIEWABLE_STATUSES:
        raise ConflictError(
            "Only complaints awaiting review can be approved."
        )

    complaint.status = ComplaintStatus.APPROVED
    complaint.approved_by_id = actor.user_id
    complaint.approved_at = _utcnow()
    complaint.approval_notes = notes
    complaint.rejection_reason = None
    await flush(session)
    return complaint


async def reject_complaint(
    session: AsyncSession,
    complaint: Complaint,
    actor: ActorContext,
    *,
    rejection_reason: str,
) -> Complaint:
    require_admin(actor)

    reason = rejection_reason.strip()
    if not reason:
        raise DomainValidationError("A rejection reason is required.")

    if complaint.status not in REVIEWABLE_STATUSES:
        raise ConflictError(
            "Only complaints awaiting review can be rejected."
        )

    complaint.status = ComplaintStatus.REJECTED
    complaint.rejection_reason = reason
    complaint.approval_notes = None
    complaint.approved_by_id = actor.user_id
    complaint.approved_at = _utcnow()
    await flush(session)
    return complaint


async def start_investigation(
    session: AsyncSession,
    complaint: Complaint,
    actor: ActorContext,
) -> Complaint:
    require_admin(actor)

    if complaint.status is not ComplaintStatus.APPROVED:
        raise ConflictError(
            "Only approved complaints can enter investigation."
        )

    complaint.status = ComplaintStatus.UNDER_INVESTIGATION
    await flush(session)
    return complaint


async def cancel_complaint(
    session: AsyncSession,
    complaint: Complaint,
    actor: ActorContext,
) -> Complaint:
    await _authorize_complaint(session, actor, complaint)
    if actor.is_technician:
        raise ForbiddenError("Technicians cannot cancel complaints.")

    if complaint.status not in CANCELLABLE_STATUSES:
        raise ConflictError(
            "Complaint cannot be cancelled in its current state."
        )

    complaint.status = ComplaintStatus.CANCELLED
    complaint.closed_at = _utcnow()
    await flush(session)
    return complaint


def mark_converted_to_work_order(complaint: Complaint) -> None:
    """Internal transition applied when a work order is created."""
    if complaint.status not in WORK_ORDER_SOURCE_STATUSES:
        raise ConflictError(
            "Only approved or under-investigation complaints can be "
            "converted to a work order."
        )
    complaint.status = ComplaintStatus.CONVERTED_TO_WORK_ORDER


__all__ = [
    "CANCELLABLE_STATUSES",
    "EDITABLE_STATUSES",
    "REVIEWABLE_STATUSES",
    "WORK_ORDER_SOURCE_STATUSES",
    "approve_complaint",
    "cancel_complaint",
    "create_complaint",
    "get_complaint_for_actor",
    "list_complaints",
    "mark_converted_to_work_order",
    "reject_complaint",
    "start_investigation",
    "submit_complaint",
    "update_complaint",
]

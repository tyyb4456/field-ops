from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.equipment import Equipment
from app.models.technician_assignment import TechnicianAssignment
from app.models.work_order import WorkOrder
from app.services.shared.actor import ActorContext
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import ForbiddenError, NotFoundError

ACTIVE_ASSIGNMENT_STATUSES = ("offered", "accepted")


def require_admin(actor: ActorContext) -> None:
    if not actor.is_admin:
        raise ForbiddenError(
            "You do not have permission to perform this action."
        )


def require_customer(actor: ActorContext) -> uuid.UUID:
    if not actor.is_customer or actor.customer_id is None:
        raise ForbiddenError(
            "This operation requires a customer account."
        )
    return actor.customer_id


def require_technician(actor: ActorContext) -> uuid.UUID:
    if not actor.is_technician or actor.technician_id is None:
        raise ForbiddenError(
            "This operation requires a technician account."
        )
    return actor.technician_id


async def get_equipment_or_404(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Equipment:
    stmt = select(Equipment).where(Equipment.id == equipment_id)
    if for_update:
        stmt = stmt.with_for_update()
    equipment = (await session.execute(stmt)).scalar_one_or_none()
    if equipment is None:
        raise NotFoundError("Equipment not found.")
    return equipment


async def ensure_equipment_owned_by(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> Equipment:
    equipment = await get_equipment_or_404(session, equipment_id)
    if equipment.customer_id != customer_id:
        raise AccessDeniedError("Equipment not found")
    return equipment


async def get_conversation_or_404(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Conversation:
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    if for_update:
        stmt = stmt.with_for_update()
    conversation = (await session.execute(stmt)).scalar_one_or_none()
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    return conversation


async def ensure_conversation_owned_by(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> Conversation:
    conversation = await get_conversation_or_404(session, conversation_id)
    if conversation.customer_id != customer_id:
        raise AccessDeniedError("Conversation not found")
    return conversation


async def technician_has_work_order_access(
    session: AsyncSession,
    technician_id: uuid.UUID,
    work_order_id: uuid.UUID,
) -> bool:
    assignment_id = await session.scalar(
        select(TechnicianAssignment.id)
        .where(
            TechnicianAssignment.technician_id == technician_id,
            TechnicianAssignment.work_order_id == work_order_id,
        )
        .limit(1)
    )
    return assignment_id is not None


async def technician_has_equipment_access(
    session: AsyncSession,
    technician_id: uuid.UUID,
    equipment_id: uuid.UUID,
) -> bool:
    assignment_id = await session.scalar(
        select(TechnicianAssignment.id)
        .join(
            WorkOrder,
            WorkOrder.id == TechnicianAssignment.work_order_id,
        )
        .where(
            TechnicianAssignment.technician_id == technician_id,
            WorkOrder.equipment_id == equipment_id,
        )
        .limit(1)
    )
    return assignment_id is not None


async def technician_has_conversation_access(
    session: AsyncSession,
    technician_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    assignment_id = await session.scalar(
        select(TechnicianAssignment.id)
        .join(
            WorkOrder,
            WorkOrder.id == TechnicianAssignment.work_order_id,
        )
        .join(
            Complaint,
            Complaint.id == WorkOrder.complaint_id,
        )
        .where(
            TechnicianAssignment.technician_id == technician_id,
            Complaint.origin_conversation_id == conversation_id,
        )
        .limit(1)
    )
    return assignment_id is not None


__all__ = [
    "ACTIVE_ASSIGNMENT_STATUSES",
    "ensure_conversation_owned_by",
    "ensure_equipment_owned_by",
    "get_conversation_or_404",
    "get_equipment_or_404",
    "require_admin",
    "require_customer",
    "require_technician",
    "technician_has_conversation_access",
    "technician_has_equipment_access",
    "technician_has_work_order_access",
]

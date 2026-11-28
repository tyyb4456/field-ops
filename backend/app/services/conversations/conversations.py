from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.enums import (
    ConversationStatus,
    MessageSenderType,
)
from app.models.message import Message
from app.models.technician_assignment import TechnicianAssignment
from app.models.work_order import WorkOrder
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.schemas.message import MessageCreate
from app.services.shared.access import (
    get_conversation_or_404,
    require_customer,
    technician_has_conversation_access,
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

_STATUS_TRANSITIONS: dict[ConversationStatus, set[ConversationStatus]] = {
    ConversationStatus.ACTIVE: {
        ConversationStatus.AWAITING_CUSTOMER,
        ConversationStatus.CLOSED,
        ConversationStatus.ARCHIVED,
    },
    ConversationStatus.AWAITING_CUSTOMER: {
        ConversationStatus.ACTIVE,
        ConversationStatus.CLOSED,
        ConversationStatus.ARCHIVED,
    },
    ConversationStatus.CLOSED: {ConversationStatus.ARCHIVED},
    ConversationStatus.ARCHIVED: set(),
}

_TERMINAL_STATUSES = {
    ConversationStatus.CLOSED,
    ConversationStatus.ARCHIVED,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _resolve_customer_id(
    session: AsyncSession,
    actor: ActorContext,
    requested_customer_id: uuid.UUID | None,
) -> uuid.UUID:
    if actor.is_admin:
        if requested_customer_id is None:
            raise DomainValidationError(
                "customer_id is required when an administrator creates a "
                "conversation."
            )
        customer = await session.get(Customer, requested_customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        return customer.id

    customer_id = require_customer(actor)
    if requested_customer_id is not None and requested_customer_id != customer_id:
        raise ForbiddenError(
            "You cannot create a conversation for another customer."
        )
    return customer_id


async def create_conversation(
    session: AsyncSession,
    actor: ActorContext,
    data: ConversationCreate,
) -> Conversation:
    customer_id = await _resolve_customer_id(
        session,
        actor,
        data.customer_id,
    )
    now = _utcnow()
    conversation = Conversation(
        customer_id=customer_id,
        channel=data.channel,
        external_conversation_id=data.external_conversation_id,
        started_at=now,
        last_activity_at=now,
        conversation_metadata=data.conversation_metadata,
    )
    session.add(conversation)
    await flush(session)
    return conversation


async def get_conversation_for_actor(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    actor: ActorContext,
    *,
    for_update: bool = False,
) -> Conversation:
    conversation = await get_conversation_or_404(
        session,
        conversation_id,
        for_update=for_update,
    )

    if actor.is_admin:
        return conversation
    if actor.is_customer:
        if conversation.customer_id != actor.customer_id:
            raise AccessDeniedError("Conversation not found")
        return conversation
    if (
        actor.is_technician
        and actor.technician_id is not None
        and await technician_has_conversation_access(
            session,
            actor.technician_id,
            conversation.id,
        )
    ):
        return conversation

    raise AccessDeniedError("Conversation not found")


async def list_conversations(
    session: AsyncSession,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
    customer_id: uuid.UUID | None = None,
    status: ConversationStatus | None = None,
) -> tuple[list[Conversation], int]:
    conditions: list[Any] = []

    if actor.is_admin:
        if customer_id is not None:
            conditions.append(Conversation.customer_id == customer_id)
    elif actor.is_customer:
        conditions.append(Conversation.customer_id == actor.customer_id)
    elif actor.is_technician and actor.technician_id is not None:
        conversation_ids = (
            select(Complaint.origin_conversation_id)
            .join(WorkOrder, WorkOrder.complaint_id == Complaint.id)
            .join(
                TechnicianAssignment,
                TechnicianAssignment.work_order_id == WorkOrder.id,
            )
            .where(
                TechnicianAssignment.technician_id == actor.technician_id,
                Complaint.origin_conversation_id.is_not(None),
            )
        )
        conditions.append(Conversation.id.in_(conversation_ids))
    else:
        raise ForbiddenError(
            "You do not have permission to list conversations."
        )

    if status is not None:
        conditions.append(Conversation.status == status)

    total = await session.scalar(
        select(func.count()).select_from(Conversation).where(*conditions)
    )
    items = (
        await session.scalars(
            select(Conversation)
            .where(*conditions)
            .order_by(
                Conversation.last_activity_at.desc(),
                Conversation.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


def _apply_status_transition(
    conversation: Conversation,
    new_status: ConversationStatus,
    actor: ActorContext,
) -> None:
    if new_status is conversation.status:
        return

    allowed = _STATUS_TRANSITIONS[conversation.status]
    if new_status not in allowed:
        raise ConflictError("Invalid conversation status transition.")

    if actor.is_customer and new_status is not ConversationStatus.CLOSED:
        raise ForbiddenError(
            "Customers may only close their own conversations."
        )

    conversation.status = new_status
    now = _utcnow()
    conversation.last_activity_at = now
    if new_status is ConversationStatus.CLOSED and conversation.closed_at is None:
        conversation.closed_at = now


async def update_conversation(
    session: AsyncSession,
    conversation: Conversation,
    actor: ActorContext,
    data: ConversationUpdate,
) -> Conversation:
    if not actor.is_admin and (
        not actor.is_customer or conversation.customer_id != actor.customer_id
    ):
        raise AccessDeniedError("Conversation not found")

    if data.status is not None:
        _apply_status_transition(conversation, data.status, actor)

    if data.conversation_metadata is not None:
        conversation.conversation_metadata = data.conversation_metadata

    await flush(session)
    return conversation


async def close_conversation(
    session: AsyncSession,
    conversation: Conversation,
    actor: ActorContext,
) -> Conversation:
    return await update_conversation(
        session,
        conversation,
        actor,
        ConversationUpdate(status=ConversationStatus.CLOSED),
    )


def _resolve_sender(
    actor: ActorContext,
    requested_sender: MessageSenderType,
) -> tuple[MessageSenderType, uuid.UUID | None]:
    if actor.is_customer:
        if requested_sender is not MessageSenderType.CUSTOMER:
            raise ForbiddenError(
                "Customers may only send customer messages."
            )
        return MessageSenderType.CUSTOMER, actor.user_id

    if actor.is_admin:
        if requested_sender is MessageSenderType.ADMIN:
            return MessageSenderType.ADMIN, actor.user_id
        if requested_sender is MessageSenderType.SYSTEM:
            return MessageSenderType.SYSTEM, None
        raise ForbiddenError(
            "Administrators may send admin or system messages only."
        )

    if actor.is_technician:
        if requested_sender is not MessageSenderType.TECHNICIAN:
            raise ForbiddenError(
                "Technicians may only send technician messages."
            )
        return MessageSenderType.TECHNICIAN, actor.user_id

    raise ForbiddenError("You do not have permission to send messages.")


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    actor: ActorContext,
    data: MessageCreate,
) -> Message:
    if conversation.status in _TERMINAL_STATUSES:
        raise ConflictError(
            "Messages cannot be added to a closed conversation."
        )

    sender_type, sender_user_id = _resolve_sender(actor, data.sender_type)

    if sender_type is MessageSenderType.TECHNICIAN and (
        actor.technician_id is None
        or not await technician_has_conversation_access(
            session,
            actor.technician_id,
            conversation.id,
        )
    ):
        raise AccessDeniedError("Conversation not found")

    message = Message(
        conversation_id=conversation.id,
        sender_type=sender_type,
        sender_user_id=sender_user_id,
        content=data.content,
        message_type=data.message_type,
        external_message_id=data.external_message_id,
        channel_metadata=data.channel_metadata,
        message_metadata=data.message_metadata,
    )
    session.add(message)

    now = _utcnow()
    conversation.last_activity_at = now
    if (
        sender_type is MessageSenderType.CUSTOMER
        and conversation.status is ConversationStatus.AWAITING_CUSTOMER
    ):
        conversation.status = ConversationStatus.ACTIVE
    elif (
        sender_type is MessageSenderType.ADMIN
        and conversation.status is ConversationStatus.ACTIVE
    ):
        conversation.status = ConversationStatus.AWAITING_CUSTOMER

    await flush(session)
    return message


async def list_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Message], int]:
    total = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id)
    )
    items = (
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


__all__ = [
    "add_message",
    "close_conversation",
    "create_conversation",
    "get_conversation_for_actor",
    "list_conversations",
    "list_messages",
    "update_conversation",
]

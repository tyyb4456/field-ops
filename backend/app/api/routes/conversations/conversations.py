from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.db.session import get_db_session
from app.models.enums import ConversationStatus
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
)
from app.schemas.message import (
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from app.services.conversations import conversations as conversation_service
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.shared.transactions import commit

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
async def create_conversation(
    payload: ConversationCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    conversation = await conversation_service.create_conversation(
        session,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List conversations",
)
async def list_conversations(
    customer_id: uuid.UUID | None = Query(default=None),
    conversation_status: ConversationStatus | None = Query(
        default=None,
        alias="status",
    ),
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await conversation_service.list_conversations(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
        customer_id=customer_id,
        status=conversation_status,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Retrieve a conversation",
)
async def read_conversation(
    conversation_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    conversation = await conversation_service.get_conversation_for_actor(
        session,
        conversation_id,
        actor,
    )
    return ConversationResponse.model_validate(conversation)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation status or metadata",
)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    conversation = await conversation_service.get_conversation_for_actor(
        session,
        conversation_id,
        actor,
        for_update=True,
    )
    updated = await conversation_service.update_conversation(
        session,
        conversation,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(updated)
    return ConversationResponse.model_validate(updated)


@router.post(
    "/{conversation_id}/close",
    response_model=ConversationResponse,
    summary="Close a conversation",
)
async def close_conversation(
    conversation_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    conversation = await conversation_service.get_conversation_for_actor(
        session,
        conversation_id,
        actor,
        for_update=True,
    )
    closed = await conversation_service.close_conversation(
        session,
        conversation,
        actor,
    )
    await commit(session)
    await session.refresh(closed)
    return ConversationResponse.model_validate(closed)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a message to a conversation",
)
async def add_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    conversation = await conversation_service.get_conversation_for_actor(
        session,
        conversation_id,
        actor,
        for_update=True,
    )
    message = await conversation_service.add_message(
        session,
        conversation,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(message)
    return MessageResponse.model_validate(message)


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List conversation messages in order",
)
async def list_messages(
    conversation_id: uuid.UUID,
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    await conversation_service.get_conversation_for_actor(
        session,
        conversation_id,
        actor,
    )
    items, total = await conversation_service.list_messages(
        session,
        conversation_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }

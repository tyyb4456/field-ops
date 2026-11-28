from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import MessageSenderType, MessageType
from app.schemas.common import ORMModel, StrictRequest


class MessageCreate(StrictRequest):
    conversation_id: uuid.UUID
    sender_type: MessageSenderType
    sender_user_id: uuid.UUID | None = None
    content: str | None = None
    message_type: MessageType = MessageType.TEXT
    external_message_id: str | None = Field(default=None, max_length=255)
    channel_metadata: dict[str, Any] = Field(default_factory=dict)
    message_metadata: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(ORMModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: MessageSenderType
    sender_user_id: uuid.UUID | None = None
    content: str | None = None
    message_type: MessageType
    external_message_id: str | None = None
    channel_metadata: dict[str, Any]
    message_metadata: dict[str, Any]
    created_at: datetime

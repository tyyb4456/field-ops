from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.models.enums import MessageSenderType, MessageType
from app.schemas.common import ORMModel, StrictRequest


class MessageCreate(StrictRequest):
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Ignored on nested routes; the path conversation is used.",
    )
    sender_type: MessageSenderType
    sender_user_id: uuid.UUID | None = Field(
        default=None,
        description="Ignored; the authenticated sender is always used.",
    )
    content: str | None = Field(default=None, max_length=20_000)
    message_type: MessageType = MessageType.TEXT
    external_message_id: str | None = Field(default=None, max_length=255)
    channel_metadata: dict[str, Any] = Field(default_factory=dict)
    message_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_payload(self) -> MessageCreate:
        has_content = bool(self.content and self.content.strip())
        has_metadata = bool(self.channel_metadata)
        if self.message_type is MessageType.TEXT and not has_content:
            raise ValueError("Text messages require content")
        if not has_content and not has_metadata:
            raise ValueError("A message requires content or channel metadata")
        return self


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


class MessageListResponse(ORMModel):
    items: list[MessageResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "MessageCreate",
    "MessageListResponse",
    "MessageResponse",
]

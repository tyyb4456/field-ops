from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import Channel, ConversationStatus
from app.schemas.common import ORMModel, StrictRequest


class ConversationCreate(StrictRequest):
    customer_id: uuid.UUID
    channel: Channel = Channel.WEB
    conversation_metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdate(StrictRequest):
    status: ConversationStatus | None = None
    last_activity_at: datetime | None = None
    closed_at: datetime | None = None
    conversation_metadata: dict[str, Any] | None = None


class ConversationResponse(ORMModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    status: ConversationStatus
    channel: Channel
    external_conversation_id: str | None = None
    started_at: datetime
    last_activity_at: datetime
    closed_at: datetime | None = None
    conversation_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

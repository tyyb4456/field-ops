from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import Enum as SQLEnum


class UserRole(str, PyEnum):
    CUSTOMER = "customer"
    TECHNICIAN = "technician"
    ADMIN = "admin"


class Priority(str, PyEnum):
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ComplaintChannel(str, PyEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"


class ComplaintStatus(str, PyEnum):
    RECEIVED = "received"
    ANALYZING = "analyzing"
    AWAITING_CUSTOMER = "awaiting_customer"
    READY_FOR_WORK_ORDER = "ready_for_work_order"
    CONVERTED = "converted"
    ESCALATED = "escalated"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ConversationStatus(str, PyEnum):
    ACTIVE = "active"
    AWAITING_CUSTOMER = "awaiting_customer"
    AWAITING_INVESTIGATION_APPROVAL = "awaiting_investigation_approval"
    INVESTIGATING = "investigating"
    AWAITING_ASSIGNMENT_APPROVAL = "awaiting_assignment_approval"
    CONVERTED = "converted"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MessageSenderType(str, PyEnum):
    CUSTOMER = "customer"
    ASSISTANT = "assistant"
    STAFF = "staff"


class MediaType(str, PyEnum):
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"


def enum_type(
    enum_cls: type[PyEnum],
    name: str,
    length: int = 40,
) -> SQLEnum:
    return SQLEnum(
        enum_cls,
        name=name,
        length=length,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum: [member.value for member in enum],
    )


__all__ = [
    ...
]

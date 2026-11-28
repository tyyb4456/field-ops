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


class Channel(str, PyEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"


class ComplaintStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDER_INVESTIGATION = "under_investigation"
    CONVERTED_TO_WORK_ORDER = "converted_to_work_order"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class WorkOrderStatus(str, PyEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ConversationStatus(str, PyEnum):
    ACTIVE = "active"
    AWAITING_CUSTOMER = "awaiting_customer"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MessageSenderType(str, PyEnum):
    CUSTOMER = "customer"
    AI_AGENT = "ai_agent"
    ADMIN = "admin"
    TECHNICIAN = "technician"
    SYSTEM = "system"


class MessageType(str, PyEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"


class TechnicianAssignmentStatus(str, PyEnum):
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class EquipmentOperationalStatus(str, PyEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    DECOMMISSIONED = "decommissioned"


class EquipmentDocumentType(str, PyEnum):
    MANUAL = "manual"
    DATASHEET = "datasheet"
    INSTALLATION_GUIDE = "installation_guide"
    TROUBLESHOOTING_GUIDE = "troubleshooting_guide"
    WARRANTY = "warranty"
    OTHER = "other"


class DocumentProcessingStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


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
    "Channel",
    "ComplaintStatus",
    "ConversationStatus",
    "DocumentProcessingStatus",
    "EquipmentDocumentType",
    "EquipmentOperationalStatus",
    "MessageSenderType",
    "MessageType",
    "Priority",
    "TechnicianAssignmentStatus",
    "UserRole",
    "WorkOrderStatus",
    "enum_type",
]

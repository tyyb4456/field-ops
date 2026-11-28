from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401 - registers all model classes
from app.db.base import Base
from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.enums import (
    Channel,
    ComplaintStatus,
    ConversationStatus,
    DocumentProcessingStatus,
    EquipmentDocumentType,
    EquipmentOperationalStatus,
    MessageSenderType,
    MessageType,
    Priority,
    TechnicianAssignmentStatus,
    UserRole,
    WorkOrderStatus,
)
from app.models.equipment import Equipment
from app.models.message import Message
from app.models.service_record import ServiceRecord
from app.models.technician_assignment import TechnicianAssignment
from app.models.user import User
from app.models.work_order import WorkOrder

EXPECTED_TABLES = {
    "users",
    "customers",
    "technicians",
    "equipment",
    "conversations",
    "complaints",
    "messages",
    "work_orders",
    "technician_assignments",
    "service_records",
    "equipment_documents",
}


def test_all_models_register_expected_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_sqlalchemy_mappers_configure_successfully() -> None:
    configure_mappers()


def test_enum_values_are_stable() -> None:
    assert {role.value for role in UserRole} == {
        "customer",
        "technician",
        "admin",
    }
    assert {priority.value for priority in Priority} == {
        "normal",
        "high",
        "urgent",
    }
    assert {channel.value for channel in Channel} == {"web", "whatsapp"}
    assert {status.value for status in ComplaintStatus} == {
        "draft",
        "submitted",
        "pending_approval",
        "approved",
        "rejected",
        "under_investigation",
        "converted_to_work_order",
        "closed",
        "cancelled",
    }
    assert {status.value for status in WorkOrderStatus} == {
        "draft",
        "pending_approval",
        "approved",
        "assigned",
        "in_progress",
        "on_hold",
        "completed",
        "cancelled",
    }
    assert {status.value for status in ConversationStatus} == {
        "active",
        "awaiting_customer",
        "closed",
        "archived",
    }
    assert {sender.value for sender in MessageSenderType} == {
        "customer",
        "ai_agent",
        "admin",
        "technician",
        "system",
    }
    assert {message_type.value for message_type in MessageType} == {
        "text",
        "image",
        "audio",
        "file",
    }
    assert {status.value for status in TechnicianAssignmentStatus} == {
        "offered",
        "accepted",
        "rejected",
        "withdrawn",
        "expired",
    }
    assert {status.value for status in EquipmentOperationalStatus} == {
        "active",
        "degraded",
        "offline",
        "decommissioned",
    }
    assert {document_type.value for document_type in EquipmentDocumentType} == {
        "manual",
        "datasheet",
        "installation_guide",
        "troubleshooting_guide",
        "warranty",
        "other",
    }
    assert {status.value for status in DocumentProcessingStatus} == {
        "pending",
        "processing",
        "ready",
        "failed",
    }


def test_relationship_cardinalities() -> None:
    assert not User.customer.property.uselist
    assert not User.technician.property.uselist
    assert Customer.equipment.property.uselist
    assert Customer.conversations.property.uselist
    assert Customer.complaints.property.uselist
    assert Customer.work_orders.property.uselist
    assert Conversation.messages.property.uselist
    assert Conversation.complaints.property.uselist
    assert Complaint.work_order.property.uselist is False
    assert WorkOrder.assignments.property.uselist
    assert WorkOrder.service_records.property.uselist
    assert Equipment.complaints.property.uselist
    assert Equipment.service_records.property.uselist
    assert Equipment.documents.property.uselist


def test_nullable_relationships() -> None:
    complaint_columns = inspect(Complaint).columns
    assert complaint_columns["equipment_id"].nullable is True
    assert complaint_columns["origin_conversation_id"].nullable is True
    assert complaint_columns["approved_by_id"].nullable is True

    work_order_columns = inspect(WorkOrder).columns
    assert work_order_columns["equipment_id"].nullable is False
    assert work_order_columns["customer_id"].nullable is False
    assert work_order_columns["complaint_id"].nullable is False

    service_record_columns = inspect(ServiceRecord).columns
    assert service_record_columns["work_order_id"].nullable is True
    assert service_record_columns["equipment_id"].nullable is False


def test_message_supports_all_sender_and_media_types() -> None:
    message_columns = inspect(Message).columns
    assert message_columns["content"].nullable is True
    assert message_columns["sender_user_id"].nullable is True
    assert Message.message_type.type.enums == [
        "text",
        "image",
        "audio",
        "file",
    ]


def test_expected_constraints_and_indexes_exist() -> None:
    complaint_constraints = {
        constraint.name for constraint in Complaint.__table__.constraints
    }
    assert "fk_complaints_equipment_customer" in complaint_constraints
    assert "ck_complaints_approval_consistency" in complaint_constraints
    assert "ck_complaints_rejection_requires_reason" in complaint_constraints

    work_order_constraints = {
        constraint.name for constraint in WorkOrder.__table__.constraints
    }
    assert "fk_work_orders_complaint_equipment" in work_order_constraints
    assert "fk_work_orders_equipment_customer" in work_order_constraints
    assert "uq_work_orders_complaint_id" in work_order_constraints

    assignment_indexes = {
        index.name for index in TechnicianAssignment.__table__.indexes
    }
    assert "uq_technician_assignments_active_work_order" in assignment_indexes

    assert {
        "ix_complaints_status",
        "ix_complaints_priority",
        "ix_complaints_customer_id",
    } <= {index.name for index in Complaint.__table__.indexes}
    assert {
        "ix_work_orders_status",
        "ix_work_orders_scheduled_date",
    } <= {index.name for index in WorkOrder.__table__.indexes}
    assert {
        "ix_messages_conversation_created_at",
    } <= {index.name for index in Message.__table__.indexes}

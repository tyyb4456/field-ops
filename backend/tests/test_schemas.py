from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import (
    Channel,
    EquipmentDocumentType,
    MessageSenderType,
    MessageType,
    Priority,
)
from app.schemas.complaint import ComplaintCreate
from app.schemas.equipment_document import EquipmentDocumentCreate
from app.schemas.message import MessageCreate
from app.schemas.work_order import WorkOrderCreate


def test_complaint_can_be_created_without_equipment() -> None:
    complaint = ComplaintCreate(
        customer_id=uuid.uuid4(),
        description="Inverter is offline.",
        channel=Channel.WEB,
    )

    assert complaint.equipment_id is None
    assert complaint.priority is Priority.NORMAL
    assert complaint.reported_symptoms == []


def test_request_schemas_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ComplaintCreate(
            customer_id=uuid.uuid4(),
            description="Inverter is offline.",
            channel=Channel.WEB,
            unexpected="value",
        )


def test_message_defaults_to_text() -> None:
    message = MessageCreate(
        conversation_id=uuid.uuid4(),
        sender_type=MessageSenderType.CUSTOMER,
        content="Hello",
    )

    assert message.message_type is MessageType.TEXT


def test_work_order_derives_ownership_from_complaint() -> None:
    work_order = WorkOrderCreate(
        complaint_id=uuid.uuid4(),
        title="Repair inverter",
        description="Investigate the fault.",
    )

    assert work_order.work_order_number is None
    assert work_order.priority is Priority.NORMAL
    assert work_order.required_actions == []


def test_equipment_document_rejects_negative_file_size() -> None:
    with pytest.raises(ValidationError):
        EquipmentDocumentCreate(
            manufacturer="SolarEdge",
            model="SE10K-RWS",
            title="Manual",
            document_type=EquipmentDocumentType.MANUAL,
            file_size=-1,
        )

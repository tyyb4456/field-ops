from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.enums import (
    Channel,
    ComplaintStatus,
    MessageSenderType,
    TechnicianAssignmentStatus,
    UserRole,
    WorkOrderStatus,
)
from app.models.equipment import Equipment
from app.models.message import Message
from app.models.service_record import ServiceRecord
from app.models.technician import Technician
from app.models.technician_assignment import TechnicianAssignment
from app.models.user import User
from app.models.work_order import WorkOrder


async def _create_user(
    session: AsyncSession,
    *,
    role: UserRole,
    full_name: str = "Test User",
) -> User:
    user = User(
        full_name=full_name,
        email=f"{uuid.uuid4().hex}@example.com",
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_customer(
    session: AsyncSession,
    *,
    full_name: str = "Test Customer",
) -> Customer:
    user = await _create_user(
        session,
        role=UserRole.CUSTOMER,
        full_name=full_name,
    )
    customer = Customer(user_id=user.id, address="1 Solar Way")
    session.add(customer)
    await session.flush()
    return customer


async def _create_technician(
    session: AsyncSession,
    *,
    full_name: str = "Test Technician",
) -> Technician:
    user = await _create_user(
        session,
        role=UserRole.TECHNICIAN,
        full_name=full_name,
    )
    technician = Technician(
        user_id=user.id,
        skills={"solar_inverter": "advanced"},
        service_area="North",
    )
    session.add(technician)
    await session.flush()
    return technician


async def _create_equipment(
    session: AsyncSession,
    customer: Customer,
    *,
    serial_number: str | None = None,
) -> Equipment:
    equipment = Equipment(
        customer_id=customer.id,
        manufacturer="SolarEdge",
        model="SE10K-RWS",
        serial_number=serial_number or uuid.uuid4().hex,
        equipment_type="solar_inverter",
    )
    session.add(equipment)
    await session.flush()
    return equipment


async def _create_conversation(
    session: AsyncSession,
    customer: Customer,
) -> Conversation:
    conversation = Conversation(
        customer_id=customer.id,
        channel=Channel.WEB,
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def _create_complaint(
    session: AsyncSession,
    customer: Customer,
    *,
    equipment: Equipment | None = None,
    conversation: Conversation | None = None,
    status: ComplaintStatus = ComplaintStatus.DRAFT,
    admin: User | None = None,
) -> Complaint:
    approved = status in {
        ComplaintStatus.APPROVED,
        ComplaintStatus.UNDER_INVESTIGATION,
        ComplaintStatus.CONVERTED_TO_WORK_ORDER,
    }
    complaint = Complaint(
        customer_id=customer.id,
        equipment_id=equipment.id if equipment is not None else None,
        origin_conversation_id=(conversation.id if conversation is not None else None),
        description="Inverter stopped exporting power.",
        channel=Channel.WEB,
        status=status,
        approved_by_id=admin.id if approved and admin is not None else None,
        approved_at=(datetime.now(UTC) if approved and admin is not None else None),
    )
    session.add(complaint)
    await session.flush()
    return complaint


async def _create_work_order(
    session: AsyncSession,
    complaint: Complaint,
    *,
    number: str | None = None,
    status: WorkOrderStatus = WorkOrderStatus.DRAFT,
    admin: User | None = None,
    completion_date: date | None = None,
) -> WorkOrder:
    approved = status in {
        WorkOrderStatus.APPROVED,
        WorkOrderStatus.ASSIGNED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.ON_HOLD,
        WorkOrderStatus.COMPLETED,
    }
    work_order = WorkOrder(
        complaint_id=complaint.id,
        customer_id=complaint.customer_id,
        equipment_id=complaint.equipment_id,
        work_order_number=number or f"WO-{uuid.uuid4().hex[:10]}",
        title="Repair solar inverter",
        description="Investigate and repair the inverter.",
        status=status,
        approved_by_id=admin.id if approved and admin is not None else None,
        approved_at=(datetime.now(UTC) if approved and admin is not None else None),
        completion_date=completion_date,
    )
    session.add(work_order)
    await session.flush()
    return work_order


async def test_database_connectivity(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def test_transaction_rollback_discards_changes(
    db_session: AsyncSession,
) -> None:
    user = await _create_user(db_session, role=UserRole.ADMIN)
    assert user.id is not None

    await db_session.rollback()

    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 0


async def test_customer_can_own_multiple_equipment(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    first = await _create_equipment(db_session, customer)
    second = await _create_equipment(db_session, customer)

    equipment = (
        await db_session.scalars(
            select(Equipment).where(Equipment.customer_id == customer.id)
        )
    ).all()

    assert {first.id, second.id} <= {item.id for item in equipment}


async def test_customer_can_have_multiple_conversations(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    first = await _create_conversation(db_session, customer)
    second = await _create_conversation(db_session, customer)

    conversations = (
        await db_session.scalars(
            select(Conversation).where(Conversation.customer_id == customer.id)
        )
    ).all()

    assert {first.id, second.id} <= {item.id for item in conversations}


async def test_conversation_can_contain_multiple_messages(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    conversation = await _create_conversation(db_session, customer)

    db_session.add_all(
        [
            Message(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.CUSTOMER,
                content="My inverter is offline.",
            ),
            Message(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.AI_AGENT,
                content="Can you share the error code?",
            ),
            Message(
                conversation_id=conversation.id,
                sender_type=MessageSenderType.SYSTEM,
                content="Conversation created.",
            ),
        ]
    )
    await db_session.flush()

    messages = (
        await db_session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    ).all()

    assert len(messages) == 3


async def test_complaint_can_exist_without_equipment(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    complaint = await _create_complaint(db_session, customer)

    assert complaint.equipment_id is None
    assert complaint.origin_conversation_id is None


async def test_complaint_can_link_equipment_and_conversation(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    conversation = await _create_conversation(db_session, customer)

    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=equipment,
        conversation=conversation,
    )

    assert complaint.equipment_id == equipment.id
    assert complaint.origin_conversation_id == conversation.id


async def test_work_order_references_its_complaint(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=equipment,
    )

    work_order = await _create_work_order(db_session, complaint)

    assert work_order.complaint_id == complaint.id
    assert work_order.customer_id == customer.id
    assert work_order.equipment_id == equipment.id


async def test_work_order_preserves_assignment_history(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=equipment,
    )
    work_order = await _create_work_order(db_session, complaint)
    first_technician = await _create_technician(db_session)
    second_technician = await _create_technician(db_session)

    first = TechnicianAssignment(
        work_order_id=work_order.id,
        technician_id=first_technician.id,
        assignment_status=TechnicianAssignmentStatus.REJECTED,
        rejected_at=datetime.now(UTC),
        rejection_reason="Outside service area.",
    )
    db_session.add(first)
    await db_session.flush()

    second = TechnicianAssignment(
        work_order_id=work_order.id,
        technician_id=second_technician.id,
        assignment_status=TechnicianAssignmentStatus.OFFERED,
    )
    db_session.add(second)
    await db_session.flush()

    assignments = (
        await db_session.scalars(
            select(TechnicianAssignment)
            .where(TechnicianAssignment.work_order_id == work_order.id)
            .order_by(TechnicianAssignment.assigned_at)
        )
    ).all()

    assert len(assignments) == 2
    assert assignments[0].technician_id == first_technician.id
    assert assignments[1].technician_id == second_technician.id


async def test_technician_can_have_multiple_assignments(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    technician = await _create_technician(db_session)

    work_orders = []
    for _ in range(2):
        complaint = await _create_complaint(
            db_session,
            customer,
            equipment=equipment,
        )
        work_orders.append(await _create_work_order(db_session, complaint))

    db_session.add_all(
        [
            TechnicianAssignment(
                work_order_id=work_order.id,
                technician_id=technician.id,
            )
            for work_order in work_orders
        ]
    )
    await db_session.flush()

    assignments = (
        await db_session.scalars(
            select(TechnicianAssignment).where(
                TechnicianAssignment.technician_id == technician.id
            )
        )
    ).all()

    assert len(assignments) == 2


async def test_service_record_links_equipment_and_work_order(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=equipment,
    )
    work_order = await _create_work_order(db_session, complaint)
    technician = await _create_technician(db_session)

    record = ServiceRecord(
        equipment_id=equipment.id,
        work_order_id=work_order.id,
        technician_id=technician.id,
        work_performed="Replaced the communication board.",
        findings="Communication board failed.",
        parts_replaced=[{"part": "communication_board", "quantity": 1}],
    )
    db_session.add(record)
    await db_session.flush()

    stored = await db_session.scalar(
        select(ServiceRecord).where(ServiceRecord.id == record.id)
    )

    assert stored is not None
    assert stored.equipment_id == equipment.id
    assert stored.work_order_id == work_order.id


async def test_complaint_equipment_must_belong_to_customer(
    db_session: AsyncSession,
) -> None:
    owner = await _create_customer(db_session)
    other = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, owner)

    complaint = Complaint(
        customer_id=other.id,
        equipment_id=equipment.id,
        description="Wrong owner.",
        channel=Channel.WEB,
    )
    db_session.add(complaint)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_work_order_equipment_must_match_complaint(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    first = await _create_equipment(db_session, customer)
    second = await _create_equipment(db_session, customer)
    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=first,
    )

    work_order = WorkOrder(
        complaint_id=complaint.id,
        customer_id=customer.id,
        equipment_id=second.id,
        work_order_number=f"WO-{uuid.uuid4().hex[:10]}",
        title="Mismatched equipment",
        description="This should fail.",
    )
    db_session.add(work_order)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_only_one_active_assignment_per_work_order(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=equipment,
    )
    work_order = await _create_work_order(db_session, complaint)
    first_technician = await _create_technician(db_session)
    second_technician = await _create_technician(db_session)

    db_session.add(
        TechnicianAssignment(
            work_order_id=work_order.id,
            technician_id=first_technician.id,
        )
    )
    await db_session.flush()

    db_session.add(
        TechnicianAssignment(
            work_order_id=work_order.id,
            technician_id=second_technician.id,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_rejected_complaint_requires_reason(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    complaint = Complaint(
        customer_id=customer.id,
        description="Rejected without reason.",
        channel=Channel.WEB,
        status=ComplaintStatus.REJECTED,
    )
    db_session.add(complaint)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_approved_complaint_requires_reviewer(
    db_session: AsyncSession,
) -> None:
    customer = await _create_customer(db_session)
    complaint = Complaint(
        customer_id=customer.id,
        description="Approved without reviewer.",
        channel=Channel.WEB,
        status=ComplaintStatus.APPROVED,
    )
    db_session.add(complaint)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_completed_work_order_requires_completion_date(
    db_session: AsyncSession,
) -> None:
    admin = await _create_user(db_session, role=UserRole.ADMIN)
    customer = await _create_customer(db_session)
    equipment = await _create_equipment(db_session, customer)
    complaint = await _create_complaint(
        db_session,
        customer,
        equipment=equipment,
        status=ComplaintStatus.APPROVED,
        admin=admin,
    )
    with pytest.raises(IntegrityError):
        await _create_work_order(
            db_session,
            complaint,
            status=WorkOrderStatus.COMPLETED,
            admin=admin,
            completion_date=None,
        )

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.enums import (
    Channel,
    ComplaintStatus,
    ConversationStatus,
    EquipmentOperationalStatus,
    Priority,
    TechnicianAssignmentStatus,
    UserRole,
    WorkOrderStatus,
)
from app.models.equipment import Equipment
from app.models.technician import Technician
from app.models.technician_assignment import TechnicianAssignment
from app.models.user import User
from app.models.work_order import WorkOrder
from app.services.shared.actor import ActorContext


def actor_for(user: User) -> ActorContext:
    return ActorContext(
        user_id=user.id,
        role=user.role,
        customer_id=(
            user.customer.id if user.customer is not None else None
        ),
        technician_id=(
            user.technician.id if user.technician is not None else None
        ),
    )


async def create_admin(
    session: AsyncSession,
    *,
    full_name: str = "Admin User",
) -> User:
    user = User(
        full_name=full_name,
        email=f"{uuid.uuid4().hex}@example.com",
        role=UserRole.ADMIN,
        is_active=True,
    )
    user.customer = None
    user.technician = None
    session.add(user)
    await session.flush()
    return user


async def create_customer(
    session: AsyncSession,
    *,
    full_name: str = "Test Customer",
    address: str | None = "1 Solar Way",
) -> User:
    user = User(
        full_name=full_name,
        email=f"{uuid.uuid4().hex}@example.com",
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    user.customer = Customer(address=address, preferred_language="en")
    user.technician = None
    session.add(user)
    await session.flush()
    return user


async def create_technician(
    session: AsyncSession,
    *,
    full_name: str = "Test Technician",
    is_active: bool = True,
    is_available: bool = True,
    skills: dict[str, Any] | None = None,
) -> User:
    user = User(
        full_name=full_name,
        email=f"{uuid.uuid4().hex}@example.com",
        role=UserRole.TECHNICIAN,
        is_active=True,
    )
    user.technician = Technician(
        skills=skills or {"solar_inverter": "advanced"},
        service_area="North",
        is_active=is_active,
        is_available=is_available,
    )
    user.customer = None
    session.add(user)
    await session.flush()
    return user


async def create_equipment(
    session: AsyncSession,
    customer: Customer,
    *,
    manufacturer: str = "SolarEdge",
    model: str = "SE10K-RWS",
    serial_number: str | None = None,
    equipment_type: str = "solar_inverter",
    operational_status: EquipmentOperationalStatus = (
        EquipmentOperationalStatus.ACTIVE
    ),
) -> Equipment:
    equipment = Equipment(
        customer_id=customer.id,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number or uuid.uuid4().hex,
        equipment_type=equipment_type,
        operational_status=operational_status,
    )
    session.add(equipment)
    await session.flush()
    return equipment


async def create_conversation(
    session: AsyncSession,
    customer: Customer,
    *,
    status: ConversationStatus = ConversationStatus.ACTIVE,
    channel: Channel = Channel.WEB,
) -> Conversation:
    now = datetime.now(UTC)
    conversation = Conversation(
        customer_id=customer.id,
        status=status,
        channel=channel,
        started_at=now,
        last_activity_at=now,
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def create_complaint(
    session: AsyncSession,
    customer: Customer,
    *,
    equipment: Equipment | None = None,
    conversation: Conversation | None = None,
    status: ComplaintStatus = ComplaintStatus.DRAFT,
    admin: User | None = None,
    priority: Priority = Priority.NORMAL,
    description: str = "Inverter stopped exporting power.",
) -> Complaint:
    approved = status in {
        ComplaintStatus.APPROVED,
        ComplaintStatus.UNDER_INVESTIGATION,
        ComplaintStatus.CONVERTED_TO_WORK_ORDER,
    }
    complaint = Complaint(
        customer_id=customer.id,
        equipment_id=equipment.id if equipment is not None else None,
        origin_conversation_id=(
            conversation.id if conversation is not None else None
        ),
        description=description,
        channel=Channel.WEB,
        status=status,
        priority=priority,
        submitted_at=(
            datetime.now(UTC)
            if status is not ComplaintStatus.DRAFT
            else None
        ),
        approved_by_id=(
            admin.id if approved and admin is not None else None
        ),
        approved_at=(
            datetime.now(UTC) if approved and admin is not None else None
        ),
        rejection_reason=(
            "Duplicate report" if status is ComplaintStatus.REJECTED else None
        ),
    )
    session.add(complaint)
    await session.flush()
    return complaint


async def create_work_order(
    session: AsyncSession,
    complaint: Complaint,
    *,
    status: WorkOrderStatus = WorkOrderStatus.DRAFT,
    admin: User | None = None,
    number: str | None = None,
    completion_date: date | None = None,
) -> WorkOrder:
    approved = status in {
        WorkOrderStatus.APPROVED,
        WorkOrderStatus.ASSIGNED,
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.ON_HOLD,
        WorkOrderStatus.COMPLETED,
    }
    if status is WorkOrderStatus.COMPLETED and completion_date is None:
        completion_date = date.today()

    work_order = WorkOrder(
        complaint_id=complaint.id,
        customer_id=complaint.customer_id,
        equipment_id=complaint.equipment_id,
        work_order_number=number or f"WO-{uuid.uuid4().hex[:10].upper()}",
        title="Repair solar inverter",
        description="Investigate and repair the inverter.",
        status=status,
        approved_by_id=(
            admin.id if approved and admin is not None else None
        ),
        approved_at=(
            datetime.now(UTC) if approved and admin is not None else None
        ),
        completion_date=completion_date,
        completion_summary=(
            "Work completed." if status is WorkOrderStatus.COMPLETED else None
        ),
    )
    session.add(work_order)
    await session.flush()
    return work_order


async def create_assignment(
    session: AsyncSession,
    work_order: WorkOrder,
    technician: Technician,
    *,
    status: TechnicianAssignmentStatus = TechnicianAssignmentStatus.OFFERED,
) -> TechnicianAssignment:
    now = datetime.now(UTC)
    assignment = TechnicianAssignment(
        work_order_id=work_order.id,
        technician_id=technician.id,
        assignment_status=status,
        accepted_at=(
            now if status is TechnicianAssignmentStatus.ACCEPTED else None
        ),
        rejected_at=(
            now if status is TechnicianAssignmentStatus.REJECTED else None
        ),
        rejection_reason=(
            "Outside service area"
            if status is TechnicianAssignmentStatus.REJECTED
            else None
        ),
    )
    session.add(assignment)
    await session.flush()
    return assignment


__all__ = [
    "actor_for",
    "create_admin",
    "create_assignment",
    "create_complaint",
    "create_conversation",
    "create_customer",
    "create_equipment",
    "create_technician",
    "create_work_order",
]

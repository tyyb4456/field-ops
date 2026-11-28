from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    Channel,
    ComplaintStatus,
    ConversationStatus,
    DocumentProcessingStatus,
    EquipmentDocumentType,
    EquipmentOperationalStatus,
    MessageSenderType,
    Priority,
    TechnicianAssignmentStatus,
    WorkOrderStatus,
)
from app.models.equipment import Equipment
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate
from app.schemas.conversation import ConversationUpdate
from app.schemas.equipment import EquipmentCreate
from app.schemas.equipment_document import EquipmentDocumentCreate
from app.schemas.message import MessageCreate
from app.schemas.service_record import ServiceRecordCreate
from app.schemas.technician_assignment import (
    ReassignRequest,
    TechnicianAssignmentCreate,
)
from app.schemas.work_order import (
    WorkOrderComplete,
    WorkOrderCreate,
    WorkOrderUpdate,
)
from app.services.assignments import assignments as assignment_service
from app.services.complaints import complaints as complaint_service
from app.services.conversations import conversations as conversation_service
from app.services.equipment import equipment as equipment_service
from app.services.equipment_documents import (
    equipment_documents as document_service,
)
from app.services.service_records import service_records as service_record_service
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import (
    ConflictError,
    DomainValidationError,
    DuplicateResourceError,
    ForbiddenError,
    InvalidStateTransitionError,
)
from app.services.shared.transactions import commit
from app.services.work_orders import work_orders as work_order_service
from tests.support import (
    actor_for,
    create_admin,
    create_assignment,
    create_complaint,
    create_conversation,
    create_customer,
    create_equipment,
    create_technician,
    create_work_order,
)


async def _approved_work_order(
    session: AsyncSession,
    *,
    status: WorkOrderStatus = WorkOrderStatus.APPROVED,
):
    admin_user = await create_admin(session)
    customer_user = await create_customer(session)
    equipment = await create_equipment(session, customer_user.customer)
    complaint = await create_complaint(
        session,
        customer_user.customer,
        equipment=equipment,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )
    work_order = await create_work_order(
        session,
        complaint,
        status=status,
        admin=admin_user,
    )
    return admin_user, customer_user, equipment, complaint, work_order


# ---------------------------------------------------------------------------
# Authorization and ownership
# ---------------------------------------------------------------------------


async def test_customer_cannot_register_equipment_for_another_customer(
    db_session: AsyncSession,
) -> None:
    owner = await create_customer(db_session)
    other = await create_customer(db_session)

    with pytest.raises(ForbiddenError):
        await equipment_service.create_equipment(
            db_session,
            actor_for(other),
            EquipmentCreate(
                customer_id=owner.customer.id,
                manufacturer="SolarEdge",
                model="SE10K",
                equipment_type="solar_inverter",
            ),
        )


async def test_customer_cannot_read_another_customers_equipment(
    db_session: AsyncSession,
) -> None:
    owner = await create_customer(db_session)
    other = await create_customer(db_session)
    equipment = await create_equipment(db_session, owner.customer)

    with pytest.raises(AccessDeniedError):
        await equipment_service.get_equipment_for_actor(
            db_session,
            equipment.id,
            actor_for(other),
        )


async def test_unassigned_technician_cannot_read_equipment(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    technician_user = await create_technician(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)

    with pytest.raises(AccessDeniedError):
        await equipment_service.get_equipment_for_actor(
            db_session,
            equipment.id,
            actor_for(technician_user),
        )


async def test_assigned_technician_can_read_work_order_complaint(
    db_session: AsyncSession,
) -> None:
    _admin_user, _, _equipment, complaint, work_order = (
        await _approved_work_order(db_session)
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    fetched = await complaint_service.get_complaint_for_actor(
        db_session,
        complaint.id,
        actor_for(technician_user),
    )

    assert fetched.id == complaint.id


async def test_customer_complaint_list_is_scoped_to_self(
    db_session: AsyncSession,
) -> None:
    first = await create_customer(db_session)
    second = await create_customer(db_session)
    mine = await create_complaint(db_session, first.customer)
    await create_complaint(db_session, second.customer)

    items, total = await complaint_service.list_complaints(
        db_session,
        actor_for(first),
        limit=50,
        offset=0,
    )

    assert total == 1
    assert [item.id for item in items] == [mine.id]


# ---------------------------------------------------------------------------
# Complaint lifecycle
# ---------------------------------------------------------------------------


async def test_complaint_submit_moves_to_pending_approval(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    complaint = await complaint_service.create_complaint(
        db_session,
        actor_for(customer_user),
        ComplaintCreate(
            description="Inverter offline.",
            channel=Channel.WEB,
        ),
    )
    assert complaint.status is ComplaintStatus.DRAFT

    submitted = await complaint_service.submit_complaint(
        db_session,
        complaint,
        actor_for(customer_user),
    )

    assert submitted.status is ComplaintStatus.PENDING_APPROVAL
    assert submitted.submitted_at is not None


async def test_admin_approves_pending_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )

    approved = await complaint_service.approve_complaint(
        db_session,
        complaint,
        actor_for(admin_user),
        notes="Valid report.",
    )

    assert approved.status is ComplaintStatus.APPROVED
    assert approved.approved_by_id == admin_user.id
    assert approved.approved_at is not None
    assert approved.approval_notes == "Valid report."


async def test_reject_requires_reason(db_session: AsyncSession) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )

    with pytest.raises(DomainValidationError):
        await complaint_service.reject_complaint(
            db_session,
            complaint,
            actor_for(admin_user),
            rejection_reason="   ",
        )


async def test_admin_rejects_pending_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )

    rejected = await complaint_service.reject_complaint(
        db_session,
        complaint,
        actor_for(admin_user),
        rejection_reason="Duplicate report.",
    )

    assert rejected.status is ComplaintStatus.REJECTED
    assert rejected.rejection_reason == "Duplicate report."


async def test_only_approved_complaint_enters_investigation(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )

    with pytest.raises(ConflictError):
        await complaint_service.start_investigation(
            db_session,
            complaint,
            actor_for(admin_user),
        )


async def test_customer_cannot_set_urgent_priority(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)

    with pytest.raises(ForbiddenError):
        await complaint_service.create_complaint(
            db_session,
            actor_for(customer_user),
            ComplaintCreate(
                description="Everything is on fire.",
                channel=Channel.WEB,
                priority=Priority.URGENT,
            ),
        )


async def test_approved_complaint_cannot_be_edited(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )

    with pytest.raises(ConflictError):
        await complaint_service.update_complaint(
            db_session,
            complaint,
            actor_for(customer_user),
            ComplaintUpdate(description="Changed after approval."),
        )


async def test_cancel_allowed_until_review_completes(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    cancellable = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )
    approved = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )

    cancelled = await complaint_service.cancel_complaint(
        db_session,
        cancellable,
        actor_for(customer_user),
    )
    assert cancelled.status is ComplaintStatus.CANCELLED
    assert cancelled.closed_at is not None

    with pytest.raises(ConflictError):
        await complaint_service.cancel_complaint(
            db_session,
            approved,
            actor_for(customer_user),
        )


# ---------------------------------------------------------------------------
# Work orders
# ---------------------------------------------------------------------------


async def test_create_work_order_converts_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        equipment=equipment,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )

    work_order = await work_order_service.create_work_order(
        db_session,
        actor_for(admin_user),
        WorkOrderCreate(
            complaint_id=complaint.id,
            title="Repair inverter",
            description="Investigate the fault.",
        ),
    )

    assert work_order.status is WorkOrderStatus.DRAFT
    assert work_order.complaint_id == complaint.id
    assert work_order.customer_id == complaint.customer_id
    assert complaint.status is ComplaintStatus.CONVERTED_TO_WORK_ORDER
    assert work_order.work_order_number


async def test_work_order_requires_approved_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        equipment=equipment,
        status=ComplaintStatus.DRAFT,
    )

    with pytest.raises(InvalidStateTransitionError):
        await work_order_service.create_work_order(
            db_session,
            actor_for(admin_user),
            WorkOrderCreate(
                complaint_id=complaint.id,
                title="Repair inverter",
                description="Investigate the fault.",
            ),
        )


async def test_work_order_requires_complaint_equipment(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )

    with pytest.raises(DomainValidationError):
        await work_order_service.create_work_order(
            db_session,
            actor_for(admin_user),
            WorkOrderCreate(
                complaint_id=complaint.id,
                title="Repair inverter",
                description="Investigate the fault.",
            ),
        )


async def test_only_one_work_order_per_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, complaint, _ = await _approved_work_order(db_session)

    with pytest.raises(DuplicateResourceError):
        await work_order_service.create_work_order(
            db_session,
            actor_for(admin_user),
            WorkOrderCreate(
                complaint_id=complaint.id,
                title="Second work order",
                description="Should be rejected.",
            ),
        )


async def test_non_admin_cannot_create_or_approve_work_order(
    db_session: AsyncSession,
) -> None:
    _admin_user, customer_user, _equipment, complaint, work_order = (
        await _approved_work_order(db_session, status=WorkOrderStatus.DRAFT)
    )

    with pytest.raises(ForbiddenError):
        await work_order_service.create_work_order(
            db_session,
            actor_for(customer_user),
            WorkOrderCreate(
                complaint_id=complaint.id,
                title="Sneaky",
                description="Not allowed.",
            ),
        )

    with pytest.raises(ForbiddenError):
        await work_order_service.approve_work_order(
            db_session,
            work_order,
            actor_for(customer_user),
        )


async def test_completed_work_order_cannot_be_updated(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.COMPLETED,
    )

    with pytest.raises(ConflictError):
        await work_order_service.update_work_order(
            db_session,
            work_order,
            actor_for(admin_user),
            WorkOrderUpdate(title="Changed"),
        )


async def test_cancel_work_order_withdraws_active_assignment(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    technician_user = await create_technician(db_session)
    assignment = await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    cancelled = await work_order_service.cancel_work_order(
        db_session,
        work_order,
        actor_for(admin_user),
    )

    assert cancelled.status is WorkOrderStatus.CANCELLED
    assert assignment.assignment_status is TechnicianAssignmentStatus.WITHDRAWN


# ---------------------------------------------------------------------------
# Technician assignments and execution
# ---------------------------------------------------------------------------


async def test_assign_offers_and_marks_work_order_assigned(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(db_session)
    technician_user = await create_technician(db_session)

    assignment = await assignment_service.create_assignment(
        db_session,
        actor_for(admin_user),
        work_order.id,
        TechnicianAssignmentCreate(technician_id=technician_user.technician.id),
    )

    assert assignment.assignment_status is TechnicianAssignmentStatus.OFFERED
    assert work_order.status is WorkOrderStatus.ASSIGNED


async def test_assignment_requires_approved_work_order(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.DRAFT,
    )
    technician_user = await create_technician(db_session)

    with pytest.raises(InvalidStateTransitionError):
        await assignment_service.create_assignment(
            db_session,
            actor_for(admin_user),
            work_order.id,
            TechnicianAssignmentCreate(
                technician_id=technician_user.technician.id,
            ),
        )


async def test_work_order_cannot_have_two_active_assignments(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(db_session)
    first = await create_technician(db_session)
    second = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        first.technician,
        status=TechnicianAssignmentStatus.OFFERED,
    )

    with pytest.raises(ConflictError):
        await assignment_service.create_assignment(
            db_session,
            actor_for(admin_user),
            work_order.id,
            TechnicianAssignmentCreate(technician_id=second.technician.id),
        )


async def test_inactive_technician_cannot_be_assigned(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(db_session)
    technician_user = await create_technician(
        db_session,
        is_active=False,
    )

    with pytest.raises(ConflictError):
        await assignment_service.create_assignment(
            db_session,
            actor_for(admin_user),
            work_order.id,
            TechnicianAssignmentCreate(
                technician_id=technician_user.technician.id,
            ),
        )


async def test_technician_accepts_own_assignment(
    db_session: AsyncSession,
) -> None:
    _, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    technician_user = await create_technician(db_session)
    assignment = await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
    )

    accepted = await assignment_service.accept_assignment(
        db_session,
        assignment,
        actor_for(technician_user),
    )

    assert accepted.assignment_status is TechnicianAssignmentStatus.ACCEPTED
    assert accepted.accepted_at is not None


async def test_other_technician_cannot_accept_assignment(
    db_session: AsyncSession,
) -> None:
    _, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    owner = await create_technician(db_session)
    intruder = await create_technician(db_session)
    assignment = await create_assignment(
        db_session,
        work_order,
        owner.technician,
    )

    with pytest.raises(AccessDeniedError):
        await assignment_service.accept_assignment(
            db_session,
            assignment,
            actor_for(intruder),
        )


async def test_rejecting_only_assignment_returns_work_order_to_approved(
    db_session: AsyncSession,
) -> None:
    _, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    technician_user = await create_technician(db_session)
    assignment = await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
    )

    rejected = await assignment_service.reject_assignment(
        db_session,
        assignment,
        actor_for(technician_user),
        rejection_reason="Outside service area.",
    )

    assert rejected.assignment_status is TechnicianAssignmentStatus.REJECTED
    assert rejected.rejected_at is not None
    assert work_order.status is WorkOrderStatus.APPROVED


async def test_reassign_withdraws_previous_and_preserves_history(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    first = await create_technician(db_session)
    second = await create_technician(db_session)
    previous = await create_assignment(
        db_session,
        work_order,
        first.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    replacement = await assignment_service.reassign_work_order(
        db_session,
        actor_for(admin_user),
        work_order.id,
        ReassignRequest(technician_id=second.technician.id),
    )

    assert previous.assignment_status is TechnicianAssignmentStatus.WITHDRAWN
    assert replacement.assignment_status is TechnicianAssignmentStatus.OFFERED
    assert replacement.technician_id == second.technician.id

    items, total = await assignment_service.list_assignments(
        db_session,
        actor_for(admin_user),
        limit=50,
        offset=0,
        work_order_id=work_order.id,
    )
    assert total == 2
    assert {item.id for item in items} == {previous.id, replacement.id}


async def test_work_execution_requires_accepted_assignment(
    db_session: AsyncSession,
) -> None:
    _, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.OFFERED,
    )

    with pytest.raises(ForbiddenError):
        await work_order_service.start_work_order(
            db_session,
            work_order,
            actor_for(technician_user),
        )


async def test_work_order_execution_lifecycle(
    db_session: AsyncSession,
) -> None:
    _, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    technician_user = await create_technician(db_session)
    assignment = await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )
    actor = actor_for(technician_user)

    started = await work_order_service.start_work_order(
        db_session,
        work_order,
        actor,
    )
    assert started.status is WorkOrderStatus.IN_PROGRESS
    assert assignment.started_at is not None

    held = await work_order_service.hold_work_order(
        db_session,
        work_order,
        actor,
    )
    assert held.status is WorkOrderStatus.ON_HOLD

    resumed = await work_order_service.resume_work_order(
        db_session,
        work_order,
        actor,
    )
    assert resumed.status is WorkOrderStatus.IN_PROGRESS

    completed = await work_order_service.complete_work_order(
        db_session,
        work_order,
        actor,
        WorkOrderComplete(completion_summary="Replaced the inverter board."),
    )
    assert completed.status is WorkOrderStatus.COMPLETED
    assert completed.completion_date == date.today()
    assert assignment.completed_at is not None


async def test_completion_rejects_future_date(
    db_session: AsyncSession,
) -> None:
    _, _, _, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    with pytest.raises(DomainValidationError):
        await work_order_service.complete_work_order(
            db_session,
            work_order,
            actor_for(technician_user),
            WorkOrderComplete(
                completion_summary="Done early.",
                completion_date=date.today() + timedelta(days=1),
            ),
        )


# ---------------------------------------------------------------------------
# Conversations and messages
# ---------------------------------------------------------------------------


async def test_customer_message_reactivates_awaiting_conversation(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(
        db_session,
        customer_user.customer,
        status=ConversationStatus.AWAITING_CUSTOMER,
    )

    message = await conversation_service.add_message(
        db_session,
        conversation,
        actor_for(customer_user),
        MessageCreate(
            sender_type=MessageSenderType.CUSTOMER,
            content="Here is the error code.",
        ),
    )

    assert message.sender_type is MessageSenderType.CUSTOMER
    assert message.sender_user_id == customer_user.id
    assert conversation.status is ConversationStatus.ACTIVE


async def test_admin_message_sets_awaiting_customer(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(
        db_session,
        customer_user.customer,
        status=ConversationStatus.ACTIVE,
    )

    await conversation_service.add_message(
        db_session,
        conversation,
        actor_for(admin_user),
        MessageCreate(
            sender_type=MessageSenderType.ADMIN,
            content="Can you send a photo?",
        ),
    )

    assert conversation.status is ConversationStatus.AWAITING_CUSTOMER


async def test_customer_cannot_send_admin_message(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(db_session, customer_user.customer)

    with pytest.raises(ForbiddenError):
        await conversation_service.add_message(
            db_session,
            conversation,
            actor_for(customer_user),
            MessageCreate(
                sender_type=MessageSenderType.ADMIN,
                content="Pretending to be support.",
            ),
        )


async def test_closed_conversation_rejects_new_messages(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(
        db_session,
        customer_user.customer,
        status=ConversationStatus.CLOSED,
    )

    with pytest.raises(ConflictError):
        await conversation_service.add_message(
            db_session,
            conversation,
            actor_for(customer_user),
            MessageCreate(
                sender_type=MessageSenderType.CUSTOMER,
                content="One more thing.",
            ),
        )


async def test_customer_cannot_update_another_customers_conversation(
    db_session: AsyncSession,
) -> None:
    owner = await create_customer(db_session)
    other = await create_customer(db_session)
    conversation = await create_conversation(db_session, owner.customer)

    with pytest.raises(AccessDeniedError):
        await conversation_service.update_conversation(
            db_session,
            conversation,
            actor_for(other),
            ConversationUpdate(status=ConversationStatus.CLOSED),
        )


async def test_assigned_technician_can_access_conversation(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(db_session, customer_user.customer)
    equipment = await create_equipment(db_session, customer_user.customer)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        equipment=equipment,
        conversation=conversation,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )
    work_order = await create_work_order(
        db_session,
        complaint,
        status=WorkOrderStatus.ASSIGNED,
        admin=admin_user,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(db_session, work_order, technician_user.technician)

    fetched = await conversation_service.get_conversation_for_actor(
        db_session,
        conversation.id,
        actor_for(technician_user),
    )
    assert fetched.id == conversation.id

    stranger = await create_technician(db_session)
    with pytest.raises(AccessDeniedError):
        await conversation_service.get_conversation_for_actor(
            db_session,
            conversation.id,
            actor_for(stranger),
        )


async def test_message_listing_is_ordered(db_session: AsyncSession) -> None:
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(db_session, customer_user.customer)

    base = datetime(2024, 1, 1, tzinfo=UTC)
    for index in range(3):
        message = await conversation_service.add_message(
            db_session,
            conversation,
            actor_for(customer_user),
            MessageCreate(
                sender_type=MessageSenderType.CUSTOMER,
                content=f"message {index}",
            ),
        )
        message.created_at = base + timedelta(seconds=index)
        await db_session.flush()

    items, total = await conversation_service.list_messages(
        db_session,
        conversation.id,
        limit=50,
        offset=0,
    )

    assert total == 3
    assert [item.content for item in items] == [
        "message 0",
        "message 1",
        "message 2",
    ]


# ---------------------------------------------------------------------------
# Equipment and documents
# ---------------------------------------------------------------------------


async def test_duplicate_equipment_serial_is_rejected(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    await create_equipment(
        db_session,
        customer_user.customer,
        manufacturer="SolarEdge",
        serial_number="SN-123",
    )

    with pytest.raises(DuplicateResourceError):
        await equipment_service.create_equipment(
            db_session,
            actor_for(admin_user),
            EquipmentCreate(
                customer_id=customer_user.customer.id,
                manufacturer="SolarEdge",
                model="SE10K",
                equipment_type="solar_inverter",
                serial_number="SN-123",
            ),
        )


async def test_customer_cannot_register_non_active_equipment(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)

    with pytest.raises(ForbiddenError):
        await equipment_service.create_equipment(
            db_session,
            actor_for(customer_user),
            EquipmentCreate(
                manufacturer="SolarEdge",
                model="SE10K",
                equipment_type="solar_inverter",
                operational_status=EquipmentOperationalStatus.DEGRADED,
            ),
        )


async def test_technician_cannot_decommission_equipment(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        equipment=equipment,
        status=ComplaintStatus.APPROVED,
        admin=admin_user,
    )
    work_order = await create_work_order(
        db_session,
        complaint,
        status=WorkOrderStatus.ASSIGNED,
        admin=admin_user,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(db_session, work_order, technician_user.technician)

    with pytest.raises(ForbiddenError):
        await equipment_service.change_operational_status(
            db_session,
            equipment,
            actor_for(technician_user),
            EquipmentOperationalStatus.DECOMMISSIONED,
        )


async def test_decommissioned_equipment_cannot_be_reactivated(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(
        db_session,
        customer_user.customer,
        operational_status=EquipmentOperationalStatus.DECOMMISSIONED,
    )

    with pytest.raises(ConflictError):
        await equipment_service.change_operational_status(
            db_session,
            equipment,
            actor_for(admin_user),
            EquipmentOperationalStatus.ACTIVE,
        )


async def test_duplicate_equipment_document_is_rejected(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)
    payload = EquipmentDocumentCreate(
        title="Installation Manual",
        document_type=EquipmentDocumentType.MANUAL,
    )
    await document_service.create_document(
        db_session,
        actor_for(admin_user),
        equipment.id,
        payload,
    )

    with pytest.raises(DuplicateResourceError):
        await document_service.create_document(
            db_session,
            actor_for(admin_user),
            equipment.id,
            payload,
        )


async def test_document_processing_transitions(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)
    document = await document_service.create_document(
        db_session,
        actor_for(admin_user),
        equipment.id,
        EquipmentDocumentCreate(title="Datasheet"),
    )

    processing = await document_service.change_processing_status(
        db_session,
        document,
        actor_for(admin_user),
        processing_status=DocumentProcessingStatus.PROCESSING,
    )
    assert processing.processing_status is DocumentProcessingStatus.PROCESSING

    ready = await document_service.change_processing_status(
        db_session,
        document,
        actor_for(admin_user),
        processing_status=DocumentProcessingStatus.READY,
    )
    assert ready.processing_status is DocumentProcessingStatus.READY

    with pytest.raises(ConflictError):
        await document_service.change_processing_status(
            db_session,
            document,
            actor_for(admin_user),
            processing_status=DocumentProcessingStatus.PENDING,
        )


async def test_technician_cannot_write_equipment_document(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    technician_user = await create_technician(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)

    with pytest.raises(ForbiddenError):
        await document_service.create_document(
            db_session,
            actor_for(technician_user),
            equipment.id,
            EquipmentDocumentCreate(title="Manual"),
        )


# ---------------------------------------------------------------------------
# Service records
# ---------------------------------------------------------------------------


async def test_technician_records_service_for_accepted_work_order(
    db_session: AsyncSession,
) -> None:
    _, _, equipment, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    record = await service_record_service.create_service_record(
        db_session,
        actor_for(technician_user),
        ServiceRecordCreate(
            equipment_id=equipment.id,
            work_order_id=work_order.id,
            work_performed="Replaced the inverter board.",
        ),
    )

    assert record.technician_id == technician_user.technician.id
    assert record.equipment_id == equipment.id
    assert record.service_date == date.today()


async def test_technician_service_record_requires_work_order(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)
    technician_user = await create_technician(db_session)

    with pytest.raises(DomainValidationError):
        await service_record_service.create_service_record(
            db_session,
            actor_for(technician_user),
            ServiceRecordCreate(equipment_id=equipment.id),
        )


async def test_service_record_requires_accepted_assignment(
    db_session: AsyncSession,
) -> None:
    _, _, equipment, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.OFFERED,
    )

    with pytest.raises(ForbiddenError):
        await service_record_service.create_service_record(
            db_session,
            actor_for(technician_user),
            ServiceRecordCreate(
                equipment_id=equipment.id,
                work_order_id=work_order.id,
            ),
        )


async def test_service_record_requires_serviceable_work_order(
    db_session: AsyncSession,
) -> None:
    _, _, equipment, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.ASSIGNED,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    with pytest.raises(InvalidStateTransitionError):
        await service_record_service.create_service_record(
            db_session,
            actor_for(technician_user),
            ServiceRecordCreate(
                equipment_id=equipment.id,
                work_order_id=work_order.id,
            ),
        )


async def test_service_record_rejects_future_date(
    db_session: AsyncSession,
) -> None:
    _, _, equipment, _, work_order = await _approved_work_order(
        db_session,
        status=WorkOrderStatus.IN_PROGRESS,
    )
    technician_user = await create_technician(db_session)
    await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    with pytest.raises(DomainValidationError):
        await service_record_service.create_service_record(
            db_session,
            actor_for(technician_user),
            ServiceRecordCreate(
                equipment_id=equipment.id,
                work_order_id=work_order.id,
                service_date=date.today() + timedelta(days=1),
            ),
        )


async def test_admin_service_record_requires_technician_id(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    equipment = await create_equipment(db_session, customer_user.customer)

    with pytest.raises(DomainValidationError):
        await service_record_service.create_service_record(
            db_session,
            actor_for(admin_user),
            ServiceRecordCreate(equipment_id=equipment.id),
        )


async def test_customer_cannot_list_technician_service_records(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    technician_user = await create_technician(db_session)

    with pytest.raises(ForbiddenError):
        await service_record_service.list_technician_service_records(
            db_session,
            technician_user.technician.id,
            actor_for(customer_user),
            limit=50,
            offset=0,
        )


# ---------------------------------------------------------------------------
# Transaction handling
# ---------------------------------------------------------------------------


async def test_commit_translates_integrity_error(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    serial = "SN-CONFLICT"
    db_session.add(
        Equipment(
            customer_id=customer_user.customer.id,
            manufacturer="SolarEdge",
            model="SE10K",
            serial_number=serial,
            equipment_type="solar_inverter",
        )
    )
    await db_session.flush()

    db_session.add(
        Equipment(
            customer_id=customer_user.customer.id,
            manufacturer="SolarEdge",
            model="SE10K",
            serial_number=serial,
            equipment_type="solar_inverter",
        )
    )

    with pytest.raises(DuplicateResourceError):
        await commit(db_session)

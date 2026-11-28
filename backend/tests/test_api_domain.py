from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.core.config import settings
from app.db.session import get_db_session
from app.main import app
from app.models.complaint import Complaint
from app.models.enums import (
    ComplaintStatus,
    TechnicianAssignmentStatus,
    WorkOrderStatus,
)
from app.services.shared.actor import ActorContext
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

PREFIX = settings.api_v1_prefix


@asynccontextmanager
async def api_client(
    session: AsyncSession,
    actor: ActorContext,
) -> AsyncIterator[AsyncClient]:
    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_actor_context] = lambda: actor
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def _approved_complaint(
    session: AsyncSession,
    *,
    status: ComplaintStatus = ComplaintStatus.APPROVED,
):
    admin_user = await create_admin(session)
    customer_user = await create_customer(session)
    equipment = await create_equipment(session, customer_user.customer)
    complaint = await create_complaint(
        session,
        customer_user.customer,
        equipment=equipment,
        status=status,
        admin=admin_user,
    )
    return admin_user, customer_user, equipment, complaint


async def test_customer_files_complaint_deriving_ownership(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/complaints",
            json={"description": "Inverter offline.", "channel": "web"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == str(customer_user.customer.id)
    assert body["status"] == ComplaintStatus.DRAFT.value


async def test_customer_cannot_file_for_another_customer(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    other = await create_customer(db_session)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/complaints",
            json={
                "customer_id": str(other.customer.id),
                "description": "Not mine.",
                "channel": "web",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_reading_another_customers_complaint_is_404(
    db_session: AsyncSession,
) -> None:
    owner = await create_customer(db_session)
    intruder = await create_customer(db_session)
    complaint = await create_complaint(db_session, owner.customer)

    async with api_client(db_session, actor_for(intruder)) as client:
        response = await client.get(f"{PREFIX}/complaints/{complaint.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_customer_cannot_approve_complaint(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/complaints/{complaint.id}/approve",
            json={},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_admin_approves_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.PENDING_APPROVAL,
    )

    async with api_client(db_session, actor_for(admin_user)) as client:
        response = await client.post(
            f"{PREFIX}/complaints/{complaint.id}/approve",
            json={"notes": "Approved."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ComplaintStatus.APPROVED.value
    assert body["approved_by_id"] == str(admin_user.id)


async def test_admin_creates_work_order_and_converts_complaint(
    db_session: AsyncSession,
) -> None:
    admin_user, _, _, complaint = await _approved_complaint(db_session)

    async with api_client(db_session, actor_for(admin_user)) as client:
        response = await client.post(
            f"{PREFIX}/work-orders",
            json={
                "complaint_id": str(complaint.id),
                "title": "Repair inverter",
                "description": "Investigate the fault.",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == WorkOrderStatus.DRAFT.value
    assert body["complaint_id"] == str(complaint.id)

    await db_session.refresh(complaint)
    assert complaint.status is ComplaintStatus.CONVERTED_TO_WORK_ORDER


async def test_non_admin_cannot_create_work_order(
    db_session: AsyncSession,
) -> None:
    _, customer_user, _, complaint = await _approved_complaint(db_session)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/work-orders",
            json={
                "complaint_id": str(complaint.id),
                "title": "Repair inverter",
                "description": "Investigate the fault.",
            },
        )

    assert response.status_code == 403


async def test_duplicate_equipment_serial_returns_conflict(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    await create_equipment(
        db_session,
        customer_user.customer,
        manufacturer="SolarEdge",
        serial_number="SN-DUP",
    )

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/equipment",
            json={
                "manufacturer": "SolarEdge",
                "model": "SE10K",
                "equipment_type": "solar_inverter",
                "serial_number": "SN-DUP",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_resource"


async def test_admin_equipment_registration_requires_customer(
    db_session: AsyncSession,
) -> None:
    admin_user = await create_admin(db_session)

    async with api_client(db_session, actor_for(admin_user)) as client:
        response = await client.post(
            f"{PREFIX}/equipment",
            json={
                "manufacturer": "SolarEdge",
                "model": "SE10K",
                "equipment_type": "solar_inverter",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "domain_validation_error"


async def test_complaint_list_is_scoped_to_customer(
    db_session: AsyncSession,
) -> None:
    first = await create_customer(db_session)
    second = await create_customer(db_session)
    await create_complaint(db_session, first.customer)
    await create_complaint(db_session, second.customer)

    async with api_client(db_session, actor_for(first)) as client:
        response = await client.get(f"{PREFIX}/complaints")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


async def test_invalid_payload_returns_validation_error(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/complaints",
            json={"description": "", "channel": "web"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_pagination_limit_is_capped(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.get(f"{PREFIX}/complaints?limit=500")

    assert response.status_code == 422


async def test_technician_accepts_assignment_via_api(
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
    assignment = await create_assignment(
        db_session,
        work_order,
        technician_user.technician,
    )

    async with api_client(db_session, actor_for(technician_user)) as client:
        response = await client.post(
            f"{PREFIX}/assignments/{assignment.id}/accept",
        )

    assert response.status_code == 200
    body = response.json()
    assert body["assignment_status"] == (
        TechnicianAssignmentStatus.ACCEPTED.value
    )
    assert body["accepted_at"] is not None


async def test_admin_reassigns_work_order_via_api(
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
    first = await create_technician(db_session)
    second = await create_technician(db_session)
    previous = await create_assignment(
        db_session,
        work_order,
        first.technician,
        status=TechnicianAssignmentStatus.ACCEPTED,
    )

    async with api_client(db_session, actor_for(admin_user)) as client:
        response = await client.post(
            f"{PREFIX}/work-orders/{work_order.id}/reassign",
            json={"technician_id": str(second.technician.id)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["technician_id"] == str(second.technician.id)
    assert body["assignment_status"] == (
        TechnicianAssignmentStatus.OFFERED.value
    )

    await db_session.refresh(previous)
    assert previous.assignment_status is TechnicianAssignmentStatus.WITHDRAWN


async def test_customer_message_uses_authenticated_sender(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(db_session, customer_user.customer)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/conversations/{conversation.id}/messages",
            json={
                "sender_type": "customer",
                "content": "The inverter is offline.",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["sender_user_id"] == str(customer_user.id)


async def test_customer_cannot_send_admin_message_via_api(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    conversation = await create_conversation(db_session, customer_user.customer)

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/conversations/{conversation.id}/messages",
            json={"sender_type": "admin", "content": "Hello"},
        )

    assert response.status_code == 403


async def test_technician_cannot_read_unrelated_work_order(
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
        status=WorkOrderStatus.APPROVED,
        admin=admin_user,
    )
    technician_user = await create_technician(db_session)

    async with api_client(db_session, actor_for(technician_user)) as client:
        response = await client.get(
            f"{PREFIX}/work-orders/{work_order.id}",
        )

    assert response.status_code == 404


async def test_complaint_response_exposes_status_after_submit(
    db_session: AsyncSession,
) -> None:
    customer_user = await create_customer(db_session)
    complaint = await create_complaint(
        db_session,
        customer_user.customer,
        status=ComplaintStatus.DRAFT,
    )

    async with api_client(db_session, actor_for(customer_user)) as client:
        response = await client.post(
            f"{PREFIX}/complaints/{complaint.id}/submit",
        )

    assert response.status_code == 200
    assert response.json()["status"] == (
        ComplaintStatus.PENDING_APPROVAL.value
    )
    stored = await db_session.get(Complaint, complaint.id)
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.status is ComplaintStatus.PENDING_APPROVAL

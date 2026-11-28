from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    get_actor_context,
    get_current_customer,
    require_admin_user,
    require_customer_user,
)
from app.api.serializers import (
    complaint_response,
    customer_profile_response,
    equipment_response,
)
from app.db.session import get_db_session
from app.models.customer import Customer
from app.models.user import User
from app.schemas.complaint import ComplaintListResponse
from app.schemas.conversation import ConversationListResponse
from app.schemas.customer import CustomerProfileResponse, CustomerUpdate
from app.schemas.equipment import EquipmentListResponse
from app.schemas.work_order import WorkOrderListResponse
from app.services.complaints import complaints as complaint_service
from app.services.conversations import conversations as conversation_service
from app.services.customers.customers import (
    get_customer_for_admin,
    update_customer_profile,
)
from app.services.equipment import equipment as equipment_service
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.work_orders import work_orders as work_order_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "/me",
    response_model=CustomerProfileResponse,
    summary="Current customer's profile",
)
async def read_own_customer_profile(
    current_user: User = Depends(require_customer_user),
    customer: Customer = Depends(get_current_customer),
) -> CustomerProfileResponse:
    return customer_profile_response(customer, current_user)


@router.patch(
    "/me",
    response_model=CustomerProfileResponse,
    summary="Update current customer's profile",
)
async def update_own_customer_profile(
    payload: CustomerUpdate,
    current_user: User = Depends(require_customer_user),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db_session),
) -> CustomerProfileResponse:
    updated = await update_customer_profile(session, customer, payload)
    await session.commit()
    await session.refresh(updated)

    logger.info(
        "Customer profile updated",
        extra={
            "event": "customer_profile_updated",
            "actor_id": str(current_user.id),
            "customer_id": str(updated.id),
        },
    )
    return customer_profile_response(updated, current_user)


@router.get(
    "/{customer_id}",
    response_model=CustomerProfileResponse,
    summary="Admin: read any customer profile",
)
async def read_customer_profile_for_admin(
    customer_id: uuid.UUID,
    _: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> CustomerProfileResponse:
    customer = await get_customer_for_admin(session, customer_id)
    return customer_profile_response(customer)


@router.get(
    "/me/equipment",
    response_model=EquipmentListResponse,
    summary="List the authenticated customer's equipment",
)
async def list_own_equipment(
    pagination: Pagination = Depends(pagination_params),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentListResponse:
    items, total = await equipment_service.list_customer_equipment(
        session,
        customer.id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return EquipmentListResponse(
        items=[equipment_response(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/me/complaints",
    response_model=ComplaintListResponse,
    summary="List the authenticated customer's complaints",
)
async def list_own_complaints(
    pagination: Pagination = Depends(pagination_params),
    _: User = Depends(require_customer_user),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintListResponse:
    items, total = await complaint_service.list_complaints(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return ComplaintListResponse(
        items=[complaint_response(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/me/conversations",
    response_model=ConversationListResponse,
    summary="List the authenticated customer's conversations",
)
async def list_own_conversations(
    pagination: Pagination = Depends(pagination_params),
    _: User = Depends(require_customer_user),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await conversation_service.list_conversations(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get(
    "/me/work-orders",
    response_model=WorkOrderListResponse,
    summary="List the authenticated customer's work orders",
)
async def list_own_work_orders(
    pagination: Pagination = Depends(pagination_params),
    _: User = Depends(require_customer_user),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await work_order_service.list_work_orders(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }

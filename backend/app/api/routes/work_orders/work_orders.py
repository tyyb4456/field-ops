from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.db.session import get_db_session
from app.models.enums import Priority, WorkOrderStatus
from app.schemas.work_order import (
    WorkOrderComplete,
    WorkOrderCreate,
    WorkOrderListResponse,
    WorkOrderResponse,
    WorkOrderUpdate,
)
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.shared.transactions import commit
from app.services.work_orders import work_orders as work_order_service

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])


@router.post(
    "",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Administrator: create a work order from an approved complaint",
)
async def create_work_order(
    payload: WorkOrderCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.create_work_order(
        session,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(work_order)
    return WorkOrderResponse.model_validate(work_order)


@router.get(
    "",
    response_model=WorkOrderListResponse,
    summary="List work orders",
)
async def list_work_orders(
    customer_id: uuid.UUID | None = Query(default=None),
    work_order_status: WorkOrderStatus | None = Query(
        default=None,
        alias="status",
    ),
    priority: Priority | None = Query(default=None),
    equipment_id: uuid.UUID | None = Query(default=None),
    complaint_id: uuid.UUID | None = Query(default=None),
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await work_order_service.list_work_orders(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
        customer_id=customer_id,
        status=work_order_status,
        priority=priority,
        equipment_id=equipment_id,
        complaint_id=complaint_id,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    summary="Retrieve a work order",
)
async def read_work_order(
    work_order_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
    )
    return WorkOrderResponse.model_validate(work_order)


@router.patch(
    "/{work_order_id}",
    response_model=WorkOrderResponse,
    summary="Administrator: update work order details",
)
async def update_work_order(
    work_order_id: uuid.UUID,
    payload: WorkOrderUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    updated = await work_order_service.update_work_order(
        session,
        work_order,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(updated)
    return WorkOrderResponse.model_validate(updated)


@router.post(
    "/{work_order_id}/approve",
    response_model=WorkOrderResponse,
    summary="Administrator: approve a work order",
)
async def approve_work_order(
    work_order_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    approved = await work_order_service.approve_work_order(
        session,
        work_order,
        actor,
    )
    await commit(session)
    await session.refresh(approved)
    return WorkOrderResponse.model_validate(approved)


@router.post(
    "/{work_order_id}/cancel",
    response_model=WorkOrderResponse,
    summary="Administrator: cancel a work order",
)
async def cancel_work_order(
    work_order_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    cancelled = await work_order_service.cancel_work_order(
        session,
        work_order,
        actor,
    )
    await commit(session)
    await session.refresh(cancelled)
    return WorkOrderResponse.model_validate(cancelled)


@router.post(
    "/{work_order_id}/start",
    response_model=WorkOrderResponse,
    summary="Technician: start assigned work",
)
async def start_work_order(
    work_order_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    started = await work_order_service.start_work_order(
        session,
        work_order,
        actor,
    )
    await commit(session)
    await session.refresh(started)
    return WorkOrderResponse.model_validate(started)


@router.post(
    "/{work_order_id}/hold",
    response_model=WorkOrderResponse,
    summary="Place in-progress work on hold",
)
async def hold_work_order(
    work_order_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    held = await work_order_service.hold_work_order(
        session,
        work_order,
        actor,
    )
    await commit(session)
    await session.refresh(held)
    return WorkOrderResponse.model_validate(held)


@router.post(
    "/{work_order_id}/resume",
    response_model=WorkOrderResponse,
    summary="Resume work that is on hold",
)
async def resume_work_order(
    work_order_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    resumed = await work_order_service.resume_work_order(
        session,
        work_order,
        actor,
    )
    await commit(session)
    await session.refresh(resumed)
    return WorkOrderResponse.model_validate(resumed)


@router.post(
    "/{work_order_id}/complete",
    response_model=WorkOrderResponse,
    summary="Complete assigned work with completion information",
)
async def complete_work_order(
    work_order_id: uuid.UUID,
    payload: WorkOrderComplete,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> WorkOrderResponse:
    work_order = await work_order_service.get_work_order_for_actor(
        session,
        work_order_id,
        actor,
        for_update=True,
    )
    completed = await work_order_service.complete_work_order(
        session,
        work_order,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(completed)
    return WorkOrderResponse.model_validate(completed)

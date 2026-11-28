from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.api.serializers import complaint_response
from app.db.session import get_db_session
from app.models.enums import ComplaintStatus, Priority
from app.schemas.complaint import (
    ComplaintApprove,
    ComplaintCreate,
    ComplaintListResponse,
    ComplaintReject,
    ComplaintResponse,
    ComplaintUpdate,
)
from app.services.complaints import complaints as complaint_service
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.shared.transactions import commit

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="File a complaint",
)
async def create_complaint(
    payload: ComplaintCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.create_complaint(
        session,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(complaint)
    return complaint_response(complaint)


@router.get(
    "",
    response_model=ComplaintListResponse,
    summary="List complaints",
)
async def list_complaints(
    customer_id: uuid.UUID | None = Query(default=None),
    complaint_status: ComplaintStatus | None = Query(
        default=None,
        alias="status",
    ),
    priority: Priority | None = Query(default=None),
    equipment_id: uuid.UUID | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintListResponse:
    items, total = await complaint_service.list_complaints(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
        customer_id=customer_id,
        status=complaint_status,
        priority=priority,
        equipment_id=equipment_id,
        created_from=created_from,
        created_to=created_to,
    )
    return ComplaintListResponse(
        items=[complaint_response(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="Retrieve a complaint",
)
async def read_complaint(
    complaint_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
    )
    return complaint_response(complaint)


@router.patch(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="Update permitted complaint fields",
)
async def update_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
        for_update=True,
    )
    updated = await complaint_service.update_complaint(
        session,
        complaint,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(updated)
    return complaint_response(updated)


@router.post(
    "/{complaint_id}/submit",
    response_model=ComplaintResponse,
    summary="Submit a complaint for review",
)
async def submit_complaint(
    complaint_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
        for_update=True,
    )
    submitted = await complaint_service.submit_complaint(
        session,
        complaint,
        actor,
    )
    await commit(session)
    await session.refresh(submitted)
    return complaint_response(submitted)


@router.post(
    "/{complaint_id}/approve",
    response_model=ComplaintResponse,
    summary="Administrator: approve a complaint",
)
async def approve_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintApprove,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
        for_update=True,
    )
    approved = await complaint_service.approve_complaint(
        session,
        complaint,
        actor,
        notes=payload.notes,
    )
    await commit(session)
    await session.refresh(approved)
    return complaint_response(approved)


@router.post(
    "/{complaint_id}/reject",
    response_model=ComplaintResponse,
    summary="Administrator: reject a complaint",
)
async def reject_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintReject,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
        for_update=True,
    )
    rejected = await complaint_service.reject_complaint(
        session,
        complaint,
        actor,
        rejection_reason=payload.rejection_reason,
    )
    await commit(session)
    await session.refresh(rejected)
    return complaint_response(rejected)


@router.post(
    "/{complaint_id}/investigate",
    response_model=ComplaintResponse,
    summary="Administrator: start complaint investigation",
)
async def start_complaint_investigation(
    complaint_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
        for_update=True,
    )
    investigating = await complaint_service.start_investigation(
        session,
        complaint,
        actor,
    )
    await commit(session)
    await session.refresh(investigating)
    return complaint_response(investigating)


@router.post(
    "/{complaint_id}/cancel",
    response_model=ComplaintResponse,
    summary="Cancel a complaint while its state permits it",
)
async def cancel_complaint(
    complaint_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ComplaintResponse:
    complaint = await complaint_service.get_complaint_for_actor(
        session,
        complaint_id,
        actor,
        for_update=True,
    )
    cancelled = await complaint_service.cancel_complaint(
        session,
        complaint,
        actor,
    )
    await commit(session)
    await session.refresh(cancelled)
    return complaint_response(cancelled)

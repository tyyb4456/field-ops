from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.db.session import get_db_session
from app.models.enums import TechnicianAssignmentStatus
from app.schemas.technician_assignment import (
    AssignmentReject,
    ReassignRequest,
    TechnicianAssignmentCreate,
    TechnicianAssignmentListResponse,
    TechnicianAssignmentResponse,
)
from app.services.assignments import assignments as assignment_service
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.shared.transactions import commit

router = APIRouter(tags=["Technician Assignments"])


@router.post(
    "/work-orders/{work_order_id}/assignments",
    response_model=TechnicianAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Administrator: offer a work order to a technician",
)
async def create_assignment(
    work_order_id: uuid.UUID,
    payload: TechnicianAssignmentCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> TechnicianAssignmentResponse:
    assignment = await assignment_service.create_assignment(
        session,
        actor,
        work_order_id,
        payload,
    )
    await commit(session)
    await session.refresh(assignment)
    return TechnicianAssignmentResponse.model_validate(assignment)


@router.get(
    "/assignments",
    response_model=TechnicianAssignmentListResponse,
    summary="List technician assignments",
)
async def list_assignments(
    work_order_id: uuid.UUID | None = Query(default=None),
    technician_id: uuid.UUID | None = Query(default=None),
    assignment_status: TechnicianAssignmentStatus | None = Query(
        default=None,
        alias="status",
    ),
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await assignment_service.list_assignments(
        session,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
        work_order_id=work_order_id,
        technician_id=technician_id,
        status=assignment_status,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get(
    "/assignments/{assignment_id}",
    response_model=TechnicianAssignmentResponse,
    summary="Retrieve a technician assignment",
)
async def read_assignment(
    assignment_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> TechnicianAssignmentResponse:
    assignment = await assignment_service.get_assignment_for_actor(
        session,
        assignment_id,
        actor,
    )
    return TechnicianAssignmentResponse.model_validate(assignment)


@router.post(
    "/assignments/{assignment_id}/accept",
    response_model=TechnicianAssignmentResponse,
    summary="Technician: accept an offered assignment",
)
async def accept_assignment(
    assignment_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> TechnicianAssignmentResponse:
    assignment = await assignment_service.get_assignment_for_actor(
        session,
        assignment_id,
        actor,
        for_update=True,
    )
    accepted = await assignment_service.accept_assignment(
        session,
        assignment,
        actor,
    )
    await commit(session)
    await session.refresh(accepted)
    return TechnicianAssignmentResponse.model_validate(accepted)


@router.post(
    "/assignments/{assignment_id}/reject",
    response_model=TechnicianAssignmentResponse,
    summary="Technician: reject an offered assignment",
)
async def reject_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentReject,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> TechnicianAssignmentResponse:
    assignment = await assignment_service.get_assignment_for_actor(
        session,
        assignment_id,
        actor,
        for_update=True,
    )
    rejected = await assignment_service.reject_assignment(
        session,
        assignment,
        actor,
        rejection_reason=payload.rejection_reason,
    )
    await commit(session)
    await session.refresh(rejected)
    return TechnicianAssignmentResponse.model_validate(rejected)


@router.post(
    "/work-orders/{work_order_id}/reassign",
    response_model=TechnicianAssignmentResponse,
    summary="Administrator: reassign a work order to another technician",
)
async def reassign_work_order(
    work_order_id: uuid.UUID,
    payload: ReassignRequest,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> TechnicianAssignmentResponse:
    assignment = await assignment_service.reassign_work_order(
        session,
        actor,
        work_order_id,
        payload,
    )
    await commit(session)
    await session.refresh(assignment)
    return TechnicianAssignmentResponse.model_validate(assignment)

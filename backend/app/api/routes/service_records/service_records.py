from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.db.session import get_db_session
from app.schemas.service_record import (
    ServiceRecordCreate,
    ServiceRecordResponse,
)
from app.services.service_records import service_records as service_record_service
from app.services.shared.actor import ActorContext
from app.services.shared.transactions import commit

router = APIRouter(prefix="/service-records", tags=["Service Records"])


@router.post(
    "",
    response_model=ServiceRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a service record",
)
async def create_service_record(
    payload: ServiceRecordCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ServiceRecordResponse:
    record = await service_record_service.create_service_record(
        session,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(record)
    return ServiceRecordResponse.model_validate(record)


@router.get(
    "/{service_record_id}",
    response_model=ServiceRecordResponse,
    summary="Retrieve a service record",
)
async def read_service_record(
    service_record_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> ServiceRecordResponse:
    record = await service_record_service.get_service_record_for_actor(
        session,
        service_record_id,
        actor,
    )
    return ServiceRecordResponse.model_validate(record)

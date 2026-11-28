from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.api.serializers import equipment_response
from app.db.session import get_db_session
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentResponse,
    EquipmentStatusUpdate,
    EquipmentUpdate,
)
from app.schemas.service_record import ServiceRecordListResponse
from app.services.equipment import equipment as equipment_service
from app.services.service_records import service_records as service_record_service
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.shared.transactions import commit

router = APIRouter(prefix="/equipment", tags=["Equipment"])


@router.post(
    "",
    response_model=EquipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register equipment",
)
async def register_equipment(
    payload: EquipmentCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentResponse:
    equipment = await equipment_service.create_equipment(
        session,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(equipment)
    return equipment_response(equipment)


@router.get(
    "/{equipment_id}",
    response_model=EquipmentResponse,
    summary="Retrieve equipment details",
)
async def read_equipment(
    equipment_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentResponse:
    equipment = await equipment_service.get_equipment_for_actor(
        session,
        equipment_id,
        actor,
    )
    return equipment_response(equipment)


@router.patch(
    "/{equipment_id}",
    response_model=EquipmentResponse,
    summary="Update equipment information",
)
async def update_equipment(
    equipment_id: uuid.UUID,
    payload: EquipmentUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentResponse:
    equipment = await equipment_service.get_equipment_for_actor(
        session,
        equipment_id,
        actor,
        for_update=True,
    )
    updated = await equipment_service.update_equipment(
        session,
        equipment,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(updated)
    return equipment_response(updated)


@router.patch(
    "/{equipment_id}/status",
    response_model=EquipmentResponse,
    summary="Change equipment operational status",
)
async def change_equipment_status(
    equipment_id: uuid.UUID,
    payload: EquipmentStatusUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentResponse:
    equipment = await equipment_service.get_equipment_for_actor(
        session,
        equipment_id,
        actor,
        for_update=True,
    )
    updated = await equipment_service.change_operational_status(
        session,
        equipment,
        actor,
        payload.operational_status,
    )
    await commit(session)
    await session.refresh(updated)
    return equipment_response(updated)


@router.get(
    "/{equipment_id}/service-records",
    response_model=ServiceRecordListResponse,
    summary="List equipment service history",
)
async def list_equipment_service_records(
    equipment_id: uuid.UUID,
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await service_record_service.list_equipment_service_records(
        session,
        equipment_id,
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

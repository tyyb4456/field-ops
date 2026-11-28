from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context
from app.db.session import get_db_session
from app.schemas.equipment_document import (
    EquipmentDocumentCreate,
    EquipmentDocumentListResponse,
    EquipmentDocumentProcessingUpdate,
    EquipmentDocumentResponse,
    EquipmentDocumentUpdate,
)
from app.services.equipment_documents import (
    equipment_documents as document_service,
)
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params
from app.services.shared.transactions import commit

router = APIRouter(prefix="/equipment", tags=["Equipment Documents"])


@router.post(
    "/{equipment_id}/documents",
    response_model=EquipmentDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register equipment document metadata",
)
async def register_equipment_document(
    equipment_id: uuid.UUID,
    payload: EquipmentDocumentCreate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentDocumentResponse:
    document = await document_service.create_document(
        session,
        actor,
        equipment_id,
        payload,
    )
    await commit(session)
    await session.refresh(document)
    return EquipmentDocumentResponse.model_validate(document)


@router.get(
    "/{equipment_id}/documents",
    response_model=EquipmentDocumentListResponse,
    summary="List equipment documents",
)
async def list_equipment_documents(
    equipment_id: uuid.UUID,
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await document_service.list_documents(
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


@router.get(
    "/{equipment_id}/documents/{document_id}",
    response_model=EquipmentDocumentResponse,
    summary="Retrieve equipment document metadata",
)
async def read_equipment_document(
    equipment_id: uuid.UUID,
    document_id: uuid.UUID,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentDocumentResponse:
    document = await document_service.get_document_for_actor(
        session,
        equipment_id,
        document_id,
        actor,
    )
    return EquipmentDocumentResponse.model_validate(document)


@router.patch(
    "/{equipment_id}/documents/{document_id}",
    response_model=EquipmentDocumentResponse,
    summary="Update equipment document metadata",
)
async def update_equipment_document(
    equipment_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: EquipmentDocumentUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentDocumentResponse:
    document = await document_service.get_document_for_actor(
        session,
        equipment_id,
        document_id,
        actor,
    )
    updated = await document_service.update_document(
        session,
        document,
        actor,
        payload,
    )
    await commit(session)
    await session.refresh(updated)
    return EquipmentDocumentResponse.model_validate(updated)


@router.patch(
    "/{equipment_id}/documents/{document_id}/processing-status",
    response_model=EquipmentDocumentResponse,
    summary="Change document processing status",
)
async def change_equipment_document_processing_status(
    equipment_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: EquipmentDocumentProcessingUpdate,
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> EquipmentDocumentResponse:
    document = await document_service.get_document_for_actor(
        session,
        equipment_id,
        document_id,
        actor,
    )
    updated = await document_service.change_processing_status(
        session,
        document,
        actor,
        processing_status=payload.processing_status,
        processing_error=payload.processing_error,
    )
    await commit(session)
    await session.refresh(updated)
    return EquipmentDocumentResponse.model_validate(updated)

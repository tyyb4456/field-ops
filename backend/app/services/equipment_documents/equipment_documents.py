from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DocumentProcessingStatus
from app.models.equipment import Equipment
from app.models.equipment_document import EquipmentDocument
from app.schemas.equipment_document import (
    EquipmentDocumentCreate,
    EquipmentDocumentUpdate,
)
from app.services.shared.access import (
    get_equipment_or_404,
    require_admin,
    technician_has_equipment_access,
)
from app.services.shared.actor import ActorContext
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import (
    ConflictError,
    DuplicateResourceError,
    ForbiddenError,
    NotFoundError,
)
from app.services.shared.transactions import flush

_PROCESSING_TRANSITIONS: dict[
    DocumentProcessingStatus,
    set[DocumentProcessingStatus],
] = {
    DocumentProcessingStatus.PENDING: {
        DocumentProcessingStatus.PROCESSING,
        DocumentProcessingStatus.FAILED,
    },
    DocumentProcessingStatus.PROCESSING: {
        DocumentProcessingStatus.READY,
        DocumentProcessingStatus.FAILED,
    },
    DocumentProcessingStatus.FAILED: {
        DocumentProcessingStatus.PENDING,
    },
    DocumentProcessingStatus.READY: set(),
}


def _authorize_equipment_read(
    equipment: Equipment,
    actor: ActorContext,
) -> None:
    if actor.is_admin:
        return
    if actor.is_customer and equipment.customer_id == actor.customer_id:
        return
    raise AccessDeniedError("Equipment not found")


def _authorize_document_write(
    equipment: Equipment,
    actor: ActorContext,
) -> None:
    if actor.is_admin:
        return
    if actor.is_customer and equipment.customer_id == actor.customer_id:
        return
    raise ForbiddenError(
        "You do not have permission to manage equipment documents."
    )


async def _assert_unique_document(
    session: AsyncSession,
    *,
    manufacturer: str,
    model: str,
    title: str,
    version: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    conditions: list[Any] = [
        EquipmentDocument.manufacturer == manufacturer,
        EquipmentDocument.model == model,
        EquipmentDocument.title == title,
    ]
    if version is None:
        conditions.append(EquipmentDocument.version.is_(None))
    else:
        conditions.append(EquipmentDocument.version == version)

    stmt = select(EquipmentDocument.id).where(*conditions)
    if exclude_id is not None:
        stmt = stmt.where(EquipmentDocument.id != exclude_id)

    if await session.scalar(stmt.limit(1)) is not None:
        raise DuplicateResourceError(
            "A document with the same manufacturer, model, title and version "
            "already exists."
        )


async def create_document(
    session: AsyncSession,
    actor: ActorContext,
    equipment_id: uuid.UUID,
    data: EquipmentDocumentCreate,
) -> EquipmentDocument:
    equipment = await get_equipment_or_404(session, equipment_id)
    _authorize_document_write(equipment, actor)

    manufacturer = (data.manufacturer or equipment.manufacturer).strip()
    model = (data.model or equipment.model).strip()
    if not manufacturer or not model:
        raise ForbiddenError("Document manufacturer and model are required.")

    await _assert_unique_document(
        session,
        manufacturer=manufacturer,
        model=model,
        title=data.title,
        version=data.version,
    )

    document = EquipmentDocument(
        equipment_id=equipment.id,
        manufacturer=manufacturer,
        model=model,
        title=data.title,
        document_type=data.document_type,
        storage_uri=data.storage_uri,
        mime_type=data.mime_type,
        file_size=data.file_size,
        version=data.version,
        processing_status=DocumentProcessingStatus.PENDING,
        uploaded_by_id=actor.user_id,
    )
    session.add(document)
    await flush(session)
    return document


async def get_document_for_actor(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    document_id: uuid.UUID,
    actor: ActorContext,
) -> EquipmentDocument:
    equipment = await get_equipment_or_404(session, equipment_id)

    document = (
        await session.execute(
            select(EquipmentDocument).where(
                EquipmentDocument.id == document_id,
                EquipmentDocument.equipment_id == equipment.id,
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise NotFoundError("Equipment document not found.")

    if actor.is_admin:
        return document
    if actor.is_customer and equipment.customer_id == actor.customer_id:
        return document
    if (
        actor.is_technician
        and actor.technician_id is not None
        and await technician_has_equipment_access(
            session,
            actor.technician_id,
            equipment.id,
        )
    ):
        return document

    raise AccessDeniedError("Equipment document not found")


async def list_documents(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    actor: ActorContext,
    *,
    limit: int,
    offset: int,
) -> tuple[list[EquipmentDocument], int]:
    equipment = await get_equipment_or_404(session, equipment_id)

    if not actor.is_admin:
        is_owner = (
            actor.is_customer
            and equipment.customer_id == actor.customer_id
        )
        is_assigned_technician = (
            actor.is_technician
            and actor.technician_id is not None
            and await technician_has_equipment_access(
                session,
                actor.technician_id,
                equipment.id,
            )
        )
        if not (is_owner or is_assigned_technician):
            raise AccessDeniedError("Equipment not found")

    conditions: list[Any] = [EquipmentDocument.equipment_id == equipment.id]
    total = await session.scalar(
        select(func.count())
        .select_from(EquipmentDocument)
        .where(*conditions)
    )
    items = (
        await session.scalars(
            select(EquipmentDocument)
            .where(*conditions)
            .order_by(
                EquipmentDocument.uploaded_at.desc(),
                EquipmentDocument.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


async def update_document(
    session: AsyncSession,
    document: EquipmentDocument,
    actor: ActorContext,
    data: EquipmentDocumentUpdate,
) -> EquipmentDocument:
    if document.equipment_id is None:
        require_admin(actor)
    else:
        equipment = await get_equipment_or_404(
            session,
            document.equipment_id,
        )
        _authorize_document_write(equipment, actor)

    fields = data.model_fields_set
    title = data.title if "title" in fields and data.title else document.title
    version = data.version if "version" in fields else document.version

    if "title" in fields or "version" in fields:
        await _assert_unique_document(
            session,
            manufacturer=document.manufacturer,
            model=document.model,
            title=title,
            version=version,
            exclude_id=document.id,
        )

    if "title" in fields and data.title is not None:
        document.title = data.title
    if "document_type" in fields and data.document_type is not None:
        document.document_type = data.document_type
    if "storage_uri" in fields:
        document.storage_uri = data.storage_uri
    if "mime_type" in fields:
        document.mime_type = data.mime_type
    if "file_size" in fields:
        document.file_size = data.file_size
    if "version" in fields:
        document.version = data.version

    await flush(session)
    return document


async def change_processing_status(
    session: AsyncSession,
    document: EquipmentDocument,
    actor: ActorContext,
    *,
    processing_status: DocumentProcessingStatus,
    processing_error: str | None = None,
) -> EquipmentDocument:
    require_admin(actor)

    if processing_status is document.processing_status:
        return document

    allowed = _PROCESSING_TRANSITIONS[document.processing_status]
    if processing_status not in allowed:
        raise ConflictError(
            "Invalid document processing status transition."
        )

    document.processing_status = processing_status
    if processing_status is DocumentProcessingStatus.FAILED:
        document.processing_error = processing_error
    elif processing_status is DocumentProcessingStatus.READY:
        document.processing_error = None

    await flush(session)
    return document


__all__ = [
    "change_processing_status",
    "create_document",
    "get_document_for_actor",
    "list_documents",
    "update_document",
]

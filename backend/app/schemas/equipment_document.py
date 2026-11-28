from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.models.enums import (
    DocumentProcessingStatus,
    EquipmentDocumentType,
)
from app.schemas.common import ORMModel, StrictRequest


class EquipmentDocumentCreate(StrictRequest):
    manufacturer: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    title: str = Field(min_length=1, max_length=255)
    document_type: EquipmentDocumentType = EquipmentDocumentType.OTHER
    storage_uri: str | None = Field(default=None, max_length=2_000)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None, ge=0)
    version: str | None = Field(default=None, max_length=50)


class EquipmentDocumentUpdate(StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    document_type: EquipmentDocumentType | None = None
    storage_uri: str | None = Field(default=None, max_length=2_000)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None, ge=0)
    version: str | None = Field(default=None, max_length=50)


class EquipmentDocumentProcessingUpdate(StrictRequest):
    processing_status: DocumentProcessingStatus
    processing_error: str | None = Field(default=None, max_length=5_000)


class EquipmentDocumentResponse(ORMModel):
    id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    manufacturer: str
    model: str
    title: str
    document_type: EquipmentDocumentType
    storage_uri: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    version: str | None = None
    processing_status: DocumentProcessingStatus
    processing_error: str | None = None
    uploaded_by_id: uuid.UUID | None = None
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime


class EquipmentDocumentListResponse(ORMModel):
    items: list[EquipmentDocumentResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "EquipmentDocumentCreate",
    "EquipmentDocumentListResponse",
    "EquipmentDocumentProcessingUpdate",
    "EquipmentDocumentResponse",
    "EquipmentDocumentUpdate",
]

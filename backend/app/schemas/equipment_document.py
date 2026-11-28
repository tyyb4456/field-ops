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
    equipment_id: uuid.UUID | None = None
    manufacturer: str = Field(min_length=1, max_length=150)
    model: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=255)
    document_type: EquipmentDocumentType = EquipmentDocumentType.OTHER
    storage_uri: str | None = None
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None, ge=0)
    version: str | None = Field(default=None, max_length=50)


class EquipmentDocumentUpdate(StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    document_type: EquipmentDocumentType | None = None
    storage_uri: str | None = None
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int | None = Field(default=None, ge=0)
    version: str | None = Field(default=None, max_length=50)
    processing_status: DocumentProcessingStatus | None = None
    processing_error: str | None = None


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

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UpdatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    DocumentProcessingStatus,
    EquipmentDocumentType,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.user import User


class EquipmentDocument(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    __tablename__ = "equipment_documents"
    __table_args__ = (
        UniqueConstraint(
            "manufacturer",
            "model",
            "title",
            "version",
            name="uq_equipment_documents_manufacturer_model_title_version",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="file_size_non_negative",
        ),
        Index(
            "ix_equipment_documents_equipment_id",
            "equipment_id",
        ),
        Index(
            "ix_equipment_documents_processing_status",
            "processing_status",
        ),
        Index(
            "ix_equipment_documents_manufacturer_model",
            "manufacturer",
            "model",
        ),
    )

    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
    )
    manufacturer: Mapped[str] = mapped_column(String(150), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[EquipmentDocumentType] = mapped_column(
        enum_type(
            EquipmentDocumentType,
            "equipment_document_type",
            length=30,
        ),
        nullable=False,
        default=EquipmentDocumentType.OTHER,
        server_default=EquipmentDocumentType.OTHER.value,
    )
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        enum_type(
            DocumentProcessingStatus,
            "document_processing_status",
            length=20,
        ),
        nullable=False,
        default=DocumentProcessingStatus.PENDING,
        server_default=DocumentProcessingStatus.PENDING.value,
    )
    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    equipment: Mapped[Equipment | None] = relationship(
        back_populates="documents",
    )
    uploaded_by: Mapped[User | None] = relationship(
        foreign_keys=[uploaded_by_id],
    )

    def __repr__(self) -> str:
        return f"EquipmentDocument(id={self.id!r}, title={self.title!r})"

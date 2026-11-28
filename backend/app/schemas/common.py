from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base response model that can be populated from SQLAlchemy entities."""

    model_config = ConfigDict(from_attributes=True)


class StrictRequest(BaseModel):
    """Base request model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class Page[T](BaseModel):
    """Consistent pagination envelope used by collection endpoints."""

    items: list[T]
    total: int
    limit: int
    offset: int


__all__ = ["ORMModel", "Page", "StrictRequest"]

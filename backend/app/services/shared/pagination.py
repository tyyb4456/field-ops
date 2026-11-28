from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    offset: int


def pagination_params(
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Maximum number of records to return.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip.",
    ),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "Pagination",
    "pagination_params",
]

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shared.errors import ConflictError, DuplicateResourceError


async def commit(session: AsyncSession) -> None:
    """Commit the request transaction, translating constraint failures.

    Routes own the transaction boundary. Lower-level service helpers only
    flush; this helper is the single place where a commit-time integrity
    failure is converted into a safe domain error so raw database details
    never reach clients.
    """

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateResourceError(
            "The operation conflicts with existing data."
        ) from exc


async def flush(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "The operation conflicts with existing data."
        ) from exc


__all__ = ["commit", "flush"]

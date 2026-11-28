from __future__ import annotations

from fastapi import status


class DomainError(Exception):
    """Base class for deterministic domain/business errors.

    Services raise these errors; the API exception layer translates them into
    consistent HTTP responses. Services never deal with HTTP concerns.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.headers = headers or {}


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ForbiddenError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class DuplicateResourceError(ConflictError):
    code = "duplicate_resource"


class InvalidStateTransitionError(ConflictError):
    code = "invalid_state_transition"


class DomainValidationError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "domain_validation_error"


__all__ = [
    "ConflictError",
    "DomainError",
    "DomainValidationError",
    "DuplicateResourceError",
    "ForbiddenError",
    "InvalidStateTransitionError",
    "NotFoundError",
]

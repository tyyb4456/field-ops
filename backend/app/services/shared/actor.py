from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.enums import UserRole


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Authenticated caller resolved from server-side account state.

    Client-supplied user, customer or technician identifiers are never trusted;
    routes build this context from the authenticated user and pass it to
    services, which perform the resource-level authorization checks.
    """

    user_id: uuid.UUID
    role: UserRole
    customer_id: uuid.UUID | None = None
    technician_id: uuid.UUID | None = None

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    @property
    def is_customer(self) -> bool:
        return self.role is UserRole.CUSTOMER

    @property
    def is_technician(self) -> bool:
        return self.role is UserRole.TECHNICIAN


__all__ = ["ActorContext"]

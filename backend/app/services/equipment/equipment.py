from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.enums import EquipmentOperationalStatus
from app.models.equipment import Equipment
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate
from app.services.shared.access import (
    get_equipment_or_404,
    require_customer,
    technician_has_equipment_access,
)
from app.services.shared.actor import ActorContext
from app.services.shared.authorization import AccessDeniedError
from app.services.shared.errors import (
    ConflictError,
    DomainValidationError,
    DuplicateResourceError,
    ForbiddenError,
    NotFoundError,
)
from app.services.shared.transactions import flush

_STATUS_TRANSITIONS: dict[EquipmentOperationalStatus, set[EquipmentOperationalStatus]] = {
    EquipmentOperationalStatus.ACTIVE: {
        EquipmentOperationalStatus.DEGRADED,
        EquipmentOperationalStatus.OFFLINE,
        EquipmentOperationalStatus.DECOMMISSIONED,
    },
    EquipmentOperationalStatus.DEGRADED: {
        EquipmentOperationalStatus.ACTIVE,
        EquipmentOperationalStatus.OFFLINE,
        EquipmentOperationalStatus.DECOMMISSIONED,
    },
    EquipmentOperationalStatus.OFFLINE: {
        EquipmentOperationalStatus.ACTIVE,
        EquipmentOperationalStatus.DEGRADED,
        EquipmentOperationalStatus.DECOMMISSIONED,
    },
    EquipmentOperationalStatus.DECOMMISSIONED: set(),
}

_TECHNICIAN_STATUS_TARGETS = {
    EquipmentOperationalStatus.ACTIVE,
    EquipmentOperationalStatus.DEGRADED,
    EquipmentOperationalStatus.OFFLINE,
}


async def _assert_serial_available(
    session: AsyncSession,
    *,
    manufacturer: str,
    serial_number: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if serial_number is None:
        return
    stmt = select(Equipment.id).where(
        Equipment.manufacturer == manufacturer,
        Equipment.serial_number == serial_number,
    )
    if exclude_id is not None:
        stmt = stmt.where(Equipment.id != exclude_id)
    existing = await session.scalar(stmt.limit(1))
    if existing is not None:
        raise DuplicateResourceError(
            "Equipment with this manufacturer and serial number already exists."
        )


async def _resolve_owner_customer_id(
    session: AsyncSession,
    actor: ActorContext,
    requested_customer_id: uuid.UUID | None,
) -> uuid.UUID:
    if actor.is_admin:
        if requested_customer_id is None:
            raise DomainValidationError(
                "customer_id is required when an administrator registers equipment."
            )
        customer = await session.get(Customer, requested_customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        return customer.id

    customer_id = require_customer(actor)
    if requested_customer_id is not None and requested_customer_id != customer_id:
        raise ForbiddenError(
            "You cannot register equipment for another customer."
        )
    return customer_id


async def create_equipment(
    session: AsyncSession,
    actor: ActorContext,
    data: EquipmentCreate,
) -> Equipment:
    customer_id = await _resolve_owner_customer_id(
        session,
        actor,
        data.customer_id,
    )

    if actor.is_customer:
        if data.operational_status is not EquipmentOperationalStatus.ACTIVE:
            raise ForbiddenError(
                "Customers cannot set the operational status on registration."
            )
        operational_status = EquipmentOperationalStatus.ACTIVE
    else:
        operational_status = data.operational_status

    await _assert_serial_available(
        session,
        manufacturer=data.manufacturer,
        serial_number=data.serial_number,
    )

    equipment = Equipment(
        customer_id=customer_id,
        manufacturer=data.manufacturer,
        model=data.model,
        serial_number=data.serial_number,
        equipment_type=data.equipment_type,
        installation_date=data.installation_date,
        location=data.location,
        operational_status=operational_status,
    )
    session.add(equipment)
    await flush(session)
    return equipment


async def get_equipment_for_actor(
    session: AsyncSession,
    equipment_id: uuid.UUID,
    actor: ActorContext,
    *,
    for_update: bool = False,
) -> Equipment:
    equipment = await get_equipment_or_404(
        session,
        equipment_id,
        for_update=for_update,
    )

    if actor.is_admin:
        return equipment

    if actor.is_customer:
        if equipment.customer_id != actor.customer_id:
            raise AccessDeniedError("Equipment not found")
        return equipment

    if (
        actor.is_technician
        and actor.technician_id is not None
        and await technician_has_equipment_access(
            session,
            actor.technician_id,
            equipment.id,
        )
    ):
        return equipment

    raise AccessDeniedError("Equipment not found")


async def update_equipment(
    session: AsyncSession,
    equipment: Equipment,
    actor: ActorContext,
    data: EquipmentUpdate,
) -> Equipment:
    if not actor.is_admin:
        if not actor.is_customer or equipment.customer_id != actor.customer_id:
            raise AccessDeniedError("Equipment not found")
        if equipment.operational_status is EquipmentOperationalStatus.DECOMMISSIONED:
            raise ConflictError(
                "Decommissioned equipment cannot be modified."
            )

    fields = data.model_fields_set
    manufacturer = (
        data.manufacturer
        if "manufacturer" in fields and data.manufacturer is not None
        else equipment.manufacturer
    )
    serial_number = (
        data.serial_number
        if "serial_number" in fields
        else equipment.serial_number
    )

    if "manufacturer" in fields or "serial_number" in fields:
        await _assert_serial_available(
            session,
            manufacturer=manufacturer,
            serial_number=serial_number,
            exclude_id=equipment.id,
        )

    if "manufacturer" in fields and data.manufacturer is not None:
        equipment.manufacturer = data.manufacturer
    if "model" in fields and data.model is not None:
        equipment.model = data.model
    if "serial_number" in fields:
        equipment.serial_number = data.serial_number
    if "equipment_type" in fields and data.equipment_type is not None:
        equipment.equipment_type = data.equipment_type
    if "installation_date" in fields:
        equipment.installation_date = data.installation_date
    if "location" in fields:
        equipment.location = data.location

    await flush(session)
    return equipment


async def change_operational_status(
    session: AsyncSession,
    equipment: Equipment,
    actor: ActorContext,
    new_status: EquipmentOperationalStatus,
) -> Equipment:
    if equipment.operational_status is new_status:
        return equipment

    if actor.is_admin:
        allowed = _STATUS_TRANSITIONS[equipment.operational_status]
        if new_status not in allowed:
            raise ConflictError(
                "Invalid equipment operational status transition."
            )
    elif actor.is_technician:
        if actor.technician_id is None or not await technician_has_equipment_access(
            session,
            actor.technician_id,
            equipment.id,
        ):
            raise AccessDeniedError("Equipment not found")
        if new_status not in _TECHNICIAN_STATUS_TARGETS:
            raise ForbiddenError(
                "Technicians cannot decommission equipment."
            )
        if equipment.operational_status is EquipmentOperationalStatus.DECOMMISSIONED:
            raise ConflictError(
                "Decommissioned equipment cannot change status."
            )
    else:
        raise ForbiddenError(
            "You do not have permission to change equipment status."
        )

    equipment.operational_status = new_status
    await flush(session)
    return equipment


async def list_customer_equipment(
    session: AsyncSession,
    customer_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    status: EquipmentOperationalStatus | None = None,
) -> tuple[list[Equipment], int]:
    conditions = [Equipment.customer_id == customer_id]
    if status is not None:
        conditions.append(Equipment.operational_status == status)

    total = await session.scalar(
        select(func.count()).select_from(Equipment).where(*conditions)
    )
    items = (
        await session.scalars(
            select(Equipment)
            .where(*conditions)
            .order_by(Equipment.created_at.desc(), Equipment.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(items), int(total or 0)


__all__ = [
    "change_operational_status",
    "create_equipment",
    "get_equipment_for_actor",
    "list_customer_equipment",
    "update_equipment",
]

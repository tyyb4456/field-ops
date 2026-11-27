from __future__ import annotations

from app.models.customer import Customer
from app.models.equipment import Equipment

from app.models.user import User
from app.schemas.user import UserMeResponse
from app.schemas.customer import CustomerProfileResponse
from app.schemas.equipment import EquipmentResponse


def user_me_response(user: User) -> UserMeResponse:
    return UserMeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        customer_id=(
            user.customer.id if user.customer is not None else None
        ),
        technician_id=(
            user.technician.id if user.technician is not None else None
        ),
    )


def customer_profile_response(
    customer: Customer,
    user: User | None = None,
) -> CustomerProfileResponse:
    owner = user if user is not None else customer.user
    return CustomerProfileResponse(
        id=customer.id,
        full_name=owner.full_name,
        email=owner.email,
        phone=owner.phone,
        address=customer.address,
        preferred_language=customer.preferred_language,
        is_active=owner.is_active,
        created_at=customer.created_at,
    )


def equipment_response(equipment: Equipment) -> EquipmentResponse:
    return EquipmentResponse(
        id=equipment.id,
        customer_id=equipment.customer_id,
        manufacturer=equipment.manufacturer,
        model=equipment.model,
        serial_number=equipment.serial_number,
        equipment_type=equipment.equipment_type,
        installation_date=equipment.installation_date,
        created_at=equipment.created_at,
    )





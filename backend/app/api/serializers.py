from __future__ import annotations

from app.models.complaint import Complaint
from app.models.customer import Customer
from app.models.equipment import Equipment
from app.models.user import User
from app.schemas.complaint import ComplaintResponse
from app.schemas.customer import CustomerProfileResponse
from app.schemas.equipment import EquipmentResponse
from app.schemas.user import UserMeResponse


def user_me_response(user: User) -> UserMeResponse:
    return UserMeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        customer_id=(user.customer.id if user.customer is not None else None),
        technician_id=(user.technician.id if user.technician is not None else None),
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
        location=equipment.location,
        operational_status=equipment.operational_status,
        created_at=equipment.created_at,
        updated_at=equipment.updated_at,
    )


def complaint_response(complaint: Complaint) -> ComplaintResponse:
    return ComplaintResponse(
        id=complaint.id,
        customer_id=complaint.customer_id,
        equipment_id=complaint.equipment_id,
        origin_conversation_id=complaint.origin_conversation_id,
        description=complaint.description,
        reported_symptoms=complaint.reported_symptoms,
        reported_error_code=complaint.reported_error_code,
        channel=complaint.channel,
        status=complaint.status,
        priority=complaint.priority,
        submitted_at=complaint.submitted_at,
        approved_by_id=complaint.approved_by_id,
        approved_at=complaint.approved_at,
        approval_notes=complaint.approval_notes,
        rejection_reason=complaint.rejection_reason,
        closed_at=complaint.closed_at,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
    )

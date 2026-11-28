from __future__ import annotations

from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.equipment import Equipment
from app.models.equipment_document import EquipmentDocument
from app.models.message import Message
from app.models.service_record import ServiceRecord
from app.models.technician import Technician
from app.models.technician_assignment import TechnicianAssignment
from app.models.user import User
from app.models.work_order import WorkOrder

__all__ = [
    "Complaint",
    "Conversation",
    "Customer",
    "Equipment",
    "EquipmentDocument",
    "Message",
    "ServiceRecord",
    "Technician",
    "TechnicianAssignment",
    "User",
    "WorkOrder",
]

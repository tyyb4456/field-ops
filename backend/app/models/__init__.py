from __future__ import annotations

from app.models.complaint import Complaint
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.equipment import Equipment
from app.models.technician import Technician
from app.models.technician_assignment import TechnicianAssignment
from app.models.user import User

__all__ = [
    "Complaint",
    "Conversation",
    "Customer",
    "Equipment",
    "Technician",
    "TechnicianAssignment",
    "User",
]

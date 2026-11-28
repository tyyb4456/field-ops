from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.accounts import auth as accounts_auth
from app.api.routes.accounts import users as accounts_users
from app.api.routes.assignments import assignments as assignment_routes
from app.api.routes.complaints import complaints as complaint_routes
from app.api.routes.conversations import conversations as conversation_routes
from app.api.routes.customers import customers as customer_routes
from app.api.routes.equipment import documents as document_routes
from app.api.routes.equipment import equipment as equipment_routes
from app.api.routes.service_records import service_records as service_record_routes
from app.api.routes.technicians import technicians as technician_routes
from app.api.routes.work_orders import work_orders as work_order_routes

api_router = APIRouter()
api_router.include_router(accounts_auth.router)
api_router.include_router(accounts_users.router)
api_router.include_router(customer_routes.router)
api_router.include_router(equipment_routes.router)
api_router.include_router(document_routes.router)
api_router.include_router(conversation_routes.router)
api_router.include_router(complaint_routes.router)
api_router.include_router(work_order_routes.router)
api_router.include_router(assignment_routes.router)
api_router.include_router(service_record_routes.router)
api_router.include_router(technician_routes.router)

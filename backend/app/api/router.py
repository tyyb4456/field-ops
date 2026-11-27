from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.accounts import auth as accounts_auth
from app.api.routes.accounts import users as accounts_users
from app.api.routes.customers import customers as customer_routes

api_router = APIRouter()
api_router.include_router(accounts_auth.router)
api_router.include_router(accounts_users.router)
api_router.include_router(customer_routes.router)

# Complaint routes are intentionally not registered in Phase 1: the complaint
# schemas and service layer are still placeholders. They will be wired in when
# the domain model and complaint service are implemented.

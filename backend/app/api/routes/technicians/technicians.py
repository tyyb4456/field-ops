from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_actor_context, get_current_technician
from app.db.session import get_db_session
from app.models.technician import Technician
from app.schemas.service_record import ServiceRecordListResponse
from app.services.service_records import service_records as service_record_service
from app.services.shared.actor import ActorContext
from app.services.shared.pagination import Pagination, pagination_params

router = APIRouter(prefix="/technicians", tags=["Technicians"])


@router.get(
    "/me/service-records",
    response_model=ServiceRecordListResponse,
    summary="List the authenticated technician's service records",
)
async def list_own_service_records(
    technician: Technician = Depends(get_current_technician),
    pagination: Pagination = Depends(pagination_params),
    actor: ActorContext = Depends(get_actor_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    items, total = await service_record_service.list_technician_service_records(
        session,
        technician.id,
        actor,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import Environment, settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    RequestBodyLimitMiddleware,
    RequestContextMiddleware,
)
from app.db.session import dispose_engine, verify_database_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting %s v%s in %s mode",
        settings.app_name,
        settings.app_version,
        settings.environment.value,
    )

    if settings.environment is not Environment.TEST:
        if await verify_database_connection():
            logger.info("Database connectivity verified")
        else:
            logger.warning(
                "Database is not reachable at startup; readiness will report "
                "not_ready until it becomes available"
            )

    try:
        yield
    finally:
        logger.info("Shutting down %s", settings.app_name)
        await dispose_engine()
        logger.info("Database engine disposed")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous field-service coordination platform.",
        debug=settings.debug,
        lifespan=lifespan,
    )

    application.add_middleware(RequestBodyLimitMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(application)

    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()

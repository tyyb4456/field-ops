from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.core.config import settings
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _async_url() -> str:
    configured = os.environ.get("TEST_DATABASE_URL")
    return configured or settings.database_url


def _sync_url(url: str, database: str | None = None) -> URL:
    parsed = make_url(url)
    return parsed.set(
        drivername="postgresql+psycopg2",
        database=database if database is not None else parsed.database,
    )


def _create_database(url: str) -> str:
    database_name = f"fieldops_test_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(
        _sync_url(url, "postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()

    return (
        make_url(url).set(database=database_name).render_as_string(hide_password=False)
    )


def _drop_database(url: str) -> None:
    parsed = make_url(url)
    admin_engine = create_engine(
        _sync_url(url, "postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name "
                    "AND pid <> pg_backend_pid()"
                ),
                {"database_name": parsed.database},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{parsed.database}"'))
    finally:
        admin_engine.dispose()


def _alembic_config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _upgrade(url: str) -> None:
    command.upgrade(_alembic_config(url), "head")


def _new_ephemeral_database() -> str:
    url = _async_url()
    try:
        return _create_database(url)
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL is not available for integration tests: {exc}")


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    configured = os.environ.get("TEST_DATABASE_URL")
    created = configured is None
    url = configured or _new_ephemeral_database()
    try:
        _upgrade(url)
    except Exception:
        if created:
            _drop_database(url)
        raise
    try:
        yield url
    finally:
        if created:
            _drop_database(url)


@pytest.fixture()
def fresh_database_url() -> Iterator[str]:
    url = _new_ephemeral_database()
    try:
        yield url
    finally:
        _drop_database(url)


@pytest.fixture()
async def db_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            session = AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                await session.close()
                await transaction.rollback()
    finally:
        await engine.dispose()

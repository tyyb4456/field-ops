from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"

EXPECTED_TABLES = {
    "users",
    "customers",
    "technicians",
    "equipment",
    "conversations",
    "complaints",
    "messages",
    "work_orders",
    "technician_assignments",
    "service_records",
    "equipment_documents",
}


def _config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _sync_engine(url: str):
    parsed = make_url(url).set(drivername="postgresql+psycopg2")
    return create_engine(parsed, poolclass=NullPool)


def test_alembic_configuration_loads() -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))

    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0001_initial_domain_model"]


def test_initial_migration_upgrade_and_downgrade(
    fresh_database_url: str,
) -> None:
    config = _config(fresh_database_url)

    command.upgrade(config, "head")
    command.check(config)

    engine = _sync_engine(fresh_database_url)
    try:
        inspector = inspect(engine)
        assert EXPECTED_TABLES <= set(inspector.get_table_names())
        with engine.connect() as connection:
            extensions = {
                row[0]
                for row in connection.execute(text("SELECT extname FROM pg_extension"))
            }
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert "vector" in extensions
        assert revision == "0001_initial_domain_model"
    finally:
        engine.dispose()

    command.downgrade(config, "base")

    engine = _sync_engine(fresh_database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            extensions = {
                row[0]
                for row in connection.execute(text("SELECT extname FROM pg_extension"))
            }
        assert not (EXPECTED_TABLES & tables)
        assert "vector" in extensions
    finally:
        engine.dispose()

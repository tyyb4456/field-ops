from __future__ import annotations

from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401 - registers all model classes
from app.db.base import Base

EXPECTED_TABLES = {
    "users",
    "customers",
    "equipment",
    "complaints",
    "conversations",
    "technicians",
    "technician_assignments",
}


def test_all_models_register_expected_tables() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_sqlalchemy_mappers_configure_successfully() -> None:
    configure_mappers()

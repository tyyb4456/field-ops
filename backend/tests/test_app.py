from __future__ import annotations

from app.core.config import settings
from app.main import app


def test_application_imports_with_metadata() -> None:
    assert app.title == settings.app_name
    assert app.version == settings.app_version


def test_application_initializes_in_test_environment() -> None:
    assert settings.environment.value == "test"


def test_api_router_registers_expected_paths() -> None:
    paths = set(app.openapi()["paths"])

    assert "/health" in paths
    assert "/health/ready" in paths
    assert f"{settings.api_v1_prefix}/auth/bootstrap" in paths
    assert f"{settings.api_v1_prefix}/users/me" in paths
    assert f"{settings.api_v1_prefix}/customers/me" in paths
    assert f"{settings.api_v1_prefix}/customers/{{customer_id}}" in paths

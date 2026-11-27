from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppError, register_exception_handlers


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/app-error")
    async def raise_app_error() -> None:
        raise AppError(
            "Teapot",
            status_code=418,
            code="teapot",
        )

    @test_app.get("/validate")
    async def validate(count: int) -> dict[str, int]:
        return {"count": count}

    @test_app.get("/unhandled")
    async def raise_unhandled() -> None:
        raise RuntimeError("boom")

    return test_app


def test_app_error_handler_returns_consistent_payload() -> None:
    client = TestClient(_build_test_app())

    response = client.get("/app-error")

    assert response.status_code == 418
    assert response.json() == {
        "error": {"code": "teapot", "message": "Teapot"},
    }


def test_validation_error_handler_returns_consistent_payload() -> None:
    client = TestClient(_build_test_app())

    response = client.get("/validate", params={"count": "not-an-int"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"]


def test_http_error_handler_returns_consistent_payload() -> None:
    client = TestClient(_build_test_app())

    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "http_error", "message": "Not Found"},
    }


def test_unhandled_error_handler_hides_internal_details() -> None:
    client = TestClient(_build_test_app(), raise_server_exceptions=False)

    response = client.get("/unhandled")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
        },
    }

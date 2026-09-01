"""Contract tests for the Stage 0 FastAPI service."""

from fastapi.testclient import TestClient

from config.settings import load_settings
from services.health_service.main import SERVICE_VERSION, create_app


def test_root_and_health_endpoints_share_the_documented_contract() -> None:
    """Both Stage 0 endpoints should return a validated, stable response shape."""

    app = create_app(load_settings("dev", environ={}))
    expected = {
        "service": "AegisQuant",
        "status": "ok",
        "version": SERVICE_VERSION,
        "environment": "development",
    }

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").json() == expected
        assert client.get("/health").status_code == 200
        assert client.get("/health").json() == expected


def test_openapi_documents_both_stage_zero_endpoints() -> None:
    """FastAPI should expose the Stage 0 endpoints through its generated contract."""

    app = create_app(load_settings("prod", environ={}))

    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert schema["info"]["version"] == SERVICE_VERSION
    assert set(schema["paths"]) == {"/", "/health"}

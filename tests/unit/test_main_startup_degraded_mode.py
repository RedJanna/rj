import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.unit
def test_create_app_returns_degraded_health_when_critical_env_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = create_app()
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "degraded"
    assert data.get("startup_error") == "RuntimeError"
    assert "OPENAI_API_KEY" in (data.get("startup_error_message") or "")

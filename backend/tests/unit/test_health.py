from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health_endpoint() -> None:
    """The public health endpoint should be available without special setup."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "0.1.0"
    assert payload["db"] in {"ok", "down"}

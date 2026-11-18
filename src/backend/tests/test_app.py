from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_expected_status_and_body() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.content == b'{"status":"ok"}'
    assert response.json() == {"status": "ok"}


def test_unknown_route_returns_not_found() -> None:
    response = client.get("/not-a-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}

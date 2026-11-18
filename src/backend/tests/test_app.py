import logging

import app.main as main
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

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


def test_process_health_does_not_require_database(
    monkeypatch,
) -> None:
    def database_unavailable() -> None:
        raise SQLAlchemyError("synthetic database connection failure")

    monkeypatch.setattr(main, "check_database_connection", database_unavailable)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_returns_safe_unavailable_response(monkeypatch, caplog) -> None:
    def database_unavailable() -> None:
        raise SQLAlchemyError(
            "postgresql://test-user:synthetic-password@localhost/gradtrack_test"
        )

    monkeypatch.setattr(main, "check_database_connection", database_unavailable)

    with caplog.at_level(logging.ERROR):
        response = client.get("/health/database")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "synthetic-password" not in response.text
    assert "synthetic-password" not in caplog.text

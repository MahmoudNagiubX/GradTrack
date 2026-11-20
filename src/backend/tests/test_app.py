import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import app.main as main
import app.submissions as submissions
import pytest
from app.main import app
from app.schemas import SubmissionVersionResponse
from app.submissions import get_submission_writer_access
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

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


def test_auth_validation_error_does_not_echo_submitted_password() -> None:
    submitted_password = "synthetic-private-password-value"
    response = client.post(
        "/auth/register",
        json={
            "email": "synthetic@example.com",
            "display_name": "Synthetic Student",
            "password": [submitted_password],
        },
    )

    assert response.status_code == 422
    assert submitted_password not in response.text
    assert "input" not in response.text


def test_submission_url_validation_does_not_echo_embedded_credentials(
    monkeypatch,
) -> None:
    app.dependency_overrides[get_submission_writer_access] = lambda: None
    credential = "synthetic-private-url-password"
    try:
        response = client.post(
            "/teams/00000000-0000-0000-0000-000000000001/milestones/"
            "00000000-0000-0000-0000-000000000002/submissions/link",
            json={"url": f"https://synthetic:{credential}@example.org/srs"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert credential not in response.text
    assert "input" not in response.text


def test_submission_openapi_describes_json_and_multipart_routes() -> None:
    paths = app.openapi()["paths"]
    link_request = paths["/teams/{team_id}/milestones/{milestone_id}/submissions/link"][
        "post"
    ]["requestBody"]
    file_request = paths["/teams/{team_id}/milestones/{milestone_id}/submissions/file"][
        "post"
    ]["requestBody"]
    file_schema = file_request["content"]["multipart/form-data"]["schema"]

    assert "application/json" in link_request["content"]
    assert "multipart/form-data" in file_request["content"]
    assert file_schema["required"] == ["file"]
    assert file_schema["properties"]["file"] == {
        "type": "string",
        "format": "binary",
    }
    assert not any("approve" in path or "return" in path for path in paths)


def test_file_route_parses_one_multipart_file_and_rejects_extra_parts(
    monkeypatch, tmp_path
) -> None:
    version = SubmissionVersionResponse(
        id=UUID(int=1),
        submission_id=UUID(int=2),
        milestone_id=UUID(int=3),
        team_id=UUID(int=4),
        version_number=1,
        submitted_by=UUID(int=5),
        submitted_at=datetime(2026, 12, 1, 15, tzinfo=UTC),
        deadline_at_submission=datetime(2026, 12, 1, 15, tzinfo=UTC),
        is_late=False,
        source_type="file",
        original_filename="Synthetic-SRS.pdf",
        file_size_bytes=18,
        media_type="application/pdf",
        url=None,
        review_status="pending_review",
    )
    app.dependency_overrides[get_submission_writer_access] = lambda: None
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        submissions,
        "_create_initial_submission",
        lambda *_args, **_kwargs: version,
    )
    try:
        path = (
            "/teams/00000000-0000-0000-0000-000000000001/milestones/"
            "00000000-0000-0000-0000-000000000002/submissions/file"
        )
        accepted = client.post(
            path,
            files={
                "file": ("Synthetic-SRS.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")
            },
        )
        extra_part = client.post(
            path,
            data={"extra": "unexpected"},
            files={
                "file": ("Synthetic-SRS.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert accepted.status_code == 201
    assert accepted.json()["source_type"] == "file"
    assert extra_part.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_multipart_parser_enforces_body_limit_without_content_length(
    monkeypatch,
) -> None:
    monkeypatch.setattr(submissions, "MAX_FILE_SIZE_BYTES", 10)
    monkeypatch.setattr(submissions, "MAX_MULTIPART_OVERHEAD_BYTES", 0)
    body = b"x" * 11
    received = False

    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/submissions/file",
            "raw_path": b"/submissions/file",
            "query_string": b"",
            "root_path": "",
            "headers": [(b"content-type", b"multipart/form-data; boundary=synthetic")],
            "server": ("test", 80),
            "client": ("127.0.0.1", 12345),
        },
        receive,
    )

    async def parse_request() -> int:
        with pytest.raises(HTTPException) as rejected:
            async for _upload in submissions._single_file_upload(request):
                pass
        return rejected.value.status_code

    assert asyncio.run(parse_request()) == 413


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

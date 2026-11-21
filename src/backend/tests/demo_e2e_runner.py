"""Real HTTP End-to-End Demo Runner for GradTrack Local Demo Readiness.

Executes real HTTP requests against the live running FastAPI server on http://127.0.0.1:8000
using synthetic accounts, testing the complete course and productivity journeys,
negative security boundaries, and persistence across server restarts.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = "http://127.0.0.1:8000"


def encode_multipart(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----GradTrackFormBoundary{uuid4().hex}"
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    for key, (filename, content, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        disposition = (
            f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
        )
        body.extend(disposition.encode())
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


class HttpClient:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict | None = None,
        raw_body: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, dict | bytes, dict[str, str]]:
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif raw_body is not None:
            data = raw_body
            if content_type:
                headers["Content-Type"] = content_type

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                status_code = response.status
                resp_headers = {k.lower(): v for k, v in response.headers.items()}
                body_bytes = response.read()
                content_type_hdr = resp_headers.get("content-type", "")
                if "application/json" in content_type_hdr:
                    return (
                        status_code,
                        json.loads(body_bytes.decode("utf-8")),
                        resp_headers,
                    )
                try:
                    return (
                        status_code,
                        json.loads(body_bytes.decode("utf-8")),
                        resp_headers,
                    )
                except Exception:
                    return status_code, body_bytes, resp_headers
        except urllib.error.HTTPError as exc:
            body_bytes = exc.read()
            resp_headers = {k.lower(): v for k, v in exc.headers.items()}
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed = {"raw": body_bytes.decode("utf-8", errors="replace")}
            return exc.code, parsed, resp_headers


def provision_synthetic_roles() -> tuple[str, str, str]:
    """Safely provision supervisor and coordinator accounts via database fixture."""
    from app.database import engine
    from app.models import User
    from app.security import hash_password
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    sup_email = "demo.supervisor@example.edu"
    coord_email = "demo.coordinator@example.edu"
    unassigned_email = "demo.unassigned.sup@example.edu"
    default_pw = "GradTrackDemo123!"

    with Session(engine) as session:
        for email, role, name in [
            (sup_email, "supervisor", "Dr. Alan Turing"),
            (coord_email, "coordinator", "Prof. Grace Hopper"),
            (unassigned_email, "supervisor", "Dr. John von Neumann"),
        ]:
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    password_hash=hash_password(default_pw),
                    display_name=name,
                    system_role=role,
                    is_active=True,
                )
                session.add(user)
            else:
                user.system_role = role
                user.password_hash = hash_password(default_pw)
                user.is_active = True
        session.commit()

    return sup_email, coord_email, unassigned_email


def run_demo(
    is_persistence_check: bool = False, state_file: str = "demo_state.json"
) -> None:
    client = HttpClient()
    state_path = Path(state_file)

    if is_persistence_check:
        print("\n=== STEP 5.4: POST-RESTART PERSISTENCE VERIFICATION ===")
        assert state_path.exists(), "State file missing for persistence check"
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)

        # 1. Health check
        code, body, _ = client.request("GET", "/health")
        assert code == 200 and body.get("status") == "ok"
        print("[PASS] GET /health -> 200 OK")

        code, body, _ = client.request("GET", "/health/database")
        assert code == 200 and body.get("status") == "ok"
        print("[PASS] GET /health/database -> 200 OK")

        # 2. Re-login Student 1
        code, body, _ = client.request(
            "POST",
            "/auth/login",
            json_body={
                "email": state["student1_email"],
                "password": state["student_pw"],
            },
        )
        assert code == 200, f"Login failed: {body}"
        student1_token = body["access_token"]
        print("[PASS] Student 1 re-login successful after server restart")

        # 3. Verify Team persists
        team_id = state["team_id"]
        code, body, _ = client.request("GET", f"/teams/{team_id}", token=student1_token)
        assert code == 200, f"Team fetch failed: {body}"
        assert body["name"] == state["team_name"]
        print(f"[PASS] Team persisted: {body['name']} ({team_id})")

        # 4. Verify Milestone 1 and Download submission file
        ms1_id = state["ms1_id"]
        v2_id = state["ms1_v2_id"]
        code, content, headers = client.request(
            "GET",
            f"/teams/{team_id}/milestones/{ms1_id}/submissions/{v2_id}/download",
            token=student1_token,
        )
        assert code == 200, f"File download after restart failed: {code}"
        assert content == state["revised_file_bytes"].encode("latin1")
        print("[PASS] Milestone submission file download verified after restart")

        # 5. Verify Task, Comment, and Download task attachment
        task1_id = state["task1_id"]
        att_id = state["att_id"]
        code, body, _ = client.request(
            "GET", f"/teams/{team_id}/tasks/{task1_id}", token=student1_token
        )
        assert code == 200, f"Task fetch failed: {body}"
        print(f"[PASS] Task persisted: {body['title']} (status: {body['status']})")

        code, content, _ = client.request(
            "GET",
            f"/teams/{team_id}/tasks/{task1_id}/attachments/{att_id}/download",
            token=student1_token,
        )
        assert code == 200, f"Task attachment download failed: {code}"
        assert content == state["attachment_bytes"].encode("latin1")
        print("[PASS] Task attachment download verified after restart (byte-for-byte)")

        # 6. Verify Read receipt persists
        code, body, _ = client.request("GET", "/notifications", token=student1_token)
        assert code == 200
        rem_map = {i["id"]: i for i in body}
        marked_rem_id = state["marked_reminder_id"]
        if marked_rem_id in rem_map:
            assert rem_map[marked_rem_id]["is_read"] is True
            print(f"[PASS] In-app notification read receipt persisted: {marked_rem_id}")

        if "png_avatar_bytes" in state:
            code, me_prof, _ = client.request("GET", "/auth/me", token=student1_token)
            assert code == 200 and me_prof["has_avatar"] is True
            code, stream_av, _ = client.request(
                "GET", "/auth/me/avatar", token=student1_token
            )
            assert code == 200
            assert stream_av == state["png_avatar_bytes"].encode("latin1")
            print(
                "[PASS] User avatar persisted and stream verified across server restart"
            )

        print("\n>>> ALL PERSISTENCE CHECKS PASSED SUCCESSFULLY! <<<\n")
        return

    print("\n=== STARTING GRADTRACK REAL HTTP END-TO-END DEMO ===")

    # 1. Server Health
    code, body, _ = client.request("GET", "/health")
    assert code == 200 and body.get("status") == "ok", f"Health failed: {body}"
    print("[PASS] GET /health -> 200 OK", body)

    code, body, _ = client.request("GET", "/health/database")
    assert code == 200 and body.get("status") == "ok", f"DB Health failed: {body}"
    print("[PASS] GET /health/database -> 200 OK", body)

    code, _, _ = client.request("GET", "/docs")
    assert code == 200
    print("[PASS] GET /docs -> 200 OK (Swagger UI)")

    # 2. Provision synthetic supervisor & coordinator
    sup_email, coord_email, unassigned_email = provision_synthetic_roles()
    demo_pw = "GradTrackDemo123!"
    print(
        f"[PASS] Dev fixture prepared: {sup_email}, {coord_email}, {unassigned_email}"
    )

    # 3. Register students
    student1_email = f"student.lead.{uuid4().hex[:6]}@example.edu"
    student2_email = f"student.member.{uuid4().hex[:6]}@example.edu"
    student3_email = f"student.other.{uuid4().hex[:6]}@example.edu"

    for email, name in [
        (student1_email, "Alice Leader"),
        (student2_email, "Bob Member"),
        (student3_email, "Charlie Other"),
    ]:
        code, body, _ = client.request(
            "POST",
            "/auth/register",
            json_body={"email": email, "password": demo_pw, "display_name": name},
        )
        assert code == 201, f"Registration failed for {email}: {body}"
        assert body["system_role"] == "student"
        print(f"[PASS] Registered student: {email} ({body['display_name']})")

    # 4. Login all roles and verify /auth/me
    def login(email: str, pw: str) -> str:
        code, body, _ = client.request(
            "POST", "/auth/login", json_body={"email": email, "password": pw}
        )
        assert code == 200, f"Login failed for {email}: {body}"
        return body["access_token"]

    student1_token = login(student1_email, demo_pw)
    student2_token = login(student2_email, demo_pw)
    student3_token = login(student3_email, demo_pw)
    supervisor_token = login(sup_email, demo_pw)
    coordinator_token = login(coord_email, demo_pw)
    unassigned_token = login(unassigned_email, demo_pw)

    # Verify /auth/me
    code, me, _ = client.request("GET", "/auth/me", token=student1_token)
    assert code == 200 and me["system_role"] == "student"
    code, me_sup, _ = client.request("GET", "/auth/me", token=supervisor_token)
    assert code == 200 and me_sup["system_role"] == "supervisor"
    code, me_coord, _ = client.request("GET", "/auth/me", token=coordinator_token)
    assert code == 200 and me_coord["system_role"] == "coordinator"
    print("[PASS] Logged in all synthetic roles and verified GET /auth/me")

    # Negative Auth Check: Invalid token -> 401
    code, _, _ = client.request("GET", "/auth/me", token="invalid_token_12345")
    assert code == 401
    print("[PASS] Negative check: Invalid token -> 401 Unauthorized")

    # 5. Team Formation
    team_name = f"GradTrack Apollo {uuid4().hex[:4]}"
    code, team, _ = client.request(
        "POST", "/teams", token=student1_token, json_body={"name": team_name}
    )
    assert code == 201, f"Team creation failed: {team}"
    team_id = team["id"]
    print(f"[PASS] Team created: {team_name} (ID: {team_id})")

    # Add student 2 to team
    code, s2_me, _ = client.request("GET", "/auth/me", token=student2_token)
    s2_id = s2_me["id"]
    code, add_res, _ = client.request(
        "POST",
        f"/teams/{team_id}/members",
        token=student1_token,
        json_body={"user_id": s2_id},
    )
    assert code == 201, f"Add member failed: {add_res}"
    print(f"[PASS] Added Student 2 ({s2_id}) to Team")

    # Negative check: Student tries to assign supervisor -> 403 Forbidden
    code, sup_me, _ = client.request("GET", "/auth/me", token=supervisor_token)
    sup_id = sup_me["id"]
    code, _, _ = client.request(
        "PUT",
        f"/teams/{team_id}/supervisor",
        token=student1_token,
        json_body={"supervisor_id": sup_id},
    )
    assert code == 403
    print("[PASS] Negative check: Student self-assigning supervisor -> 403 Forbidden")

    # Coordinator assigns supervisor
    code, assign_res, _ = client.request(
        "PUT",
        f"/teams/{team_id}/supervisor",
        token=coordinator_token,
        json_body={"supervisor_id": sup_id},
    )
    assert code == 200
    print(f"[PASS] Coordinator assigned supervisor ({sup_id}) to Team")

    # 6. Milestones
    now_utc = datetime.now(timezone.utc)
    ms1_due = (now_utc + timedelta(days=5)).isoformat()
    code, ms1, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones",
        token=supervisor_token,
        json_body={
            "name": "SRS Document",
            "description": "System requirements",
            "due_at": ms1_due,
        },
    )
    assert code == 201
    ms1_id = ms1["id"]
    print(f"[PASS] Supervisor created Milestone 1: SRS Document (ID: {ms1_id})")

    ms2_due = (now_utc + timedelta(days=10)).isoformat()
    code, ms2, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones",
        token=coordinator_token,
        json_body={
            "name": "Architecture Design",
            "description": "High level architecture",
            "due_at": ms2_due,
        },
    )
    assert code == 201
    ms2_id = ms2["id"]
    print(f"[PASS] Coordinator created Milestone 2: Architecture Design (ID: {ms2_id})")

    # Student reads sorted milestones
    code, milestones_list, _ = client.request(
        "GET", f"/teams/{team_id}/milestones", token=student1_token
    )
    assert code == 200 and len(milestones_list) == 2
    print("[PASS] Student fetched sorted milestones list")

    # 7. Milestone Submissions
    # Initial File Submission for Milestone 1
    sample_file_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n%%EOF"
    body_data, content_type = encode_multipart(
        {},
        {"file": ("srs_report_v1.pdf", sample_file_bytes, "application/pdf")},
    )
    code, sub1_v1, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/file",
        token=student1_token,
        raw_body=body_data,
        content_type=content_type,
    )
    assert code == 201, f"File submission failed: {sub1_v1}"
    assert sub1_v1["version_number"] == 1
    assert sub1_v1["source_type"] == "file"
    assert sub1_v1["is_late"] is False
    assert sub1_v1["review_status"] == "pending_review"
    ms1_v1_id = sub1_v1["id"]
    print(f"[PASS] Student submitted Milestone 1 Version 1 File (ID: {ms1_v1_id})")

    # Authorized download of submitted file
    code, downloaded_bytes, _ = client.request(
        "GET",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/{ms1_v1_id}/download",
        token=student1_token,
    )
    assert code == 200, f"Download failed: {code}"
    assert downloaded_bytes == sample_file_bytes
    print("[PASS] Student downloaded submitted file with exact byte-for-byte parity")

    # Negative check: Student from other team cannot download file -> 404/403
    code, _, _ = client.request(
        "GET",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/{ms1_v1_id}/download",
        token=student3_token,
    )
    assert code in {403, 404}
    print("[PASS] Negative check: Foreign team student cannot download submission")

    # Initial Link Submission for Milestone 2
    code, sub2_v1, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms2_id}/submissions/link",
        token=student1_token,
        json_body={"url": "https://example.com/architecture-spec"},
    )
    assert code == 201
    assert sub2_v1["source_type"] == "link"
    print("[PASS] Student submitted Milestone 2 Link")

    # 8. Supervisor Review Journey
    # Supervisor pending reviews
    code, pending_reviews, _ = client.request(
        "GET", "/supervisor/submissions/pending", token=supervisor_token
    )
    assert code == 200, f"Pending reviews failed: {pending_reviews}"
    assert any(r["milestone_id"] == ms1_id for r in pending_reviews)
    print("[PASS] Supervisor sees Milestone 1 in pending reviews queue")

    # Negative check: Coordinator cannot review submission -> 403
    code, _, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/{ms1_v1_id}/review",
        token=coordinator_token,
        json_body={"decision": "approved", "feedback": "Looks good"},
    )
    assert code == 403
    print("[PASS] Negative check: Coordinator cannot approve/review -> 403 Forbidden")

    # Negative check: Unassigned supervisor cannot review submission -> 404 (or 403)
    code, _, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/{ms1_v1_id}/review",
        token=unassigned_token,
        json_body={"decision": "approved", "feedback": "Looks good"},
    )
    assert code in {403, 404}
    print("[PASS] Negative check: Unassigned supervisor cannot review -> 403/404")

    # Assigned supervisor returns submission with feedback
    code, review1, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/{ms1_v1_id}/review",
        token=supervisor_token,
        json_body={
            "decision": "returned",
            "feedback": "Needs functional requirements matrix and risk analysis",
        },
    )
    assert code == 201, f"Review return failed: {review1}"
    assert review1["decision"] == "returned"
    print("[PASS] Assigned supervisor RETURNED Version 1 with feedback")

    # Student resubmits revised file (Version 2)
    revised_file_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n% REVISION 2\n%%EOF"
    )
    revised_body, revised_ct = encode_multipart(
        {},
        {"file": ("srs_report_v2_final.pdf", revised_file_bytes, "application/pdf")},
    )
    code, sub1_v2, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/revisions/file",
        token=student1_token,
        raw_body=revised_body,
        content_type=revised_ct,
    )
    assert code == 201, f"Revision file failed: {sub1_v2}"
    assert sub1_v2["version_number"] == 2
    assert sub1_v2["review_status"] == "pending_review"
    ms1_v2_id = sub1_v2["id"]
    print(f"[PASS] Student resubmitted Version 2 File (ID: {ms1_v2_id})")

    # Supervisor approves Version 2
    code, review2, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms1_id}/submissions/{ms1_v2_id}/review",
        token=supervisor_token,
        json_body={
            "decision": "approved",
            "feedback": "All requirements addressed. Approved!",
        },
    )
    assert code == 201, f"Approval failed: {review2}"
    assert review2["decision"] == "approved"
    print("[PASS] Assigned supervisor APPROVED Version 2")

    # Late Boundary Demonstration
    past_due = (now_utc - timedelta(hours=2)).isoformat()
    code, ms_late, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones",
        token=supervisor_token,
        json_body={"name": "Past Deadline Milestone", "due_at": past_due},
    )
    assert code == 201
    ms_late_id = ms_late["id"]

    code, sub_late, _ = client.request(
        "POST",
        f"/teams/{team_id}/milestones/{ms_late_id}/submissions/link",
        token=student1_token,
        json_body={"url": "https://example.com/late-submission"},
    )
    assert code == 201
    assert sub_late["is_late"] is True
    print("[PASS] Late boundary demonstrated: submission marked is_late=True")

    # 9. Team Tasks Journey
    code, task1, _ = client.request(
        "POST",
        f"/teams/{team_id}/tasks",
        token=student1_token,
        json_body={
            "title": "Build Authentication Module",
            "description": "JWT and password hashing",
            "priority": "high",
            "due_at": (now_utc + timedelta(days=3)).isoformat(),
            "assignee_id": s2_id,
            "milestone_id": ms1_id,
        },
    )
    assert code == 201
    task1_id = task1["id"]
    print(f"[PASS] Created Task 1: Build Authentication Module (ID: {task1_id})")

    # Member transitions task: todo -> in_progress -> done
    code, t_patch1, _ = client.request(
        "PATCH",
        f"/teams/{team_id}/tasks/{task1_id}/status",
        token=student2_token,
        json_body={"status": "in_progress"},
    )
    assert code == 200 and t_patch1["status"] == "in_progress", (
        f"Status patch failed: {t_patch1}"
    )

    code, t_patch2, _ = client.request(
        "PATCH",
        f"/teams/{team_id}/tasks/{task1_id}/status",
        token=student2_token,
        json_body={"status": "done"},
    )
    assert code == 200 and t_patch2["status"] == "done", (
        f"Status patch to done failed: {t_patch2}"
    )
    print("[PASS] Member moved Task 1 from todo -> in_progress -> done")

    # Leader reopens task
    code, t_reopen, _ = client.request(
        "PATCH",
        f"/teams/{team_id}/tasks/{task1_id}/status",
        token=student1_token,
        json_body={"status": "in_progress"},
    )
    assert code == 200 and t_reopen["status"] == "in_progress"
    print("[PASS] Leader reopened Task 1 (in_progress)")

    # Checklist Item
    code, check_item, _ = client.request(
        "POST",
        f"/teams/{team_id}/tasks/{task1_id}/checklist",
        token=student1_token,
        json_body={"item_text": "Write unit tests for token expiration"},
    )
    assert code == 201, f"Checklist add failed: {check_item}"
    check_item_id = check_item["id"]

    code, check_patch, _ = client.request(
        "PATCH",
        f"/teams/{team_id}/tasks/{task1_id}/checklist/{check_item_id}",
        token=student2_token,
        json_body={"is_done": True},
    )
    assert code == 200 and check_patch["is_done"] is True
    print("[PASS] Checklist item added and marked complete")

    # Subtask
    code, subtask, _ = client.request(
        "POST",
        f"/teams/{team_id}/tasks",
        token=student1_token,
        json_body={
            "title": "Configure Argon2 hasher",
            "assignee_id": s2_id,
            "parent_task_id": task1_id,
        },
    )
    assert code == 201, f"Subtask creation failed: {subtask}"
    print("[PASS] Subtask created under Task 1")

    # 10. Comments and Attachments Journey
    code, comment, _ = client.request(
        "POST",
        f"/teams/{team_id}/tasks/{task1_id}/comments",
        token=student2_token,
        json_body={"content": "Completed Argon2 hasher setup and benchmarked."},
    )
    assert code == 201
    print("[PASS] Member posted comment on Task 1")

    # Attachment Upload
    attachment_bytes = b"Config payload: {rounds: 3, memory_cost: 65536}"
    att_body, att_ct = encode_multipart(
        {},
        {"file": ("argon2_benchmark.txt", attachment_bytes, "text/plain")},
    )
    code, attachment, _ = client.request(
        "POST",
        f"/teams/{team_id}/tasks/{task1_id}/attachments",
        token=student2_token,
        raw_body=att_body,
        content_type=att_ct,
    )
    assert code == 201
    att_id = attachment["id"]
    print(f"[PASS] Member uploaded attachment to Task 1 (ID: {att_id})")

    # Download attachment by Team Leader
    code, dl_att_bytes, _ = client.request(
        "GET",
        f"/teams/{team_id}/tasks/{task1_id}/attachments/{att_id}/download",
        token=student1_token,
    )
    assert code == 200
    assert dl_att_bytes == attachment_bytes
    print("[PASS] Leader downloaded attachment with exact byte parity")

    # Negative check: Foreign team student cannot download task attachment -> 404
    code, _, _ = client.request(
        "GET",
        f"/teams/{team_id}/tasks/{task1_id}/attachments/{att_id}/download",
        token=student3_token,
    )
    assert code in {403, 404}
    print("[PASS] Negative check: Foreign student rejected on attachment download")

    # 11. Calendar & Progress Dashboards
    start_q = (now_utc - timedelta(days=1)).isoformat()
    end_q = (now_utc + timedelta(days=14)).isoformat()
    query_str = urllib.parse.urlencode({"start_at": start_q, "end_at": end_q})
    code, cal, _ = client.request(
        "GET", f"/teams/{team_id}/calendar?{query_str}", token=student1_token
    )
    assert code == 200, f"Calendar fetch failed: {cal}"
    assert any(item["kind"] == "task" for item in cal)
    assert any(item["kind"] == "milestone" for item in cal)
    print(f"[PASS] Fetched calendar: {len(cal)} items (tasks and milestones)")

    code, progress, _ = client.request(
        "GET", f"/teams/{team_id}/progress", token=student1_token
    )
    assert code == 200, f"Progress fetch failed: {progress}"
    total_t = progress["tasks"]["total"]
    upcoming_count = len(progress["upcoming"])
    assert total_t >= 1
    print(f"[PASS] Team progress: total_tasks={total_t}, upcoming={upcoming_count}")

    code, sup_prog, _ = client.request(
        "GET", "/supervisor/teams/progress", token=supervisor_token
    )
    assert code == 200, f"Supervisor progress failed: {sup_prog}"
    assert any(t["team_id"] == team_id for t in sup_prog)
    print("[PASS] Supervisor progress overview shows Team 1")

    # 12. In-App Deadline Reminders (GT-30)
    code, notifs, _ = client.request("GET", "/notifications", token=student2_token)
    assert code == 200
    assert len(notifs) >= 1
    target_rem_id = notifs[0]["id"]
    print(
        f"[PASS] Student 2 fetched {len(notifs)} reminders (Target ID: {target_rem_id})"
    )

    # Mark reminder as read
    code, mark_res, _ = client.request(
        "POST", f"/notifications/{target_rem_id}/read", token=student2_token
    )
    assert code == 200
    assert mark_res["status"] == "ok"
    print(f"[PASS] Student 2 marked reminder {target_rem_id} as read")

    # Fetch with unread_only=true
    code, unread_notifs, _ = client.request(
        "GET", "/notifications?unread_only=true", token=student2_token
    )
    assert code == 200
    assert all(n["id"] != target_rem_id for n in unread_notifs)
    print("[PASS] unread_only=true correctly excludes marked reminder")

    # 13. GT-32 User Profiles & Avatars
    # Student 1 updates profile
    patch_body = {
        "display_name": "Student Leader (Updated)",
        "student_number": "2024-ENG-001",
        "faculty": "Faculty of Engineering",
        "department": "Computer Science",
        "academic_level": "Senior",
        "bio": "GradTrack demo lead developer",
    }
    code, updated_me, _ = client.request(
        "PATCH", "/auth/me", token=student1_token, json_body=patch_body
    )
    assert code == 200
    assert updated_me["display_name"] == "Student Leader (Updated)"
    assert updated_me["student_number"] == "2024-ENG-001"
    assert updated_me["faculty"] == "Faculty of Engineering"
    print("[PASS] Student 1 updated self-service profile (GT-32 PATCH /auth/me)")

    # Negative check: attempting to change system_role -> 422
    code, err_res, _ = client.request(
        "PATCH",
        "/auth/me",
        token=student1_token,
        json_body={"system_role": "coordinator"},
    )
    assert code == 422
    print("[PASS] Negative check: PATCH /auth/me with system_role rejected with 422")

    # Upload avatar (PNG)
    png_avatar = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    avatar_body, avatar_ct = encode_multipart(
        {},
        {"file": ("profile.png", png_avatar, "image/png")},
    )
    code, av_res, _ = client.request(
        "POST",
        "/auth/me/avatar",
        token=student1_token,
        raw_body=avatar_body,
        content_type=avatar_ct,
    )
    assert code == 200
    assert av_res["has_avatar"] is True
    print("[PASS] Student 1 uploaded profile avatar (GT-32 POST /auth/me/avatar)")

    # Stream own avatar
    code, streamed_avatar, av_hdrs = client.request(
        "GET", "/auth/me/avatar", token=student1_token
    )
    assert code == 200
    assert streamed_avatar == png_avatar
    assert av_hdrs.get("content-type") == "image/png"
    print("[PASS] Student 1 streamed own avatar (GT-32 GET /auth/me/avatar)")

    # Teammate (Student 2) reads Student 1 limited profile
    code, tm_prof, _ = client.request(
        "GET", f"/teams/{team_id}/members/{me['id']}/profile", token=student2_token
    )
    assert code == 200
    assert tm_prof["display_name"] == "Student Leader (Updated)"
    assert tm_prof["faculty"] == "Faculty of Engineering"
    assert tm_prof["has_avatar"] is True
    assert "student_number" not in tm_prof
    assert "email" not in tm_prof
    print(
        "[PASS] Student 2 read Student 1 team-scoped profile "
        "(GT-32 GET /teams/.../members/.../profile)"
    )

    # Teammate (Student 2) streams Student 1 avatar
    code, tm_av, tm_hdrs = client.request(
        "GET", f"/teams/{team_id}/members/{me['id']}/avatar", token=student2_token
    )
    assert code == 200
    assert tm_av == png_avatar
    assert tm_hdrs.get("content-type") == "image/png"
    print(
        "[PASS] Student 2 streamed Student 1 avatar "
        "(GT-32 GET /teams/.../members/.../avatar)"
    )

    # Unassigned supervisor reading Student 1 profile returns 404
    code, _, _ = client.request(
        "GET", f"/teams/{team_id}/members/{me['id']}/profile", token=unassigned_token
    )
    assert code == 404
    print("[PASS] Negative check: Unassigned supervisor blocked with 404")

    # Save state for persistence test
    state = {
        "student1_email": student1_email,
        "student2_email": student2_email,
        "student_pw": demo_pw,
        "team_id": team_id,
        "team_name": team_name,
        "ms1_id": ms1_id,
        "ms1_v2_id": ms1_v2_id,
        "revised_file_bytes": revised_file_bytes.decode("latin1"),
        "task1_id": task1_id,
        "att_id": att_id,
        "attachment_bytes": attachment_bytes.decode("latin1"),
        "marked_reminder_id": target_rem_id,
        "png_avatar_bytes": png_avatar.decode("latin1"),
    }
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)

    print("\n>>> ALL REAL HTTP DEMO JOURNEYS COMPLETED SUCCESSFULLY! <<<")
    print(f"State saved to {state_file} for server restart persistence verification.")


if __name__ == "__main__":
    is_check = "--check-persistence" in sys.argv
    run_demo(is_persistence_check=is_check)

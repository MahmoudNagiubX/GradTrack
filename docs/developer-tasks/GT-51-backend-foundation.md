# GT-51 — Backend Phase 0: FastAPI foundation

## Task information

| Field | Value |
|---|---|
| Jira issue | GT-51 |
| Target | Backend |
| Priority | High |
| Status | To Do |
| Target PR branch | `develop` |

## Objective

Establish a small, reproducible FastAPI foundation in `src/backend/` for later GradTrack backend phases. Phase 0 exposes only the health endpoint and developer setup; it does not claim that graduation-project workflows are implemented.

## Scope

### In scope

- Create a maintainable FastAPI application with `GET /health` returning HTTP 200 and exactly `{"status":"ok"}`.
- Add environment-based settings with safe defaults, basic request/error logging, and the framework's standard HTTP error responses.
- Pin runtime and development dependencies and configure pytest plus Ruff lint and formatting checks.
- Document installation, run, test, and configuration commands in the root README.
- Extend `.github/workflows/ci.yml` to run backend tests and lint/format checks on pull requests and pushes to `develop` and `main`, retaining repository structure validation.

### Out of scope

- PostgreSQL models, ORM, and Alembic migrations.
- Authentication, JWT, accounts, roles, teams, milestones, submissions, and file handling.
- React or Flutter changes, OCR, notifications, AI, deployment, Docker, Redis, microservices, and paid services.

## Acceptance criteria

1. A fresh clone can install dependencies and start the API with the README commands.
2. `GET /health` returns HTTP 200 with the exact JSON body `{"status":"ok"}`.
3. The tests cover the health endpoint and an unknown route; tests and Ruff checks pass locally.
4. CI runs those checks for pull requests and pushes targeting both `develop` and `main`.
5. No credentials or real student information are committed.
6. Changes are committed on `feature/GT-51-backend-foundation`, pushed, and submitted in a PR to `develop`; do not merge the PR.

## Verification commands

Run from `src/backend` after installing `requirements.txt`:

```shell
python -m pytest
ruff check app tests
ruff format --check app tests
```

Also run `git diff --check` before committing.

## Security and implementation constraints

- Use only synthetic/test data and do not commit `.env` files or secrets.
- Keep logging free of request bodies, credentials, and personal data.
- Follow the root `AGENTS.md` and the approved Master Plan; do not implement later phases.
- Use logical Jira-keyed commits, push only the feature branch, and open a PR for human review.

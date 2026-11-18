# GradTrack
A full-stack graduation project management platform featuring a React web dashboard, Flutter mobile companion, collaborative task management, milestone tracking, supervisor reviews, analytics, and smart notifications.

## Backend setup — Phase 0

The initial FastAPI backend currently provides a health endpoint. Database models, authentication, and graduation-project workflows are planned for later phases.

Use Python 3.12 or newer. From the repository root, create the backend virtual environment and move into the backend directory:

```powershell
cd src/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS or Linux, use the environment's `python` executable instead:

```shell
cd src/backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

From `src/backend`, start the API on the local machine.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

```shell
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1
```

The health endpoint is available at <http://127.0.0.1:8000/health> and returns `{"status":"ok"}`. Stop the server with `Ctrl+C`.

### Configuration

Configuration is read from environment variables. Defaults are safe for local development: debug mode is off and logging is set to `INFO`.

| Variable | Default | Allowed values |
|---|---|---|
| `GRADTRACK_APP_NAME` | `GradTrack API` | Non-empty text |
| `GRADTRACK_DEBUG` | `false` | `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` |
| `GRADTRACK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

For example, in PowerShell set `$env:GRADTRACK_DEBUG = "true"` before starting Uvicorn to enable local debug mode.

### Tests and code checks

Run these commands from `src/backend` in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\ruff.exe format --check app tests
```

On macOS or Linux, use:

```shell
.venv/bin/python -m pytest
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
```

GitHub Actions runs the same backend tests and checks for pushes and pull requests targeting `develop` or `main`, while retaining repository structure validation.

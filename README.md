# ContentFactory

Production content generator factory built as a product layer around the existing
local generation scripts in `/home/kosmoletc/Content`.

## Scope

This folder is the isolated development area for the new framework. Existing
scripts remain in the parent folder and will be integrated through thin adapters
so their creative behavior does not change during the first migration phase.

## First Vertical Slice

1. FastAPI control plane with health checks and stable DTOs.
2. Render job state machine with step-level status.
3. TikTok narrative text validation.
4. Artifact storage metadata helpers.
5. Legacy script adapters that wrap current scripts without changing defaults.
6. Frontend editor and queue UI after the API contracts are stable.

## Layout

```text
backend/
  app/
    api/              FastAPI routes
    core/             config and runtime settings
    domain/services/  pure domain logic
    integrations/     adapters around legacy scripts
    providers/        external provider clients
    artifacts/        managed file artifact helpers
    schemas/          Pydantic DTOs
    workers/          queue tasks
  tests/              pytest unit/integration tests
frontend/             UI scaffold will live here
docs/                 architecture notes and migration records
```

## Backend

```bash
cd /home/kosmoletc/Content/ContentFactory/backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

The backend currently has no hard dependency on a running ComfyUI instance for
unit tests. Real render integration is intentionally isolated behind adapters.

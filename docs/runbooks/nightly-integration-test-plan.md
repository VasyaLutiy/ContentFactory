# Nightly Integration Test Plan

## Boundary

This plan covers the nightly checks called out in Batch B5.5. It focuses on
integration paths that need real environment wiring or saved fixtures, not the
fast unit test set.

## Goals

- Catch backend regressions before local deployment drift builds up.
- Verify the API can start, answer health checks, and initialize storage.
- Exercise artifact and export paths against persistent local state.
- Keep ComfyUI and TikTok-dependent checks isolated so they can fail without
  blocking unit test signal.

## Recommended Nightly Sequence

1. Validate the Compose graph.
2. Build API, worker, and frontend images.
3. Start the stack with named Postgres, Redis, and artifact volumes.
4. Run the backend test suite.
5. Run focused integration tests that touch artifact and export persistence.
6. Run any fixture-based ComfyUI adapter tests.
7. Run any fixture-based TikTok ingestion tests.
8. Capture logs and test artifacts for triage.

## Suggested Commands

Backend:

```bash
cd /home/kosmoletc/Content/ContentFactory/backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd /home/kosmoletc/Content/ContentFactory/frontend
npm run build
```

Health check:

```bash
cd /home/kosmoletc/Content/ContentFactory
docker compose --env-file .env.example config
docker compose --env-file .env.example build api worker frontend
docker compose --env-file .env.example up -d
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
curl -fsSI http://127.0.0.1:3000/dashboard
```

## Test Buckets

- Smoke: process start, health endpoint, docs availability when enabled.
- Persistence: artifact write/read, export lookup, snapshot lookup, restart
  survival with file-backed SQLite.
- External-adapter fixtures: ComfyUI and TikTok contract tests using saved
  responses or local doubles.
- Frontend gating: build succeeds before deployment promotion.

## Failure Handling

- If smoke fails, stop the pipeline immediately and preserve logs.
- If persistence fails, treat it as a deployment blocker because recovery is not
  reliable.
- If adapter fixtures fail, isolate the adapter layer first before debugging the
  workflow or UI.

## Evidence To Keep

- Backend test output.
- Health endpoint response.
- Compose service status.
- Artifact directory listing for a known sample case.
- Postgres dump timestamp or checksum.

# Local Deployment

## Boundary

This runbook covers the current single-workstation Compose setup for:

- backend API
- backend worker standby process
- Postgres and Redis
- frontend server
- local artifact storage in a named volume

## Prerequisites

- Docker with Compose support.
- A readable `CONTENT_FACTORY_LEGACY_ROOT` path on the host.
- Optional LLM provider credentials if provider-backed flows are exercised.

## Environment

The Compose stack reads `.env.example` as its smoke/development environment.
Use `--env-file .env.example` so the repository-local `.env` used for GitHub
automation is not accidentally loaded by Compose.

Key settings:

- `CONTENT_FACTORY_DATABASE_URL` defaults to Postgres inside Compose.
- `CONTENT_FACTORY_REDIS_URL` points at the Redis service.
- `CONTENT_FACTORY_LEGACY_ROOT` is mounted read-only at `/mnt/content`.
- `CONTENT_FACTORY_ARTIFACT_ROOT` is `/var/lib/content-factory/artifacts`.
- `CONTENT_FACTORY_COMFY_URL` defaults to `http://host.docker.internal:8188`.
- `CONTENT_FACTORY_LOG_JSON=true` enables structured container logs.
- `CONTENT_FACTORY_LLM_RETRY_*` controls provider timeout backoff.

Do not put secrets into `.env.example`. For a real local run, pass a private
env file with the same keys.

## Start Stack

```bash
cd /home/kosmoletc/Content/ContentFactory
docker compose --env-file .env.example up --build -d
```

If local ports are already occupied:

```bash
cd /home/kosmoletc/Content/ContentFactory
POSTGRES_PORT=15432 REDIS_PORT=16379 API_PORT=18000 FRONTEND_PORT=13000 \
NEXT_PUBLIC_CONTENT_FACTORY_API_BASE_URL=http://localhost:18000 \
docker compose --env-file .env.example up --build -d
```

## Verify

```bash
cd /home/kosmoletc/Content/ContentFactory
docker compose --env-file .env.example ps
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
curl -fsSI http://127.0.0.1:3000/dashboard
docker compose --env-file .env.example logs --no-color --tail=50 api worker frontend
```

The health response should include `status: ok`, `artifact_root`,
`legacy_content_root`, and `comfy_url`. The ready endpoint must return `200`
after the API can query Postgres.

The current worker container initializes the database and remains in standby.
It shares the Postgres, Redis, and artifact volumes so restarts preserve durable
state, but a dedicated persistent worker runtime is still a separate product
implementation task.

## Stop

```bash
cd /home/kosmoletc/Content/ContentFactory
docker compose --env-file .env.example down
```

Use `docker compose --env-file .env.example down -v` only when you explicitly
want to remove Postgres, Redis, and artifact volumes.

## Failure Modes

- If the health endpoint reports an unexpected `artifact_root`, check the
  exported environment before starting the backend.
- If `CONTENT_FACTORY_ENABLE_DOCS=false`, `/docs` and `/redoc` are intentionally
  unavailable.
- If `/health/ready` fails, inspect Postgres readiness and the configured
  `CONTENT_FACTORY_DATABASE_URL`.
- If frontend browser calls reach the wrong API host, update
  `NEXT_PUBLIC_CONTENT_FACTORY_API_BASE_URL` before rebuilding the frontend
  image.

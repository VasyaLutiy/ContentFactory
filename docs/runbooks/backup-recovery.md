# Backup And Recovery

## Boundary

This runbook covers backup and restore for the current local ContentFactory
deployment:

- artifact files in the `content-factory_artifact-data` Docker volume
- Postgres data in the `content-factory_postgres-data` Docker volume
- Redis data in the `content-factory_redis-data` Docker volume
- legacy workspace content referenced by `CONTENT_FACTORY_LEGACY_ROOT`

It does not assume a managed backup tool. The goal is a predictable manual
workflow that can be scripted later.

## What To Back Up

Back up these paths together so restore stays internally consistent:

- the artifact volume
- a Postgres logical dump
- the Redis append-only volume when queued/runtime data is introduced
- any exported deliverables you want to keep outside the managed artifact tree

## Backup Procedure

1. Stop writers or put the stack into a quiet state.
2. Dump Postgres.
3. Archive the artifact volume.
4. Store the dump and archive outside the workspace.

Example:

```bash
cd /home/kosmoletc/Content/ContentFactory
docker compose --env-file .env.example exec -T postgres \
  pg_dump -U content_factory content_factory \
  > /tmp/content-factory-postgres-$(date +%Y%m%d).sql
docker run --rm \
  -v content-factory_artifact-data:/data:ro \
  -v /tmp:/backup \
  alpine tar -czf /backup/content-factory-artifacts-$(date +%Y%m%d).tar.gz -C /data .
```

## Restore Procedure

1. Stop the stack.
2. Restore the artifact volume from the matching archive.
3. Start Postgres and restore the matching SQL dump.
4. Start the full stack and check `/api/v1/health/ready`.

Example:

```bash
cd /home/kosmoletc/Content/ContentFactory
docker compose --env-file .env.example down
docker volume rm content-factory_artifact-data
docker volume create content-factory_artifact-data
docker run --rm \
  -v content-factory_artifact-data:/data \
  -v /tmp:/backup \
  alpine sh -c "cd /data && tar -xzf /backup/content-factory-artifacts-YYYYMMDD.tar.gz"
docker compose --env-file .env.example up -d postgres
docker compose --env-file .env.example exec -T postgres \
  psql -U content_factory -d content_factory \
  < /tmp/content-factory-postgres-YYYYMMDD.sql
docker compose --env-file .env.example up -d
```

## Recovery Checks

After restore:

- Confirm `/api/v1/health/ready` returns `200`.
- Confirm the health endpoint reports the expected artifact and legacy roots.
- Confirm previously known artifact files are present on disk.
- Confirm database-backed objects such as campaigns, exports, or snapshots are
  visible again.

## Failure Modes

- A restored artifact tree without the matching database can leave orphaned
  files and broken lineage references.
- A restored database without artifacts can leave records pointing at missing
  files.
- If the stack was started without the Compose Postgres URL, verify which
  database actually received writes before restoring.

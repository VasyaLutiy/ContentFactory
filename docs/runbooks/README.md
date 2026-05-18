# Runbooks

Operational runbooks for local deployment and recovery of the ContentFactory
stack.

## Contents

- [Local Deployment](./local-deployment.md)
- [Backup And Recovery](./backup-recovery.md)
- [Nightly Integration Test Plan](./nightly-integration-test-plan.md)

## Source Of Truth

These runbooks are aligned to the current code and config in:

- `README.md`
- `.env.example`
- `backend/app/core/config.py`
- `backend/app/api/v1/health.py`
- `backend/app/main.py`

If any command or environment variable changes there, update this folder in the
same change.

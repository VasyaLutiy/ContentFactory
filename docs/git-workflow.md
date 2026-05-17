# Git Workflow

## Branches

- `main`: reviewed, stable project state.
- `plan/*`: planning-only changes such as issues, milestones, docs.
- `feature/<issue-number>-short-name`: implementation branches.
- `fix/<issue-number>-short-name`: bugfix branches.

## Pull Request Rules

- One PR should map to one Batch issue or a narrow implementation slice.
- PR description must include:
  - linked issue,
  - behavior changed,
  - tests run,
  - known risks.
- Do not mix planning, backend, frontend, and provider work in one PR unless the
  issue explicitly defines a vertical slice.

## Commit Style

Use short conventional prefixes:

- `docs:`
- `backend:`
- `frontend:`
- `tests:`
- `infra:`
- `providers:`

Examples:

```text
docs: add milestones and initial issue backlog
backend: add render job state machine
tests: cover tiktok text policy validation
```

## Issue Labels

- `type:epic`
- `type:batch`
- `area:backend`
- `area:frontend`
- `area:providers`
- `area:analytics`
- `area:ops`
- `area:tests`
- `priority:p0`
- `priority:p1`
- `priority:p2`
- `status:needs-review`
- `status:approved`
- `blocked`

## Approval Gate

Implementation work starts only after the related Batch issue is reviewed and
marked `status:approved`.

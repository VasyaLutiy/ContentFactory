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
- `status:done`
- `blocked`

## Approval Gate

Implementation work starts only after the related Batch issue is reviewed and
marked `status:approved`.

## Automatic Issue Closure

While GitHub Actions are unavailable, CI and issue closure workflows are kept as
manual `workflow_dispatch` jobs. After Actions are available again, restore
automatic PR triggers for `.github/workflows/ci.yml` and
`.github/workflows/close-delivery-issues.yml`.

When automatic triggers are enabled, merged PRs into the default branch or an
approved `plan/*` base branch trigger `.github/workflows/close-delivery-issues.yml`.
The same workflow can be run manually with `workflow_dispatch` to reconcile a
specific PR.

- To close completed Batch issues, use explicit closing references in the PR
  title or description, for example `Closes batches: #9 #10`.
- Lines such as `Related issues: #9 #10` are informational and are not closed
  by the workflow.
- Epic issues close only when every Batch listed for that Epic in
  `docs/issue-closure-map.json` is already closed.
- The workflow removes review status labels and applies `status:done` to issues
  it closes.
- The closure map is validated against live issue titles and labels before any
  write action, so stale issue numbers fail closed instead of closing the wrong
  issue.

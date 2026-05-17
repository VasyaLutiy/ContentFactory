# Agent Operational Hardening

This note documents the local failure modes used by the Factory Agent contract
evals. The goal is deterministic review without GPU access, TikTok access, or
paid LLM calls.

## Replay Artifacts

Contract evals must use saved fixtures for:

- Retention diagnosis from local analytics JSON.
- Variant comparison from local artifact metadata.
- Caption pack requests grounded in local artifact refs.
- Approval-required render requests that exercise approval events without
  enqueueing unapproved work.

Fixtures should include the user message, compact runtime context, expected tool
calls, expected grounded references, and forbidden claim patterns. The eval
runner should fail if an answer names a file, render job, timestamp, or metric
that is not present in the fixture context or tool results.

## Degraded Modes

Missing analytics:

- `analyze_tiktok_stats` returns a succeeded empty result with zero artifacts and
  no metrics.
- The assistant may say analytics are unavailable for the selected namespace.
- The assistant must not invent views, likes, retention, or platform trends.

Unavailable provider:

- Provider exceptions must be normalized to structured user-visible errors.
- Logs must include provider, model, latency, timeout/retry metadata, and any
  token/cost usage that was returned before failure.
- The UI should present an advisor-unavailable message rather than partial
  generated advice.

Interrupted SSE stream:

- Clients resume with `after_id`.
- Event payloads include stable `session_id` and `emitted_at` fields.
- Replayed streams must not re-run side-effect tools.

Duplicate side-effect request:

- Side-effect tools require an idempotency key or explicit rejection.
- Render job launch uses an atomic approval claim. A second launch attempt for
  the same approval returns a structured conflict unless it replays the same
  idempotency key, in which case the original job id is returned and a missing
  in-memory queue entry is restored.

Tool timeout policy:

- Read-only tools run behind a bounded worker pool and enforce each tool's
  `timeout_seconds` budget.
- A timeout returns a structured `tool_timeout` result and records the timeout
  in audit/log metadata.
- Synchronous Python handlers cannot be force-killed in-process after they
  start, so handlers must remain read-only and avoid unbounded external I/O.
  Queued work is bounded by the worker pool.

## Logging Contract

Agent logs should be structured dictionaries with these fields when available:

- `session_id`
- `message_id`
- `provider`
- `model`
- `tool_name`
- `latency_ms`
- `timeout_seconds`
- `retry_count`
- `tokens_prompt`
- `tokens_completion`
- `estimated_cost`
- `status`
- `error_code`

Secrets, raw provider keys, absolute private paths, and full prompt bodies must
not be logged.

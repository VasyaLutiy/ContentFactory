# Factory Agent Implementation Plan

## Source Scope

This plan translates `/home/kosmoletc/Content/FactoryAgent.md` into the first reviewable delivery epic for ContentFactory. The Factory Agent is an in-product production assistant, not a generic chatbot. The frontend chat is only the interface; backend services own context, tools, approvals, audit, and execution.

## MVP Boundary

Included:

- Copilot chat shell and session API.
- SSE event streaming.
- Provider-agnostic LLM contract.
- Versioned prompt/profile contract.
- Typed backend tool registry.
- Read-only production tools.
- Approval-gated render job launch.
- Caption/posting pack and grounded recommendations.
- Contract evals and operational hardening.

Deferred:

- Autonomous TikTok posting.
- Destructive tools.
- Unrestricted shell access.
- Realtime voice agent.
- Multi-agent autopilot loops.
- Unapproved external-cost actions.

## Backend Contracts

Agent runtime:

- `AgentSession`: project/user context, title, mode, timestamps.
- `AgentMessage`: session, role, content, artifact refs, timestamps.
- `AgentEvent`: stream event type, payload, cursor, timestamps.
- `AgentContextSnapshot`: compact context used for one LLM call, with source refs.

LLM provider:

- `create_response(request) -> AgentLLMResponse`
- `stream_response(request) -> AsyncIterable[AgentLLMEvent]`
- `supports_tools() -> bool`
- `supports_vision() -> bool`
- `supports_structured_output() -> bool`

Tool registry:

- Tool metadata: name, input schema, output schema, safety class, allowlist policy, timeout, cost hint.
- Tool execution result: status, output JSON, artifact refs, warnings, error code/details.
- Safety classes: `read_only`, `cheap_write`, `expensive_job`, `external_api_cost`, `destructive`.

Approval:

- Approval states: pending, approved, rejected, expired.
- Expensive or external-cost tools cannot execute until approved.
- Rejected and expired approvals must remain auditable.

Prompt/profile:

- Prompt metadata: prompt_id, version, profile_id, language, content, active, changelog, owner.
- Assembly order: global safety, base Factory Agent, profile prompt, project rules, experiment objective, compact runtime context, user message.

## Insertion Points

Backend API:

- Add `backend/app/api/v1/agent_sessions.py`.
- Add `backend/app/api/v1/agent_approvals.py`.
- Register both in `backend/app/api/router.py`.

Domain services:

- Add `backend/app/domain/services/agent_service.py`.
- Add `backend/app/domain/services/agent_context_builder.py`.
- Add `backend/app/domain/services/agent_tool_registry.py`.
- Add `backend/app/domain/services/agent_approval_service.py`.

Persistence:

- Add `backend/app/db/models/agent_*.py`.
- Add `backend/app/db/repos/agent_*.py`.
- Add `backend/app/schemas/agent/*.py`.

Providers:

- Add `backend/app/providers/llm/base.py`.
- Add OpenAI-compatible adapters under `backend/app/providers/llm/`.
- Keep provider secrets server-side in `backend/app/core/config.py`.

Workers and artifacts:

- Bridge `create_render_job` to `backend/app/workers/queue.py`.
- Register outputs through `backend/app/artifacts/storage.py`.
- Wrap existing provider/script adapters as typed tools instead of shell access.

Frontend:

- Extend `frontend/app/_components/app-shell.tsx` with a persistent Copilot region when enabled.
- Add Copilot chat, tool-call cards, approval cards, artifact links, and job state cards.
- Keep first UI slice incremental so the existing dashboard, campaign, and queue pages stay reviewable.

## Batch Order

1. `Batch: Agent Chat Shell And Session API`
2. `Batch: LLM Provider And Prompt Contracts`
3. `Batch: Typed Agent Tool Registry And Read-Only Tools`
4. `Batch: Approval Gates And Controlled Job Launch`
5. `Batch: Caption Pack And Production Recommendations`
6. `Batch: Agent Contract Evals And Hardening`

## Review Rules

- One batch should map to one implementation PR unless the owner explicitly approves a vertical slice.
- PR bodies must use explicit `Closes #NN` references for completed batches.
- Epic closure is dependency-driven through `docs/issue-closure-map.json`.
- Actions are currently disabled; run tests locally and use `scripts/close_delivery_issues.py` manually after merges.

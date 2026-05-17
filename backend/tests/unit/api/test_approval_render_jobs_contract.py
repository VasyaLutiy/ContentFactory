import json
import time

import pytest

from app.api.v1 import agent_sessions
from app.workers.queue import render_queue


def _create_session(client, title: str = "Approval Session") -> int:
    response = client.post("/api/v1/agent/sessions", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


def _parse_sse_events(raw_text: str) -> list[dict]:
    events: list[dict] = []
    for chunk in raw_text.strip().split("\n\n"):
        if not chunk.strip():
            continue
        event: dict[str, str] = {}
        for line in chunk.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            event[key.strip()] = value.strip()
        events.append(event)
    return events


def test_approval_gated_render_job_success_and_sse_events(client) -> None:
    session_id = _create_session(client)

    approval_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals",
        json={"episode_id": 42},
    )
    assert approval_response.status_code == 201
    approval_id = approval_response.json()["id"]
    assert approval_response.json()["status"] == "pending"

    approve_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "ops-reviewer", "reason": "validated in QA"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    create_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 42},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] == "queued"
    assert payload["approval_id"] == approval_id

    events_response = client.get(f"/api/v1/agent/sessions/{session_id}/events")
    assert events_response.status_code == 200
    events = _parse_sse_events(events_response.text)
    assert [item["event"] for item in events] == [
        "approval.required",
        "approval.resolved",
        "tool.started",
        "tool.result",
        "done",
    ]
    render_job_payload = json.loads(events[-2]["data"])
    assert render_job_payload["approval_id"] == approval_id
    assert render_job_payload["status"] == "queued"


def test_create_render_job_rejects_without_approved_matching_approval(client) -> None:
    session_id = _create_session(client)

    pending_approval = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals",
        json={"episode_id": 7},
    )
    assert pending_approval.status_code == 201
    approval_id = pending_approval.json()["id"]

    pending_attempt = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 7},
    )
    assert pending_attempt.status_code == 409
    assert pending_attempt.json()["detail"] == "Approval required"

    reject_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/reject",
        json={"decided_by": "ops-reviewer", "reason": "budget hold"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    mismatch_attempt = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 99},
    )
    assert mismatch_attempt.status_code == 409
    assert mismatch_attempt.json()["detail"] == "Approval does not match render job"


def test_create_render_job_rejects_expired_approved_approval(client) -> None:
    session_id = _create_session(client)

    approval_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals",
        json={"episode_id": 8, "expires_in_seconds": 1},
    )
    assert approval_response.status_code == 201
    approval_id = approval_response.json()["id"]

    approve_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "ops-reviewer"},
    )
    assert approve_response.status_code == 200
    time.sleep(1.1)

    expired_attempt = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 8},
    )
    assert expired_attempt.status_code == 409
    assert expired_attempt.json()["detail"] == "Approval expired"
    assert render_queue.list() == []


def test_create_render_job_does_not_enqueue_before_event_persistence(client, monkeypatch) -> None:
    session_id = _create_session(client)

    approval_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals",
        json={"episode_id": 11},
    )
    assert approval_response.status_code == 201
    approval_id = approval_response.json()["id"]

    approve_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "ops-reviewer"},
    )
    assert approve_response.status_code == 200

    original_create_event = agent_sessions.AgentEventRepository.create_event

    def fail_on_tool_result(self, *, session_id, event_type, payload):
        if event_type == "tool.result":
            raise RuntimeError("event persistence failed")
        return original_create_event(
            self,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
        )

    monkeypatch.setattr(
        agent_sessions.AgentEventRepository,
        "create_event",
        fail_on_tool_result,
    )
    with pytest.raises(RuntimeError, match="event persistence failed"):
        client.post(
            f"/api/v1/agent/sessions/{session_id}/render-jobs",
            json={"approval_id": approval_id, "episode_id": 11},
        )
    assert render_queue.list() == []

import json

from app.workers.queue import render_queue


def _create_session(client) -> int:
    response = client.post("/api/v1/agent/sessions", json={"title": "approval-session"})
    assert response.status_code == 201
    return response.json()["id"]


def _create_approval(
    client,
    *,
    session_id: int,
    episode_id: int = 1,
    expires_in_seconds: int = 300,
):
    return client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals",
        json={
            "episode_id": episode_id,
            "estimated_cost": "local worker",
            "estimated_duration_seconds": 60,
            "output_location": f"episode-{episode_id}/renders",
            "expires_in_seconds": expires_in_seconds,
        },
    )


def _parse_events(raw_text: str) -> list[dict]:
    events: list[dict] = []
    for chunk in raw_text.strip().split("\n\n"):
        if not chunk.strip():
            continue
        row: dict[str, str] = {}
        for line in chunk.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            row[key.strip()] = value.strip()
        events.append(row)
    return events


def test_create_approval_defaults_to_pending_and_emits_required_event(client) -> None:
    session_id = _create_session(client)

    response = _create_approval(client, session_id=session_id, episode_id=12)

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] == session_id
    assert body["action"] == "create_render_job"
    assert body["episode_id"] == 12
    assert body["status"] == "pending"
    assert body["estimated_cost"] == "local worker"
    assert body["estimated_duration_seconds"] == 60
    assert body["output_location"] == "episode-12/renders"
    assert body["expires_at"] is not None

    events = _parse_events(client.get(f"/api/v1/agent/sessions/{session_id}/events").text)
    assert [item["event"] for item in events] == ["approval.required"]
    event_payload = json.loads(events[0]["data"])
    assert event_payload["approval_id"] == body["id"]
    assert event_payload["estimated_cost"] == "local worker"


def test_approve_pending_approval_transitions_to_approved(client) -> None:
    session_id = _create_session(client)
    created = _create_approval(client, session_id=session_id)
    approval_id = created.json()["id"]

    decision = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "operator", "reason": "approved budget"},
    )

    assert decision.status_code == 200
    body = decision.json()
    assert body["id"] == approval_id
    assert body["status"] == "approved"
    assert body["decided_by"] == "operator"
    assert body["decided_at"] is not None


def test_reject_pending_approval_transitions_to_rejected_and_does_not_enqueue(client) -> None:
    session_id = _create_session(client)
    created = _create_approval(client, session_id=session_id, episode_id=33)
    approval_id = created.json()["id"]

    decision = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/reject",
        json={"decided_by": "operator", "reason": "budget hold"},
    )
    launch = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 33},
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"
    assert launch.status_code == 409
    assert render_queue.list() == []


def test_decision_returns_conflict_for_expired_approval(client) -> None:
    session_id = _create_session(client)
    created = _create_approval(client, session_id=session_id, expires_in_seconds=0)
    approval_id = created.json()["id"]

    decision = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "operator"},
    )

    assert decision.status_code == 409
    assert decision.json()["detail"] == "Approval expired"

    events = _parse_events(client.get(f"/api/v1/agent/sessions/{session_id}/events").text)
    assert [item["event"] for item in events] == [
        "approval.required",
        "approval.resolved",
    ]
    assert json.loads(events[-1]["data"])["status"] == "expired"


def test_duplicate_decision_is_rejected_as_conflict(client) -> None:
    session_id = _create_session(client)
    created = _create_approval(client, session_id=session_id)
    approval_id = created.json()["id"]

    first = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "operator"},
    )
    second = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/reject",
        json={"decided_by": "operator"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "Approval already resolved"


def test_destructive_tools_are_unavailable_in_mvp(client) -> None:
    session_id = _create_session(client)

    response = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals",
        json={
            "tool_name": "delete_artifact",
            "tool_input": {"artifact_id": "job-1/video/clip.mp4"},
        },
    )

    assert response.status_code == 422


def test_approved_create_render_job_enqueues_work_once(client) -> None:
    session_id = _create_session(client)
    created = _create_approval(client, session_id=session_id, episode_id=44)
    approval_id = created.json()["id"]

    decision = client.post(
        f"/api/v1/agent/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"decided_by": "operator"},
    )
    launch = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 44},
    )
    duplicate_launch = client.post(
        f"/api/v1/agent/sessions/{session_id}/render-jobs",
        json={"approval_id": approval_id, "episode_id": 44},
    )

    assert decision.status_code == 200
    assert launch.status_code == 201
    assert duplicate_launch.status_code == 409
    assert duplicate_launch.json()["detail"] == "Approval already used"
    jobs = render_queue.list()
    assert len(jobs) == 1
    assert jobs[0].episode_id == "44"

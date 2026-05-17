import json


def _create_session(client, title: str = "Issue 24 Session") -> int:
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


def test_create_agent_session_contract(client) -> None:
    response = client.post("/api/v1/agent/sessions", json={"title": "Chat Session"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["title"] == "Chat Session"
    assert "created_at" in body


def test_create_message_creates_user_and_placeholder_assistant(client) -> None:
    session_id = _create_session(client)

    response = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 201
    body = response.json()

    assert body["user_message"]["session_id"] == session_id
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "hello"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"] == (
        f"Factory Agent received message {body['user_message']['id']}. Context capture is ready."
    )


def test_events_stream_returns_persisted_message_events_and_supports_resume(client) -> None:
    session_id = _create_session(client)

    first = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "first"},
    )
    assert first.status_code == 201
    first_assistant_id = first.json()["assistant_message"]["id"]

    second = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "second"},
    )
    assert second.status_code == 201

    all_events_response = client.get(f"/api/v1/agent/sessions/{session_id}/events")
    assert all_events_response.status_code == 200
    assert all_events_response.headers["content-type"].startswith("text/event-stream")

    all_events = _parse_sse_events(all_events_response.text)
    assert len(all_events) == 4
    first_payload = json.loads(all_events[0]["data"])
    assert all_events[0]["event"] == "message.created"
    assert first_payload["role"] == "user"
    assert first_payload["content"] == "first"

    resumed_response = client.get(
        f"/api/v1/agent/sessions/{session_id}/events",
        params={"after_id": first_assistant_id},
    )
    assert resumed_response.status_code == 200
    resumed_events = _parse_sse_events(resumed_response.text)
    assert len(resumed_events) == 2
    resumed_payloads = [json.loads(item["data"]) for item in resumed_events]
    assert [item["content"] for item in resumed_payloads] == [
        "second",
        f"Factory Agent received message {resumed_payloads[0]['id']}. Context capture is ready.",
    ]


def test_create_message_returns_not_found_for_missing_session(client) -> None:
    response = client.post("/api/v1/agent/sessions/999999/messages", json={"content": "hello"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_events_stream_returns_not_found_for_missing_session(client) -> None:
    response = client.get("/api/v1/agent/sessions/999999/events")
    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"

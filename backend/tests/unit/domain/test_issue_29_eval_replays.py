from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.domain.services.agent_tool_registry import AgentToolResultStatus, build_default_agent_tool_registry


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evals" / "issue_29"


def test_retention_diagnosis_replay_is_deterministic_and_grounded(tmp_path, monkeypatch) -> None:
    fixture = _load_fixture("retention_diagnosis.json")
    registry = _registry_from_fixture(tmp_path, monkeypatch, fixture)

    first = _run_tool_calls(registry, fixture["tool_calls"])
    second = _run_tool_calls(registry, fixture["tool_calls"])

    assert [asdict(item) for item in first] == [asdict(item) for item in second]
    _assert_grounded_claims(fixture["claims"], first)


def test_variant_comparison_replay_is_grounded(tmp_path, monkeypatch) -> None:
    fixture = _load_fixture("variant_comparison.json")
    registry = _registry_from_fixture(tmp_path, monkeypatch, fixture)

    results = _run_tool_calls(registry, fixture["tool_calls"])

    assert all(item.status == AgentToolResultStatus.SUCCEEDED for item in results)
    _assert_grounded_claims(fixture["claims"], results)


def test_caption_pack_fixture_contract_and_grounding(tmp_path, monkeypatch) -> None:
    fixture = _load_fixture("caption_pack.json")
    registry = _registry_from_fixture(tmp_path, monkeypatch, fixture)

    results = _run_tool_calls(registry, fixture["tool_calls"])
    _assert_grounded_claims(fixture["claims"], results)

    pack = fixture["caption_pack"]
    assert set(pack) == {"caption", "hashtags", "first_comment", "strategy_note", "artifact_refs"}
    assert isinstance(pack["caption"], str) and pack["caption"].strip()
    assert isinstance(pack["first_comment"], str) and pack["first_comment"].strip()
    assert isinstance(pack["strategy_note"], str) and pack["strategy_note"].strip()
    assert isinstance(pack["hashtags"], list) and all(tag.startswith("#") for tag in pack["hashtags"])

    available_artifacts = _artifact_ids_from_results(results)
    for artifact_id in pack["artifact_refs"]:
        assert artifact_id in available_artifacts


def test_approval_required_render_request_replay(client) -> None:
    fixture = _load_fixture("approval_required_render_request.json")

    session_id: int | None = None
    approval_id: int | None = None
    episode_id = fixture["episode_id"]

    for step in fixture["steps"]:
        action = step["action"]
        if action == "create_session":
            response = client.post("/api/v1/agent/sessions", json={"title": step["title"]})
            assert response.status_code == 201
            session_id = response.json()["id"]
            continue
        if action == "request_approval":
            assert session_id is not None
            response = client.post(
                f"/api/v1/agent/sessions/{session_id}/approvals",
                json={"episode_id": episode_id},
            )
            assert response.status_code == 201
            approval_id = response.json()["id"]
            continue
        if action == "create_render_job":
            assert session_id is not None
            assert approval_id is not None
            response = client.post(
                f"/api/v1/agent/sessions/{session_id}/render-jobs",
                json={"approval_id": approval_id, "episode_id": episode_id},
            )
            assert response.status_code == step["expect_status"]
            assert response.json()["detail"] == step["expect_detail"]
            continue
        raise AssertionError(f"Unknown replay action {action!r}")

    assert session_id is not None
    events_response = client.get(f"/api/v1/agent/sessions/{session_id}/events")
    assert events_response.status_code == 200
    events = _parse_sse_events(events_response.text)
    assert [item["event"] for item in events] == fixture["expected_event_types"]
    last_payload = json.loads(events[-1]["data"])
    assert last_payload["code"] == fixture["required_error_code"]


def test_eval_guard_rejects_ungrounded_metric_claim(tmp_path, monkeypatch) -> None:
    fixture = _load_fixture("ungrounded_stat_claim.json")
    registry = _registry_from_fixture(tmp_path, monkeypatch, fixture)

    results = _run_tool_calls(registry, fixture["tool_calls"])

    with pytest.raises(AssertionError, match="Ungrounded metric claim"):
        _assert_grounded_claims(fixture["claims"], results)


def _registry_from_fixture(tmp_path, monkeypatch, fixture: dict):
    _materialize_artifacts(tmp_path, fixture.get("artifacts", []))
    monkeypatch.setenv("CONTENT_FACTORY_ARTIFACT_ROOT", str(tmp_path))
    get_settings.cache_clear()
    return build_default_agent_tool_registry()


def _run_tool_calls(registry, tool_calls: list[dict]):
    results = []
    for tool_call in tool_calls:
        result = registry.execute(tool_call["name"], tool_call["input"])
        assert result.status == AgentToolResultStatus.SUCCEEDED
        results.append(result)
    return results


def _materialize_artifacts(root: Path, artifacts: list[dict]) -> None:
    for artifact in artifacts:
        path = root / artifact["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if "json" in artifact:
            path.write_text(json.dumps(artifact["json"]))
        else:
            path.write_text(artifact.get("content", ""))


def _assert_grounded_claims(claims: list[dict], results) -> None:
    artifacts = _artifact_ids_from_results(results)
    metrics = _metric_index_from_results(results)
    outputs = _output_index_from_results(results)

    for claim in claims:
        claim_type = claim["type"]
        if claim_type == "artifact_ref":
            artifact_id = claim["artifact_id"]
            assert artifact_id in artifacts, f"Ungrounded artifact claim: {artifact_id}"
            continue
        if claim_type == "metric":
            key = claim["name"]
            expected_value = claim["value"]
            assert key in metrics, f"Ungrounded metric claim: {key}"
            actual_value = metrics[key]
            if isinstance(expected_value, float):
                assert abs(float(actual_value) - expected_value) < 1e-9, (
                    f"Ungrounded metric claim for {key}: expected {expected_value}, got {actual_value}"
                )
            else:
                assert actual_value == expected_value, (
                    f"Ungrounded metric claim for {key}: expected {expected_value}, got {actual_value}"
                )
            continue
        if claim_type == "output":
            field = claim["field"]
            assert field in outputs, f"Ungrounded output claim: {field}"
            assert outputs[field] == claim["value"], (
                f"Ungrounded output claim for {field}: expected {claim['value']}, got {outputs[field]}"
            )
            continue
        raise AssertionError(f"Unsupported claim type {claim_type!r}")


def _artifact_ids_from_results(results) -> set[str]:
    refs: set[str] = set()
    for result in results:
        refs.update(item.artifact_id for item in result.artifact_refs)
    return refs


def _metric_index_from_results(results) -> dict[str, object]:
    metrics: dict[str, object] = {}
    for result in results:
        for metric in result.metrics:
            metrics[metric.name] = metric.value
    return metrics


def _output_index_from_results(results) -> dict[str, object]:
    output: dict[str, object] = {}
    for result in results:
        output.update(result.output)
    return output


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


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

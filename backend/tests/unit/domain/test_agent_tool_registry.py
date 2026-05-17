from __future__ import annotations

from dataclasses import asdict
import json
import time

from app.core.config import get_settings
from app.db.repos.agent_session import AgentSessionRepository
from app.db.repos.agent_tool_call import AgentToolCallRepository
from app.db.session import get_session_maker
from app.domain.services.agent_tool_registry import (
    AgentTool,
    AgentToolAuditSink,
    AgentToolCallRecord,
    AgentToolMetadata,
    AgentToolResult,
    AgentToolResultStatus,
    AgentToolSafetyClass,
    build_default_agent_tool_registry,
)


def test_registry_is_deny_by_default_for_unknown_tools(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)

    result = registry.execute("unknown_tool", {})

    assert result.status == AgentToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.code == "unknown_tool"


def test_registry_audits_unknown_tool_attempts(tmp_path, monkeypatch) -> None:
    audit = _MemoryAuditSink()
    registry = _registry(tmp_path, monkeypatch, audit_sink=audit)

    result = registry.execute("unknown_tool", {}, context_snapshot={"session": "s1"})

    assert result.status == AgentToolResultStatus.FAILED
    assert len(audit.records) == 1
    assert audit.records[0].tool_name == "unknown_tool"
    assert audit.records[0].safety_class == "unknown"
    assert audit.records[0].context_snapshot == {"session": "s1"}


def test_audit_failures_do_not_break_successful_tool_results(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch, audit_sink=_FailingAuditSink())
    _write_tool_fixtures(tmp_path)

    result = registry.execute("list_artifacts", {"namespace": "job-1"})

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert result.output["count"] == 5


def test_registry_exposes_required_read_only_tool_specs(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)

    specs = {item.name: item for item in registry.metadata()}

    assert set(specs) == {
        "list_artifacts",
        "inspect_video",
        "extract_keyframes",
        "analyze_tiktok_stats",
        "compare_variants",
    }
    for spec in specs.values():
        assert spec.safety_class == "read_only"
        assert spec.input_schema["type"] == "object"
        assert spec.audit_metadata["reads"] == ["artifact_root"]


def test_registry_exposes_provider_tool_specs(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)

    specs = {item.name: item for item in registry.llm_tool_specs()}

    assert set(specs) == {
        "list_artifacts",
        "inspect_video",
        "extract_keyframes",
        "analyze_tiktok_stats",
        "compare_variants",
    }
    assert specs["list_artifacts"].input_schema["type"] == "object"


def test_registry_rejects_invalid_input_with_structured_schema_error(
    tmp_path,
    monkeypatch,
) -> None:
    registry = _registry(tmp_path, monkeypatch)

    result = registry.execute("list_artifacts", {"unexpected": "field"})

    assert result.status == AgentToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.code == "invalid_tool_input"
    assert "Unexpected field" in result.error.message


def test_registry_blocks_destructive_tools_without_executing_handler(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    invoked = {"called": False}

    registry.register(
        AgentTool(
            metadata=AgentToolMetadata(
                name="delete_artifact",
                description="Deletes an artifact.",
                input_schema={"type": "object", "additionalProperties": False},
                output_schema={"type": "object"},
                safety_class=AgentToolSafetyClass.DESTRUCTIVE,
                timeout_seconds=5,
                cost_hint="none",
            ),
            handler=lambda _input: _mark_invoked(invoked),
        )
    )

    result = registry.execute("delete_artifact", {})

    assert result.status == AgentToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.code == "approval_required"
    assert result.error.details["safety_class"] == "destructive"
    assert invoked["called"] is False


def test_registry_times_out_slow_read_only_tools(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)

    registry.register(
        AgentTool(
            metadata=AgentToolMetadata(
                name="slow_read",
                description="Sleeps before returning.",
                input_schema={"type": "object", "additionalProperties": False},
                output_schema={"type": "object"},
                safety_class=AgentToolSafetyClass.READ_ONLY,
                timeout_seconds=0.01,
                cost_hint="none",
            ),
            handler=lambda _input: _slow_success(),
        )
    )

    result = registry.execute("slow_read", {})

    assert result.status == AgentToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.code == "tool_timeout"


def test_read_only_tools_return_deterministic_fixture_results(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    fixtures = _write_tool_fixtures(tmp_path)
    payloads = {
        "list_artifacts": {"namespace": "job-1"},
        "inspect_video": {"artifact_id": fixtures["video"]},
        "extract_keyframes": {"artifact_id": fixtures["video"]},
        "analyze_tiktok_stats": {"namespace": "job-1"},
        "compare_variants": {"artifact_ids": [fixtures["video"], fixtures["variant"]]},
    }

    for tool_name, payload in payloads.items():
        first = registry.execute(tool_name, payload)
        second = registry.execute(tool_name, payload)

        assert asdict(first) == asdict(second)
        assert first.status == AgentToolResultStatus.SUCCEEDED


def test_list_artifacts_filters_by_namespace_and_kind(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    _write_tool_fixtures(tmp_path)

    result = registry.execute("list_artifacts", {"namespace": "job-1", "kind": "video"})

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert result.output["count"] == 2
    assert [item.kind for item in result.artifact_refs] == ["video", "video"]


def test_inspect_video_reads_metadata_sidecar(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    fixtures = _write_tool_fixtures(tmp_path)

    result = registry.execute("inspect_video", {"artifact_id": fixtures["video"]})

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert result.output["duration_seconds"] == 12.5
    assert result.output["width"] == 1080
    assert result.output["height"] == 1920
    assert result.artifact_refs[0].artifact_id == fixtures["video"]


def test_extract_keyframes_returns_existing_keyframe_refs_only(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    fixtures = _write_tool_fixtures(tmp_path)

    result = registry.execute("extract_keyframes", {"artifact_id": fixtures["video"]})

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert result.output["count"] == 2
    assert {item.kind for item in result.artifact_refs} == {"video", "image", "screenshot"}


def test_analyze_tiktok_stats_normalizes_local_json_metrics(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    _write_tool_fixtures(tmp_path)

    result = registry.execute("analyze_tiktok_stats", {"namespace": "job-1"})

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert {metric.name for metric in result.metrics} >= {"views", "likes", "retention_rate"}
    assert {metric.unit for metric in result.metrics} >= {"count", "ratio"}


def test_compare_variants_returns_artifact_refs_and_size_ranking(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    fixtures = _write_tool_fixtures(tmp_path)

    result = registry.execute(
        "compare_variants",
        {"artifact_ids": [fixtures["video"], fixtures["variant"]]},
    )

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert result.output["largest_artifact_id"] == fixtures["variant"]
    assert [item.artifact_id for item in result.artifact_refs] == [
        fixtures["video"],
        fixtures["variant"],
    ]


def test_tool_paths_cannot_escape_artifact_root(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    outside = tmp_path.parent / "outside.mp4"
    outside.write_text("outside")

    result = registry.execute("inspect_video", {"path": str(outside)})

    assert result.status == AgentToolResultStatus.FAILED
    assert result.error is not None
    assert result.error.code == "artifact_not_found"


def test_namespace_filters_cannot_escape_artifact_root(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path, monkeypatch)
    outside = tmp_path.parent / "json" / "outside.analytics.json"
    outside.parent.mkdir(exist_ok=True)
    outside.write_text(json.dumps({"metrics": {"views": 999}}))

    result = registry.execute("analyze_tiktok_stats", {"namespace": ".."})

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert result.output["artifact_count"] == 0
    assert result.metrics == ()


def test_tool_calls_are_persisted_for_replay(tmp_path, monkeypatch) -> None:
    _write_tool_fixtures(tmp_path)
    get_settings.cache_clear()
    session = get_session_maker()()
    try:
        agent_session = AgentSessionRepository(session).create_session("tool replay")
        audit = AgentToolCallRepository(session, session_id=agent_session.id)
        registry = _registry(tmp_path, monkeypatch, audit_sink=audit)

        result = registry.execute(
            "list_artifacts",
            {"namespace": "job-1"},
            context_snapshot={"episode_id": "episode-1"},
        )

        calls = audit.list_for_session(agent_session.id)
    finally:
        session.close()

    assert result.status == AgentToolResultStatus.SUCCEEDED
    assert len(calls) == 1
    assert calls[0].tool_name == "list_artifacts"
    assert calls[0].safety_class == "read_only"
    assert calls[0].status == "succeeded"
    assert calls[0].input_json == {"namespace": "job-1"}
    assert calls[0].context_snapshot_json == {"episode_id": "episode-1"}
    assert calls[0].result_json["output"]["count"] == 5


def _registry(tmp_path, monkeypatch, audit_sink=None):
    monkeypatch.setenv("CONTENT_FACTORY_ARTIFACT_ROOT", str(tmp_path))
    get_settings.cache_clear()
    return build_default_agent_tool_registry(audit_sink=audit_sink)


class _MemoryAuditSink(AgentToolAuditSink):
    def __init__(self) -> None:
        self.records: list[AgentToolCallRecord] = []

    def record_tool_call(self, record: AgentToolCallRecord) -> None:
        self.records.append(record)


class _FailingAuditSink(AgentToolAuditSink):
    def record_tool_call(self, record: AgentToolCallRecord) -> None:
        raise RuntimeError("audit down")


def _write_tool_fixtures(tmp_path) -> dict[str, str]:
    video = tmp_path / "job-1" / "video" / "clip.mp4"
    variant = tmp_path / "job-1" / "video" / "clip-b.mp4"
    keyframe = tmp_path / "job-1" / "image" / "clip_0001.jpg"
    screenshot = tmp_path / "job-1" / "screenshot" / "clip_0002.jpg"
    analytics = tmp_path / "job-1" / "json" / "clip.analytics.json"

    for path, content in (
        (video, "video"),
        (variant, "video-variant-longer"),
        (keyframe, "image"),
        (screenshot, "screenshot"),
        (analytics, json.dumps({"metrics": {"views": 1200, "likes": 88, "retention_rate": 0.42}})),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    video.with_name("clip.mp4.metadata.json").write_text(
        json.dumps(
            {
                "duration_seconds": 12.5,
                "width": 1080,
                "height": 1920,
                "metrics": {"retention_rate": 0.42},
            }
        )
    )
    variant.with_name("clip-b.mp4.metadata.json").write_text(
        json.dumps({"duration_seconds": 12.7, "metrics": {"retention_rate": 0.38}})
    )

    return {
        "video": "job-1/video/clip.mp4",
        "variant": "job-1/video/clip-b.mp4",
        "analytics": "job-1/json/clip.analytics.json",
    }


def _mark_invoked(state: dict[str, bool]):
    state["called"] = True
    raise AssertionError("handler should not be called for non-read-only tools")


def _slow_success():
    time.sleep(0.05)
    return AgentToolResult.success(output={"ok": True})

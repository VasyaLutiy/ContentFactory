from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import logging
from pathlib import Path
import re
from time import perf_counter
from typing import Any

from app.artifacts.storage import file_sha256
from app.core.config import Settings, get_settings
from app.schemas.common import AssetKind


logger = logging.getLogger(__name__)


class AgentToolSafetyClass(StrEnum):
    READ_ONLY = "read_only"
    CHEAP_WRITE = "cheap_write"
    EXPENSIVE_JOB = "expensive_job"
    EXTERNAL_API_COST = "external_api_cost"
    DESTRUCTIVE = "destructive"


class AgentToolResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class AgentArtifactRef:
    artifact_id: str
    path: str
    kind: str
    namespace: str
    size_bytes: int
    checksum_sha256: str | None = None


@dataclass(frozen=True)
class AgentMetric:
    name: str
    value: int | float | str | bool
    unit: str | None = None
    source_artifact_id: str | None = None


@dataclass(frozen=True)
class AgentToolError:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentToolResult:
    status: AgentToolResultStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[AgentArtifactRef, ...] = ()
    metrics: tuple[AgentMetric, ...] = ()
    warnings: tuple[str, ...] = ()
    error: AgentToolError | None = None

    @classmethod
    def success(
        cls,
        *,
        output: Mapping[str, Any] | None = None,
        artifact_refs: tuple[AgentArtifactRef, ...] = (),
        metrics: tuple[AgentMetric, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> AgentToolResult:
        return cls(
            status=AgentToolResultStatus.SUCCEEDED,
            output=output or {},
            artifact_refs=artifact_refs,
            metrics=metrics,
            warnings=warnings,
        )

    @classmethod
    def failure(
        cls,
        *,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> AgentToolResult:
        return cls(
            status=AgentToolResultStatus.FAILED,
            error=AgentToolError(code=code, message=message, details=details or {}),
        )


@dataclass(frozen=True)
class AgentToolMetadata:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    safety_class: AgentToolSafetyClass
    timeout_seconds: float
    cost_hint: str
    audit_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentToolCallRecord:
    tool_name: str
    safety_class: str
    input: Mapping[str, Any]
    result: AgentToolResult
    context_snapshot: Mapping[str, Any]
    duration_ms: int
    created_at: datetime


AgentToolHandler = Callable[[Mapping[str, Any]], AgentToolResult]


@dataclass(frozen=True)
class AgentTool:
    metadata: AgentToolMetadata
    handler: AgentToolHandler


class AgentToolAuditSink:
    def record_tool_call(self, record: AgentToolCallRecord) -> None:
        raise NotImplementedError


class AgentToolRegistry:
    _EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-tool")

    def __init__(self, audit_sink: AgentToolAuditSink | None = None) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._audit_sink = audit_sink

    def register(self, tool: AgentTool) -> None:
        if tool.metadata.name in self._tools:
            raise ValueError(f"Agent tool {tool.metadata.name!r} is already registered.")
        self._tools[tool.metadata.name] = tool

    def metadata(self) -> tuple[AgentToolMetadata, ...]:
        return tuple(tool.metadata for tool in self._tools.values())

    def list_tools(self) -> tuple[AgentToolMetadata, ...]:
        return self.metadata()

    def llm_tool_specs(self):
        from app.providers.llm.types import LLMToolSpec

        return tuple(
            LLMToolSpec(
                name=tool.metadata.name,
                description=tool.metadata.description,
                input_schema=tool.metadata.input_schema,
            )
            for tool in self._tools.values()
            if tool.metadata.safety_class == AgentToolSafetyClass.READ_ONLY
        )

    def get(self, name: str) -> AgentToolMetadata | None:
        tool = self._tools.get(name)
        return tool.metadata if tool else None

    def execute(
        self,
        name: str,
        input_data: Mapping[str, Any],
        *,
        context_snapshot: Mapping[str, Any] | None = None,
    ) -> AgentToolResult:
        started = perf_counter()
        tool = self._tools.get(name)
        if tool is None:
            result = AgentToolResult.failure(
                code="unknown_tool",
                message=f"Agent tool {name!r} is not registered.",
                details={"tool_name": name},
            )
            self._record_audit(
                AgentToolCallRecord(
                    tool_name=name,
                    safety_class="unknown",
                    input=dict(input_data),
                    result=result,
                    context_snapshot=context_snapshot or {},
                    duration_ms=max(0, int((perf_counter() - started) * 1000)),
                    created_at=datetime.now(timezone.utc),
                )
            )
            return result

        schema_error = validate_json_object(input_data, tool.metadata.input_schema)
        if schema_error:
            result = AgentToolResult.failure(
                code="invalid_tool_input",
                message=schema_error,
                details={"tool_name": name},
            )
        elif tool.metadata.safety_class != AgentToolSafetyClass.READ_ONLY:
            result = AgentToolResult.failure(
                code="approval_required",
                message=f"Tool {name!r} requires approval before execution.",
                details={"safety_class": tool.metadata.safety_class.value},
            )
        else:
            try:
                result = self._execute_with_timeout(
                    tool=tool,
                    input_data=input_data,
                )
            except TimeoutError:
                result = AgentToolResult.failure(
                    code="tool_timeout",
                    message=(
                        f"Tool {name!r} timed out after {tool.metadata.timeout_seconds:.2f}s."
                    ),
                    details={
                        "tool_name": name,
                        "timeout_seconds": tool.metadata.timeout_seconds,
                    },
                )
            except Exception as exc:
                result = AgentToolResult.failure(
                    code="tool_execution_failed",
                    message=str(exc),
                    details={"tool_name": name},
                )

        self._record_audit(
            AgentToolCallRecord(
                tool_name=name,
                safety_class=tool.metadata.safety_class.value,
                input=dict(input_data),
                result=result,
                context_snapshot=context_snapshot or {},
                duration_ms=max(0, int((perf_counter() - started) * 1000)),
                created_at=datetime.now(timezone.utc),
            )
        )
        error_code = result.error.code if result.error else None
        logger.info(
            "agent_tool_execution",
            extra={
                "session_id": (context_snapshot or {}).get("session_id"),
                "message_id": (context_snapshot or {}).get("message_id"),
                "tool_name": name,
                "latency_ms": max(0, int((perf_counter() - started) * 1000)),
                "timeout_seconds": tool.metadata.timeout_seconds,
                "retry_count": 0,
                "status": result.status.value,
                "error_code": error_code,
            },
        )
        return result

    @staticmethod
    def _execute_with_timeout(*, tool: AgentTool, input_data: Mapping[str, Any]) -> AgentToolResult:
        future = AgentToolRegistry._EXECUTOR.submit(tool.handler, input_data)
        try:
            return future.result(timeout=tool.metadata.timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError("Tool execution timed out") from exc

    def _record_audit(self, record: AgentToolCallRecord) -> None:
        if not self._audit_sink:
            return
        try:
            self._audit_sink.record_tool_call(record)
        except Exception:
            logger.exception("Failed to persist agent tool call audit record.")


def build_default_agent_tool_registry(
    settings: Settings | None = None,
    *,
    audit_sink: AgentToolAuditSink | None = None,
) -> AgentToolRegistry:
    resolved = settings or get_settings()
    tools = ReadOnlyAgentTools(resolved.artifact_root)
    registry = AgentToolRegistry(audit_sink=audit_sink)
    for tool in tools.tool_definitions():
        registry.register(tool)
    return registry


class ReadOnlyAgentTools:
    def __init__(self, artifact_root: Path) -> None:
        self.artifact_root = artifact_root

    def tool_definitions(self) -> tuple[AgentTool, ...]:
        return (
            AgentTool(self._list_artifacts_metadata(), self.list_artifacts),
            AgentTool(self._inspect_video_metadata(), self.inspect_video),
            AgentTool(self._extract_keyframes_metadata(), self.extract_keyframes),
            AgentTool(self._analyze_tiktok_stats_metadata(), self.analyze_tiktok_stats),
            AgentTool(self._compare_variants_metadata(), self.compare_variants),
            AgentTool(self._prepare_caption_pack_metadata(), self.prepare_caption_pack),
            AgentTool(self._recommend_next_edit_metadata(), self.recommend_next_edit),
        )

    def list_artifacts(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        namespace = str(input_data["namespace"]) if input_data.get("namespace") else None
        kind = str(input_data["kind"]) if input_data.get("kind") else None
        refs = tuple(self._iter_artifacts(namespace=namespace, kind=kind))
        return AgentToolResult.success(
            output={"count": len(refs), "artifacts": [ref.__dict__ for ref in refs]},
            artifact_refs=refs,
        )

    def inspect_video(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        resolved = self._resolve_artifact(input_data, allowed_kinds={AssetKind.VIDEO.value})
        if isinstance(resolved, AgentToolResult):
            return resolved
        ref, path = resolved
        metadata = self._read_sidecar_json(path)
        output = {
            "artifact": ref.__dict__,
            "extension": path.suffix.lower(),
            "duration_seconds": metadata.get("duration_seconds"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "created_at": self._mtime(path),
        }
        warnings = ()
        if not metadata:
            warnings = ("No video metadata sidecar found; returning filesystem inspection only.",)
        return AgentToolResult.success(output=output, artifact_refs=(ref,), warnings=warnings)

    def extract_keyframes(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        resolved = self._resolve_artifact(input_data, allowed_kinds={AssetKind.VIDEO.value})
        if isinstance(resolved, AgentToolResult):
            return resolved
        ref, path = resolved
        namespace = ref.namespace
        stem = path.stem
        keyframes = tuple(
            candidate
            for candidate in self._iter_artifacts(namespace=namespace, kind=AssetKind.IMAGE.value)
            if Path(candidate.path).stem.startswith(stem)
        )
        screenshots = tuple(
            candidate
            for candidate in self._iter_artifacts(
                namespace=namespace,
                kind=AssetKind.SCREENSHOT.value,
            )
            if Path(candidate.path).stem.startswith(stem)
        )
        refs = keyframes + screenshots
        return AgentToolResult.success(
            output={
                "source_artifact_id": ref.artifact_id,
                "count": len(refs),
                "keyframes": [item.__dict__ for item in refs],
            },
            artifact_refs=(ref,) + refs,
            warnings=()
            if refs
            else ("No existing keyframe artifacts matched the selected video.",),
        )

    def analyze_tiktok_stats(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        namespace = str(input_data["namespace"]) if input_data.get("namespace") else None
        artifact_id = str(input_data["artifact_id"]) if input_data.get("artifact_id") else None
        refs = tuple(self._iter_artifacts(namespace=namespace, kind=AssetKind.JSON.value))
        metrics: list[AgentMetric] = []
        warnings: list[str] = []
        matched_refs: list[AgentArtifactRef] = []
        for ref in refs:
            if artifact_id and ref.artifact_id != artifact_id:
                continue
            path = self._path_for_ref(ref)
            payload = self._read_json(path)
            if not payload:
                warnings.append(f"Skipping non-JSON analytics artifact {ref.artifact_id}.")
                continue
            matched_refs.append(ref)
            metrics.extend(_metrics_from_payload(payload, ref.artifact_id))
        return AgentToolResult.success(
            output={
                "artifact_count": len(matched_refs),
                "metrics": [metric.__dict__ for metric in metrics],
            },
            artifact_refs=tuple(matched_refs),
            metrics=tuple(metrics),
            warnings=tuple(warnings),
        )

    def compare_variants(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        artifact_ids = tuple(str(item) for item in input_data.get("artifact_ids", ()))
        refs: list[AgentArtifactRef] = []
        rows: list[dict[str, Any]] = []
        for artifact_id in artifact_ids:
            resolved = self._resolve_artifact({"artifact_id": artifact_id})
            if isinstance(resolved, AgentToolResult):
                return resolved
            ref, path = resolved
            refs.append(ref)
            metrics = _metrics_from_payload(self._read_sidecar_json(path), ref.artifact_id)
            rows.append(
                {
                    "artifact_id": ref.artifact_id,
                    "kind": ref.kind,
                    "size_bytes": ref.size_bytes,
                    "metrics": [metric.__dict__ for metric in metrics],
                }
            )
        ranked = sorted(rows, key=lambda item: item["size_bytes"], reverse=True)
        return AgentToolResult.success(
            output={
                "variants": rows,
                "largest_artifact_id": ranked[0]["artifact_id"] if ranked else None,
            },
            artifact_refs=tuple(refs),
            warnings=("No analytics sidecars found; comparison uses artifact metadata only.",)
            if all(not row["metrics"] for row in rows)
            else (),
        )

    def prepare_caption_pack(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        resolved = self._resolve_artifact(input_data)
        if isinstance(resolved, AgentToolResult):
            return resolved
        ref, path = resolved
        metadata = self._read_sidecar_json(path)
        metrics = _metrics_from_payload(metadata, ref.artifact_id)
        metric_lookup = _metric_lookup(metrics)
        title = _clean_phrase(
            str(
                input_data.get("episode_title")
                or metadata.get("episode_title")
                or metadata.get("title")
                or _title_from_stem(path.stem)
            )
        )
        campaign = _clean_phrase(
            str(input_data.get("campaign") or metadata.get("campaign") or ref.namespace)
        )
        platform = str(input_data.get("platform") or "tiktok")
        objective = _clean_phrase(
            str(
                input_data.get("objective")
                or metadata.get("objective")
                or "Improve first two second retention."
            )
        )
        retention_signal = _retention_signal(
            metric_lookup,
            ("first_2s_retention", "first_two_second_retention", "retention_rate"),
        )
        hook = _caption_hook(metadata, retention_signal.value)
        caption = _clamp_text(
            f"{hook} {title}. Follow the cut, then pick the next detail to test.",
            max_chars=180,
        )
        hashtags = _hashtags_for(campaign, title, platform)
        first_comment = _clamp_text(
            f"Which beat should we improve next: hook, pacing, or the final reveal?",
            max_chars=140,
        )
        strategy_note = _strategy_note(
            objective,
            retention_signal,
            _text_beat_policy_note(metadata),
        )
        evidence = _caption_evidence(ref, metric_lookup, metadata)
        memory_candidates = [
            {
                "type": "experiment_note",
                "summary": f"Caption pack prepared for artifact {ref.artifact_id}.",
                "artifact_ids": [ref.artifact_id],
                "objective": _memory_safe_text(objective),
                "evidence": [item["summary"] for item in evidence],
            }
        ]
        warnings = ()
        if not metadata:
            warnings = ("No metadata sidecar found; caption pack uses artifact identity only.",)
        return AgentToolResult.success(
            output={
                "caption_pack": {
                    "platform": platform,
                    "caption": caption,
                    "hashtags": hashtags,
                    "first_comment": first_comment,
                    "strategy_note": strategy_note,
                    "artifact_refs": [ref.__dict__],
                    "evidence": evidence,
                    "memory_candidates": memory_candidates,
                }
            },
            artifact_refs=(ref,),
            metrics=tuple(metrics),
            warnings=warnings,
        )

    def recommend_next_edit(self, input_data: Mapping[str, Any]) -> AgentToolResult:
        artifact_ids = tuple(str(item) for item in input_data.get("artifact_ids", ()))
        refs: list[AgentArtifactRef] = []
        paths: list[Path] = []
        if artifact_ids:
            for artifact_id in artifact_ids:
                resolved = self._resolve_artifact({"artifact_id": artifact_id})
                if isinstance(resolved, AgentToolResult):
                    return resolved
                ref, path = resolved
                refs.append(ref)
                paths.append(path)
        else:
            resolved = self._resolve_artifact(input_data)
            if isinstance(resolved, AgentToolResult):
                return resolved
            ref, path = resolved
            refs.append(ref)
            paths.append(path)

        recommendations: list[dict[str, Any]] = []
        metrics: list[AgentMetric] = []
        warnings: list[str] = []
        for ref, path in zip(refs, paths, strict=True):
            metadata = self._read_sidecar_json(path)
            artifact_metrics = _metrics_from_payload(metadata, ref.artifact_id)
            metrics.extend(artifact_metrics)
            metric_lookup = _metric_lookup(artifact_metrics)
            if not metadata:
                warnings.append(
                    (
                        f"No metadata sidecar found for {ref.artifact_id}; "
                        "using artifact identity only."
                    )
                )
            recommendations.extend(
                _recommendations_for_artifact(
                    ref=ref,
                    metadata=metadata,
                    metric_lookup=metric_lookup,
                    objective=str(input_data.get("objective") or ""),
                )
            )

        ranked_variant = _rank_retention_winner(refs, paths)
        if ranked_variant:
            recommendations.append(ranked_variant)
        if not recommendations and refs:
            recommendations.append(
                {
                    "kind": "production_recommendation",
                    "artifact_ids": [refs[0].artifact_id],
                    "reason": "No clear retention or text-beat risk was found in local sidecars.",
                    "evidence": ["Artifact has no actionable metric deltas in available metadata."],
                    "next_action": (
                        "Publish this variant as the control and collect a fresh "
                        "analytics snapshot."
                    ),
                    "confidence": "low",
                }
            )
        memory_candidates = [
            {
                "type": "variant_history",
                "summary": recommendation["reason"],
                "artifact_ids": recommendation["artifact_ids"],
                "next_action": recommendation["next_action"],
            }
            for recommendation in recommendations[:3]
        ]
        return AgentToolResult.success(
            output={
                "recommendations": recommendations,
                "memory_candidates": memory_candidates,
                "artifact_refs": [ref.__dict__ for ref in refs],
            },
            artifact_refs=tuple(refs),
            metrics=tuple(metrics),
            warnings=tuple(warnings),
        )

    def _iter_artifacts(
        self,
        *,
        namespace: str | None = None,
        kind: str | None = None,
    ) -> tuple[AgentArtifactRef, ...]:
        if not self.artifact_root.exists():
            return ()
        namespace_path = self._safe_namespace_path(namespace) if namespace else None
        if namespace and namespace_path is None:
            return ()
        roots = (
            [namespace_path]
            if namespace
            else sorted(self.artifact_root.iterdir())
        )
        refs: list[AgentArtifactRef] = []
        for namespace_dir in roots:
            if not namespace_dir.is_dir():
                continue
            kind_dirs = [namespace_dir / kind] if kind else sorted(namespace_dir.iterdir())
            for kind_dir in kind_dirs:
                if not kind_dir.is_dir():
                    continue
                for path in sorted(item for item in kind_dir.iterdir() if item.is_file()):
                    if path.name.endswith(".metadata.json"):
                        continue
                    refs.append(self._ref_for_path(path))
        return tuple(refs)

    def _resolve_artifact(
        self,
        input_data: Mapping[str, Any],
        *,
        allowed_kinds: set[str] | None = None,
    ) -> tuple[AgentArtifactRef, Path] | AgentToolResult:
        artifact_id = str(input_data["artifact_id"]) if input_data.get("artifact_id") else None
        path_value = str(input_data["path"]) if input_data.get("path") else None
        if artifact_id:
            matches = [ref for ref in self._iter_artifacts() if ref.artifact_id == artifact_id]
            if not matches:
                return AgentToolResult.failure(
                    code="artifact_not_found",
                    message=f"Artifact {artifact_id!r} was not found.",
                )
            ref = matches[0]
            path = self._path_for_ref(ref)
        elif path_value:
            path = self._safe_artifact_path(path_value)
            if path is None or not path.is_file():
                return AgentToolResult.failure(
                    code="artifact_not_found",
                    message=f"Artifact path {path_value!r} was not found.",
                )
            ref = self._ref_for_path(path)
        else:
            return AgentToolResult.failure(
                code="missing_artifact_ref",
                message="Provide artifact_id or path.",
            )
        if allowed_kinds and ref.kind not in allowed_kinds:
            return AgentToolResult.failure(
                code="invalid_artifact_kind",
                message=(
                    f"Artifact {ref.artifact_id!r} is {ref.kind}, "
                    f"expected {sorted(allowed_kinds)}."
                ),
            )
        return ref, path

    def _safe_artifact_path(self, path_value: str) -> Path | None:
        candidate = Path(path_value)
        if not candidate.is_absolute():
            candidate = self.artifact_root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.artifact_root.resolve())
        except ValueError:
            return None
        return resolved

    def _safe_namespace_path(self, namespace: str | None) -> Path | None:
        if not namespace:
            return None
        candidate = self.artifact_root / namespace
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.artifact_root.resolve())
        except ValueError:
            return None
        return resolved

    def _ref_for_path(self, path: Path) -> AgentArtifactRef:
        relative = path.resolve().relative_to(self.artifact_root.resolve())
        namespace = relative.parts[0] if len(relative.parts) >= 1 else ""
        kind = relative.parts[1] if len(relative.parts) >= 2 else ""
        artifact_id = "/".join(relative.parts)
        return AgentArtifactRef(
            artifact_id=artifact_id,
            path=str(relative),
            kind=kind,
            namespace=namespace,
            size_bytes=path.stat().st_size,
            checksum_sha256=file_sha256(path),
        )

    def _path_for_ref(self, ref: AgentArtifactRef) -> Path:
        return self.artifact_root / ref.path

    def _read_sidecar_json(self, path: Path) -> Mapping[str, Any]:
        return self._read_json(path.with_name(f"{path.name}.metadata.json"))

    @staticmethod
    def _read_json(path: Path) -> Mapping[str, Any]:
        if not path.is_file():
            return {}
        import json

        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, Mapping) else {}

    @staticmethod
    def _mtime(path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

    @staticmethod
    def _list_artifacts_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="list_artifacts",
            description="List registered artifacts under the configured artifact root.",
            input_schema=_object_schema(
                properties={
                    "namespace": {"type": "string"},
                    "kind": {"type": "string", "enum": [item.value for item in AssetKind]},
                }
            ),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"]},
        )

    @staticmethod
    def _inspect_video_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="inspect_video",
            description="Inspect an existing video artifact and optional metadata sidecar.",
            input_schema=_artifact_ref_schema(),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"]},
        )

    @staticmethod
    def _extract_keyframes_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="extract_keyframes",
            description="Return existing keyframe/screenshot artifacts for a video.",
            input_schema=_artifact_ref_schema(),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"], "mutates": []},
        )

    @staticmethod
    def _analyze_tiktok_stats_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="analyze_tiktok_stats",
            description="Read local TikTok analytics JSON artifacts and normalize metrics.",
            input_schema=_object_schema(
                properties={
                    "namespace": {"type": "string"},
                    "artifact_id": {"type": "string"},
                }
            ),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"]},
        )

    @staticmethod
    def _compare_variants_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="compare_variants",
            description="Compare artifact variants using local metadata and analytics sidecars.",
            input_schema=_object_schema(
                required=("artifact_ids",),
                properties={
                    "artifact_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                    }
                },
            ),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"]},
        )

    @staticmethod
    def _prepare_caption_pack_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="prepare_caption_pack",
            description=(
                "Prepare a posting-ready caption, hashtags, first comment, strategy note, "
                "and curated memory candidates for a selected artifact."
            ),
            input_schema=_object_schema(
                properties={
                    "artifact_id": {"type": "string"},
                    "path": {"type": "string"},
                    "campaign": {"type": "string"},
                    "episode_title": {"type": "string"},
                    "objective": {"type": "string"},
                    "platform": {
                        "type": "string",
                        "enum": ["tiktok", "youtube_shorts", "instagram_reels"],
                    },
                }
            ),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"]},
        )

    @staticmethod
    def _recommend_next_edit_metadata() -> AgentToolMetadata:
        return AgentToolMetadata(
            name="recommend_next_edit",
            description=(
                "Return production recommendation cards grounded in artifact metadata, "
                "TikTok metrics, first-two-second retention, and text-beat policy."
            ),
            input_schema=_object_schema(
                properties={
                    "artifact_id": {"type": "string"},
                    "path": {"type": "string"},
                    "artifact_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "objective": {"type": "string"},
                }
            ),
            output_schema=_object_schema(),
            safety_class=AgentToolSafetyClass.READ_ONLY,
            timeout_seconds=2.0,
            cost_hint="local_io_only",
            audit_metadata={"reads": ["artifact_root"]},
        )


def validate_json_object(data: Mapping[str, Any], schema: Mapping[str, Any]) -> str | None:
    if schema.get("type", "object") != "object":
        return None
    required = tuple(schema.get("required", ()))
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        properties = {}
    for key in required:
        if key not in data:
            return f"Missing required field {key!r}."
    if schema.get("additionalProperties", False) is False:
        extra = sorted(set(data) - set(properties))
        if extra:
            return f"Unexpected field {extra[0]!r}."
    for key, value in data.items():
        if key not in properties:
            continue
        error = _validate_value(key, value, properties[key])
        if error:
            return error
    return None


def _validate_value(key: str, value: Any, schema: Mapping[str, Any]) -> str | None:
    expected = schema.get("type")
    if expected == "string" and not isinstance(value, str):
        return f"Field {key!r} must be a string."
    if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return f"Field {key!r} must be an integer."
    if expected == "number" and not isinstance(value, (int, float)):
        return f"Field {key!r} must be a number."
    if expected == "boolean" and not isinstance(value, bool):
        return f"Field {key!r} must be a boolean."
    if expected == "array":
        if not isinstance(value, list | tuple):
            return f"Field {key!r} must be an array."
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            return f"Field {key!r} must contain at least {min_items} items."
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for item in value:
                error = _validate_value(f"{key}[]", item, item_schema)
                if error:
                    return error
    if expected == "object" and not isinstance(value, Mapping):
        return f"Field {key!r} must be an object."
    enum = schema.get("enum")
    if enum and value not in enum:
        return f"Field {key!r} must be one of {list(enum)!r}."
    return None


def _metrics_from_payload(payload: Mapping[str, Any], artifact_id: str) -> list[AgentMetric]:
    metrics: list[AgentMetric] = []
    metric_payload = payload.get("metrics", payload)
    if not isinstance(metric_payload, Mapping):
        return metrics
    for name, value in sorted(metric_payload.items()):
        if isinstance(value, int | float | str | bool):
            metrics.append(
                AgentMetric(
                    name=str(name),
                    value=value,
                    unit=_unit_for_metric(str(name)),
                    source_artifact_id=artifact_id,
                )
            )
    return metrics


def _unit_for_metric(name: str) -> str | None:
    if name.endswith("_rate") or "retention" in name:
        return "ratio"
    if name in {"views", "likes", "comments", "shares"}:
        return "count"
    if name.endswith("_seconds"):
        return "seconds"
    return None


def _metric_lookup(metrics: list[AgentMetric]) -> dict[str, AgentMetric]:
    return {metric.name: metric for metric in metrics}


def _numeric_metric(
    metrics: Mapping[str, AgentMetric],
    names: tuple[str, ...],
) -> float | None:
    for name in names:
        metric = metrics.get(name)
        if metric and isinstance(metric.value, int | float) and not isinstance(metric.value, bool):
            return float(metric.value)
    return None


@dataclass(frozen=True)
class RetentionSignal:
    name: str | None
    label: str
    value: float | None


def _retention_signal(
    metrics: Mapping[str, AgentMetric],
    names: tuple[str, ...],
) -> RetentionSignal:
    labels = {
        "first_2s_retention": "First-two-second retention",
        "first_two_second_retention": "First-two-second retention",
        "retention_rate": "Overall retention rate",
    }
    for name in names:
        metric = metrics.get(name)
        if metric and isinstance(metric.value, int | float) and not isinstance(metric.value, bool):
            return RetentionSignal(
                name=name,
                label=labels.get(name, name),
                value=float(metric.value),
            )
    return RetentionSignal(name=None, label="Retention signal", value=None)


def _title_from_stem(stem: str) -> str:
    cleaned = re.sub(r"[_-]+", " ", stem).strip()
    return cleaned.title() if cleaned else "Untitled Cut"


def _clean_phrase(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or "Untitled"


def _clamp_text(value: str, *, max_chars: int) -> str:
    cleaned = _clean_phrase(value)
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 3:
        return cleaned[:max_chars]
    return cleaned[: max(0, max_chars - 3)].rstrip() + "..."


def _caption_hook(metadata: Mapping[str, Any], first_two_retention: float | None) -> str:
    hook = metadata.get("hook")
    if isinstance(hook, str) and hook.strip():
        return _clamp_text(hook, max_chars=80)
    if first_two_retention is not None and first_two_retention < 0.45:
        return "The opening beat is the test."
    return "This cut is ready for a controlled test."


def _memory_safe_text(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9 .,;:!?()/_-]+", " ", value)
    return _clamp_text(sanitized, max_chars=160)


def _hashtags_for(campaign: str, title: str, platform: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]+", f"{campaign} {title}".lower())
    tags: list[str] = []
    for word in words:
        if len(word) < 3 or word in {"the", "and", "for", "with"}:
            continue
        tag = f"#{word[:24]}"
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= 4:
            break
    defaults = {
        "tiktok": ["#tiktok", "#contentfactory"],
        "youtube_shorts": ["#shorts", "#contentfactory"],
        "instagram_reels": ["#reels", "#contentfactory"],
    }
    for tag in defaults.get(platform, defaults["tiktok"]):
        if tag not in tags:
            tags.append(tag)
    return tags[:6]


def _text_beats(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    beats = metadata.get("text_beats", metadata.get("on_screen_text_beats", ()))
    return [beat for beat in beats if isinstance(beat, Mapping)] if isinstance(beats, list) else []


def _first_text_start(metadata: Mapping[str, Any]) -> float | None:
    starts: list[float] = []
    for beat in _text_beats(metadata):
        value = beat.get("start", beat.get("start_seconds"))
        if isinstance(value, int | float) and not isinstance(value, bool):
            starts.append(float(value))
    return min(starts) if starts else None


def _text_beat_policy_note(metadata: Mapping[str, Any]) -> str:
    first_start = _first_text_start(metadata)
    if first_start is None:
        return "No text-beat sidecar was found; validate hook text before publishing."
    if first_start > 0.3:
        return f"First on-screen text starts at {first_start:.2f}s; policy target is <=0.30s."
    return f"First on-screen text starts at {first_start:.2f}s and meets the <=0.30s hook policy."


def _strategy_note(
    objective: str,
    retention_signal: RetentionSignal,
    text_policy_note: str,
) -> str:
    metric_note = (
        f"{retention_signal.label} is {retention_signal.value:.0%}; "
        if retention_signal.value is not None
        else "No retention metric is available; "
    )
    return _clamp_text(f"{metric_note}{text_policy_note} Objective: {objective}", max_chars=260)


def _caption_evidence(
    ref: AgentArtifactRef,
    metric_lookup: Mapping[str, AgentMetric],
    metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence = [
        {
            "type": "artifact",
            "artifact_id": ref.artifact_id,
            "summary": f"Posting pack is linked to {ref.kind} artifact {ref.artifact_id}.",
        }
    ]
    retention = _retention_signal(
        metric_lookup,
        ("first_2s_retention", "first_two_second_retention", "retention_rate"),
    )
    if retention.value is not None:
        evidence.append(
            {
                "type": "metric",
                "metric": retention.name,
                "value": retention.value,
                "summary": f"{retention.label} is {retention.value:.0%}.",
            }
        )
    evidence.append(
        {
            "type": "policy",
            "summary": _text_beat_policy_note(metadata),
        }
    )
    return evidence


def _recommendations_for_artifact(
    *,
    ref: AgentArtifactRef,
    metadata: Mapping[str, Any],
    metric_lookup: Mapping[str, AgentMetric],
    objective: str,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    retention = _retention_signal(
        metric_lookup,
        ("first_2s_retention", "first_two_second_retention", "retention_rate"),
    )
    if retention.value is not None and retention.value < 0.45:
        recommendations.append(
            {
                "kind": "production_recommendation",
                "artifact_ids": [ref.artifact_id],
                "reason": "Opening retention is below the production threshold.",
                "evidence": [
                    f"{retention.label} is {retention.value:.0%}.",
                    f"Artifact: {ref.artifact_id}.",
                ],
                "next_action": (
                    "Cut a variant with a clearer first-frame hook and re-test "
                    "the first two seconds."
                ),
                "confidence": "medium",
            }
        )
    first_start = _first_text_start(metadata)
    if first_start is None or first_start > 0.3:
        policy_summary = (
            "No text-beat timing was found."
            if first_start is None
            else f"First text beat starts at {first_start:.2f}s."
        )
        recommendations.append(
            {
                "kind": "proposed_edit_action",
                "artifact_ids": [ref.artifact_id],
                "reason": "Hook text does not satisfy the first 0.3 second policy.",
                "evidence": [policy_summary, "Policy target: first text beat at or before 0.30s."],
                "next_action": "Add a short burned-in hook text beat at 0.00-0.30s.",
                "confidence": "high",
            }
        )
    if objective:
        for recommendation in recommendations:
            recommendation["objective"] = objective
    return recommendations


def _rank_retention_winner(
    refs: list[AgentArtifactRef],
    paths: list[Path],
) -> dict[str, Any] | None:
    if len(refs) < 2:
        return None
    scored: list[tuple[float, AgentArtifactRef]] = []
    for ref, path in zip(refs, paths, strict=True):
        lookup = _metric_lookup(_metrics_from_payload(_read_json_sidecar(path), ref.artifact_id))
        score = _numeric_metric(
            lookup,
            ("retention_rate", "first_2s_retention", "first_two_second_retention"),
        )
        if score is not None:
            scored.append((score, ref))
    if len(scored) < 2:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    winner_score, winner = scored[0]
    loser_score, loser = scored[-1]
    if winner.artifact_id == loser.artifact_id:
        return None
    return {
        "kind": "production_recommendation",
        "artifact_ids": [winner.artifact_id, loser.artifact_id],
        "reason": "One variant has the strongest available retention signal.",
        "evidence": [
            f"{winner.artifact_id}: {winner_score:.0%} retention.",
            f"{loser.artifact_id}: {loser_score:.0%} retention.",
        ],
        "next_action": (
            f"Promote {winner.artifact_id} as the control and archive the "
            "lower-retention variant."
        ),
        "confidence": "medium",
    }


def _read_json_sidecar(path: Path) -> Mapping[str, Any]:
    sidecar = path.with_name(f"{path.name}.metadata.json")
    if not sidecar.is_file():
        return {}
    import json

    try:
        payload = json.loads(sidecar.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _object_schema(
    *,
    required: tuple[str, ...] = (),
    properties: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": dict(properties or {}),
        "additionalProperties": False,
    }


def _artifact_ref_schema() -> Mapping[str, Any]:
    return _object_schema(
        properties={
            "artifact_id": {"type": "string"},
            "path": {"type": "string"},
        }
    )

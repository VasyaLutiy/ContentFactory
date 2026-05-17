from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import logging
from pathlib import Path
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
                result = tool.handler(input_data)
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
        return result

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

from dataclasses import dataclass, replace
import os
from pathlib import Path

from app.artifacts.storage import ArtifactStorage
from app.integrations.scripts.execution import (
    ExpectedArtifact,
    LegacyScriptResult,
    require_artifact_namespace,
    run_legacy_command,
)
from app.integrations.scripts.legacy_paths import legacy_script_path
from app.schemas.common import AssetKind


def _comfy_tiktok_output_dir() -> Path:
    return Path(os.getenv("CONTENT_FACTORY_COMFY_OUTPUT_ROOT", "/home/kosmoletc/ComfyUI/output")) / "tiktok"


@dataclass(frozen=True)
class MakeShortRequest:
    prompt: str
    motion: str | None = None
    duration: int = 6
    fps: int = 24
    voice: str | None = None
    music: Path | None = None
    ref: Path | None = None
    out: str | None = None
    text: str | None = None


def build_make_short_command(request: MakeShortRequest) -> list[str]:
    cmd = ["python", str(legacy_script_path("make_short.py")), request.prompt]
    if request.motion:
        cmd.extend(["--motion", request.motion])
    cmd.extend(["--duration", str(request.duration), "--fps", str(request.fps)])
    if request.voice:
        cmd.extend(["--voice", request.voice])
    if request.music:
        cmd.extend(["--music", str(request.music)])
    if request.ref:
        cmd.extend(["--ref", str(request.ref)])
    if request.out:
        cmd.extend(["--out", request.out])
    if request.text:
        cmd.extend(["--text", request.text])
    return cmd


def expected_make_short_artifacts(request: MakeShortRequest) -> tuple[ExpectedArtifact, ...]:
    return (ExpectedArtifact(make_short_output_path(request), AssetKind.VIDEO),)


def run_make_short(
    request: MakeShortRequest,
    *,
    storage: ArtifactStorage | None = None,
    namespace: str | None = None,
) -> LegacyScriptResult:
    require_artifact_namespace(storage=storage, namespace=namespace)
    request = _with_namespaced_default_out(request, storage=storage, namespace=namespace)
    for artifact in expected_make_short_artifacts(request):
        artifact.path.parent.mkdir(parents=True, exist_ok=True)
    return run_legacy_command(
        build_make_short_command(request),
        expected_artifacts=expected_make_short_artifacts(request),
        storage=storage,
        namespace=namespace,
    )


def make_short_output_path(request: MakeShortRequest) -> Path:
    out_name = request.out or f"{_slugify(request.prompt)}.mp4"
    out = Path(out_name)
    if out.is_absolute():
        return out
    return _comfy_tiktok_output_dir() / out


def _with_namespaced_default_out(
    request: MakeShortRequest,
    *,
    storage: ArtifactStorage | None,
    namespace: str | None,
) -> MakeShortRequest:
    if storage is None or request.out is not None:
        return request
    if namespace is None:
        raise ValueError("namespace is required when artifact storage is enabled.")
    return replace(request, out=f"{namespace}_{_slugify(request.prompt)}.mp4")


def _slugify(text: str, max_len: int = 40) -> str:
    out = "".join(char if char.isalnum() else "_" for char in text.lower())
    out = "_".join(filter(None, out.split("_")))[:max_len]
    return out or "short"

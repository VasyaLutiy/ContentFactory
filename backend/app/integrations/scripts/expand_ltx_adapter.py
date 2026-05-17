from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.artifacts.storage import ArtifactStorage
from app.integrations.scripts.execution import ExpectedArtifact, LegacyScriptResult, run_legacy_command
from app.integrations.scripts.legacy_paths import legacy_script_path
from app.schemas.common import AssetKind


@dataclass(frozen=True)
class ExpandLtxRequest:
    workflow: Path
    prompt: str
    image: Path
    out: Path | None = None
    width: int = 576
    height: int = 1024
    fps: int = 24
    duration: int = 6


def build_expand_ltx_command(request: ExpandLtxRequest) -> list[str]:
    cmd = [
        "python",
        str(legacy_script_path("expand_ltx_workflow.py")),
        str(request.workflow),
        "--prompt",
        request.prompt,
        "--image",
        str(request.image),
        "--width",
        str(request.width),
        "--height",
        str(request.height),
        "--fps",
        str(request.fps),
        "--duration",
        str(request.duration),
    ]
    if request.out:
        cmd.extend(["--out", str(request.out)])
    return cmd


def expected_expand_ltx_artifacts(request: ExpandLtxRequest) -> tuple[ExpectedArtifact, ...]:
    if request.out is None:
        return ()
    return (ExpectedArtifact(request.out, AssetKind.WORKFLOW),)


def run_expand_ltx(
    request: ExpandLtxRequest,
    *,
    storage: ArtifactStorage | None = None,
    namespace: str | None = None,
) -> LegacyScriptResult:
    return run_legacy_command(
        build_expand_ltx_command(request),
        expected_artifacts=expected_expand_ltx_artifacts(request),
        storage=storage,
        namespace=namespace,
    )

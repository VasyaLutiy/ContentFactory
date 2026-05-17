from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.integrations.scripts.legacy_paths import legacy_script_path


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


def run_expand_ltx(request: ExpandLtxRequest) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_expand_ltx_command(request),
        check=True,
        capture_output=True,
        text=True,
    )

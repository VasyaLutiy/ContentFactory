from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.integrations.scripts.legacy_paths import legacy_script_path


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


def run_make_short(request: MakeShortRequest) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_make_short_command(request),
        check=True,
        capture_output=True,
        text=True,
    )

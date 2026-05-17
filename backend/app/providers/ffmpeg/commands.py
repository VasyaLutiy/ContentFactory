from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


DEFAULT_FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


@dataclass(frozen=True)
class MuxAudioRequest:
    video: Path
    audio: Path
    out: Path
    audio_volume: float = 1.0
    keep_original_audio: bool = False


@dataclass(frozen=True)
class TextOverlayRequest:
    video: Path
    out: Path
    text: str
    start: float = 0.0
    end: float = 2.5
    font_path: Path = DEFAULT_FONT_PATH
    font_size: int = 64


@dataclass(frozen=True)
class ConcatVideosRequest:
    videos: tuple[Path, ...]
    out: Path


def build_mux_audio_command(request: MuxAudioRequest) -> list[str]:
    if request.keep_original_audio:
        filter_graph = (
            f"[0:a]volume=0.20[base];"
            f"[1:a]volume={request.audio_volume}[voice];"
            f"[base][voice]amix=inputs=2:duration=longest:dropout_transition=0[a]"
        )
    else:
        filter_graph = f"[1:a]volume={request.audio_volume}[a]"

    return [
        "ffmpeg",
        "-y",
        "-i",
        str(request.video),
        "-i",
        str(request.audio),
        "-filter_complex",
        filter_graph,
        "-map",
        "0:v",
        "-map",
        "[a]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(request.out),
    ]


def build_text_overlay_command(request: TextOverlayRequest) -> list[str]:
    escaped_text = _escape_drawtext(request.text)
    filter_graph = (
        f"drawtext=fontfile={request.font_path}:text='{escaped_text}'"
        f":fontsize={request.font_size}:fontcolor=white:bordercolor=black:borderw=6"
        f":x=(w-text_w)/2:y=h*0.20:enable='between(t,{request.start:.2f},{request.end:.2f})'"
    )
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(request.video),
        "-vf",
        filter_graph,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        str(request.out),
    ]


def build_concat_videos_command(request: ConcatVideosRequest, list_file: Path) -> list[str]:
    if not request.videos:
        raise ValueError("At least one video is required for concat.")
    return [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(request.out),
    ]


def write_concat_list(videos: tuple[Path, ...], list_file: Path) -> Path:
    if not videos:
        raise ValueError("At least one video is required for concat.")
    list_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{_escape_concat_path(video)}'" for video in videos]
    list_file.write_text("\n".join(lines) + "\n")
    return list_file


def run_ffmpeg_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\\'")


def _escape_concat_path(path: Path) -> str:
    return str(path).replace("'", r"'\''")

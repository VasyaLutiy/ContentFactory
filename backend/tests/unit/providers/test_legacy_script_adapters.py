from __future__ import annotations

from pathlib import Path
import sys

import pytest

from app.artifacts.storage import ArtifactStorage
from app.core.config import get_settings
from app.integrations.scripts.execution import ExpectedArtifact, run_legacy_command
from app.integrations.scripts.expand_ltx_adapter import (
    ExpandLtxRequest,
    build_expand_ltx_command,
    expected_expand_ltx_artifacts,
)
from app.integrations.scripts.make_short_adapter import (
    MakeShortRequest,
    build_make_short_command,
    expected_make_short_artifacts,
    make_short_output_path,
    run_make_short,
)
from app.integrations.scripts.voice_adapters import (
    DEFAULT_ELEVENLABS_MODEL_ID,
    DEFAULT_ELEVENLABS_VOICE_ID,
    DEFAULT_F5_REF_AUDIO,
    ElevenLabsVoiceRequest,
    F5VoiceRequest,
    build_elevenlabs_voice_command,
    build_f5_voice_command,
    expected_elevenlabs_artifacts,
    expected_f5_artifacts,
    run_f5_voice,
)
from app.providers.ffmpeg.commands import (
    ConcatVideosRequest,
    MuxAudioRequest,
    TextOverlayRequest,
    build_concat_videos_command,
    build_mux_audio_command,
    build_text_overlay_command,
    write_concat_list,
)
from app.schemas.common import AssetKind


def test_build_make_short_command_preserves_legacy_defaults(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    request = MakeShortRequest(prompt="neon city")

    command = build_make_short_command(request)

    assert command == [
        "python",
        str(legacy_root / "make_short.py"),
        "neon city",
        "--duration",
        "6",
        "--fps",
        "24",
    ]


def test_build_make_short_command_includes_optional_args(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    request = MakeShortRequest(
        prompt="lab",
        motion="slow push",
        duration=8,
        fps=30,
        voice="hello",
        music=tmp_path / "music.mp3",
        ref=tmp_path / "ref.png",
        out="lab.mp4",
        text="HOOK",
    )

    command = build_make_short_command(request)

    assert command == [
        "python",
        str(legacy_root / "make_short.py"),
        "lab",
        "--motion",
        "slow push",
        "--duration",
        "8",
        "--fps",
        "30",
        "--voice",
        "hello",
        "--music",
        str(tmp_path / "music.mp3"),
        "--ref",
        str(tmp_path / "ref.png"),
        "--out",
        "lab.mp4",
        "--text",
        "HOOK",
    ]


def test_build_expand_ltx_command_preserves_legacy_defaults(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    request = ExpandLtxRequest(
        workflow=tmp_path / "workflow.json",
        prompt="camera move",
        image=tmp_path / "image.png",
    )

    command = build_expand_ltx_command(request)

    assert command == [
        "python",
        str(legacy_root / "expand_ltx_workflow.py"),
        str(tmp_path / "workflow.json"),
        "--prompt",
        "camera move",
        "--image",
        str(tmp_path / "image.png"),
        "--width",
        "576",
        "--height",
        "1024",
        "--fps",
        "24",
        "--duration",
        "6",
    ]


def test_build_voice_adapter_commands_preserve_defaults(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    video = tmp_path / "clip.mp4"

    eleven = build_elevenlabs_voice_command(
        ElevenLabsVoiceRequest(video=video, text="voice text", out=tmp_path / "out.mp4")
    )
    f5 = build_f5_voice_command(F5VoiceRequest(video=video, text="voice text"))

    assert eleven == [
        "python",
        str(legacy_root / "add_elevenlabs_voice.py"),
        str(video),
        "voice text",
        "--out",
        str(tmp_path / "out.mp4"),
        "--voice-id",
        DEFAULT_ELEVENLABS_VOICE_ID,
        "--model-id",
        DEFAULT_ELEVENLABS_MODEL_ID,
        "--voice-vol",
        "1.25",
    ]
    assert f5 == [
        "python",
        str(legacy_root / "add_voice.py"),
        str(video),
        "voice text",
        "--vol",
        "1.2",
        "--speed",
        "1.0",
        "--ref-audio",
        DEFAULT_F5_REF_AUDIO,
    ]


def test_voice_adapters_expose_expected_video_artifacts(tmp_path) -> None:
    video = tmp_path / "clip.mp4"
    eleven_out = tmp_path / "eleven.mp4"

    assert expected_elevenlabs_artifacts(
        ElevenLabsVoiceRequest(video=video, text="x", out=eleven_out)
    ) == (ExpectedArtifact(eleven_out, AssetKind.VIDEO),)
    assert expected_f5_artifacts(F5VoiceRequest(video=video, text="x")) == (
        ExpectedArtifact(video.resolve().with_name("clip_voice.mp4"), AssetKind.VIDEO),
    )


def test_make_short_and_expand_ltx_artifacts_come_from_command_output(tmp_path, monkeypatch) -> None:
    comfy_output = tmp_path / "comfy-output"
    monkeypatch.setenv("CONTENT_FACTORY_COMFY_OUTPUT_ROOT", str(comfy_output))
    make_request = MakeShortRequest(prompt="x", out=str(tmp_path / "short.mp4"))
    default_make_request = MakeShortRequest(prompt="Neon city!")
    ltx_request = ExpandLtxRequest(
        workflow=tmp_path / "workflow.json",
        prompt="motion",
        image=tmp_path / "image.png",
        out=tmp_path / "workflow_api.json",
    )

    assert expected_make_short_artifacts(make_request) == (
        ExpectedArtifact(tmp_path / "short.mp4", AssetKind.VIDEO),
    )
    assert expected_make_short_artifacts(default_make_request) == (
        ExpectedArtifact(comfy_output / "tiktok" / "neon_city.mp4", AssetKind.VIDEO),
    )
    assert make_short_output_path(MakeShortRequest(prompt="x", out="relative.mp4")) == (
        comfy_output / "tiktok" / "relative.mp4"
    )
    assert expected_expand_ltx_artifacts(ltx_request) == (
        ExpectedArtifact(tmp_path / "workflow_api.json", AssetKind.WORKFLOW),
    )


def test_artifact_namespace_required_when_storage_enabled(tmp_path) -> None:
    output = tmp_path / "output.mp4"
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path(r'" + str(output) + "').write_text('video')",
    ]

    with pytest.raises(ValueError, match="namespace is required"):
        run_legacy_command(
            command,
            expected_artifacts=(ExpectedArtifact(output, AssetKind.VIDEO),),
            storage=ArtifactStorage(tmp_path / "artifacts"),
        )

    assert not output.exists()


def test_run_make_short_validates_namespace_before_mkdir(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    (legacy_root / "make_short.py").write_text("raise SystemExit('should not run')\n")
    out = tmp_path / "nested" / "out.mp4"

    with pytest.raises(ValueError, match="namespace is required"):
        run_make_short(
            MakeShortRequest(prompt="x", out=str(out)),
            storage=ArtifactStorage(tmp_path / "artifacts"),
        )

    assert not out.parent.exists()


def test_run_f5_voice_validates_namespace_before_mkdir(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    (legacy_root / "add_voice.py").write_text("raise SystemExit('should not run')\n")
    video = tmp_path / "clip.mp4"
    video.write_text("source")
    out = tmp_path / "nested" / "voice.mp4"

    with pytest.raises(ValueError, match="namespace is required"):
        run_f5_voice(
            F5VoiceRequest(video=video, text="voice", out=out),
            storage=ArtifactStorage(tmp_path / "artifacts"),
        )

    assert not out.parent.exists()


def test_run_make_short_uses_namespaced_default_output_before_registration(
    tmp_path, monkeypatch
) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    (legacy_root / "make_short.py").write_text(
        "import argparse, os\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('prompt')\n"
        "parser.add_argument('--duration')\n"
        "parser.add_argument('--fps')\n"
        "parser.add_argument('--out')\n"
        "args, _ = parser.parse_known_args()\n"
        "out = Path(os.environ['CONTENT_FACTORY_COMFY_OUTPUT_ROOT']) / 'tiktok' / args.out\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_text('video')\n"
    )
    comfy_output = tmp_path / "comfy-output"
    monkeypatch.setenv("CONTENT_FACTORY_COMFY_OUTPUT_ROOT", str(comfy_output))

    result = run_make_short(
        MakeShortRequest(prompt="Neon city!"),
        storage=ArtifactStorage(tmp_path / "artifacts"),
        namespace="job-14",
    )

    assert "--out" in result.command
    assert "job-14_neon_city.mp4" in result.command
    assert result.artifacts[0].path == (
        tmp_path / "artifacts" / "job-14" / "video" / "job-14_neon_city.mp4"
    )
    assert result.artifacts[0].path.read_text() == "video"


def test_run_f5_voice_uses_namespaced_default_output(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    (legacy_root / "add_voice.py").write_text(
        "import argparse\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('video')\n"
        "parser.add_argument('text')\n"
        "parser.add_argument('--out')\n"
        "parser.add_argument('--vol')\n"
        "parser.add_argument('--speed')\n"
        "parser.add_argument('--ref-audio')\n"
        "args = parser.parse_args()\n"
        "Path(args.out).parent.mkdir(parents=True, exist_ok=True)\n"
        "Path(args.out).write_text('voice-video')\n"
    )
    video = tmp_path / "clip.mp4"
    video.write_text("source")

    result = run_f5_voice(
        F5VoiceRequest(video=video, text="voice"),
        storage=ArtifactStorage(tmp_path / "artifacts"),
        namespace="job-voice",
    )

    expected_output = video.with_name("clip_job-voice_voice.mp4")
    assert str(expected_output) in result.command
    assert result.artifacts[0].path == (
        tmp_path / "artifacts" / "job-voice" / "video" / "clip_job-voice_voice.mp4"
    )
    assert result.artifacts[0].path.read_text() == "voice-video"


def test_run_legacy_command_registers_expected_outputs(tmp_path) -> None:
    output = tmp_path / "output.mp4"
    storage = ArtifactStorage(tmp_path / "artifacts")
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path(r'" + str(output) + "').write_text('video')",
    ]

    result = run_legacy_command(
        command,
        expected_artifacts=(ExpectedArtifact(output, AssetKind.VIDEO),),
        storage=storage,
        namespace="job-14",
    )

    assert result.returncode == 0
    assert result.command == tuple(command)
    assert len(result.artifacts) == 1
    assert result.artifacts[0].path == tmp_path / "artifacts" / "job-14" / "video" / "output.mp4"
    assert result.artifacts[0].path.read_text() == "video"


def test_ffmpeg_mux_audio_command_can_keep_or_replace_original_audio(tmp_path) -> None:
    replace = build_mux_audio_command(
        MuxAudioRequest(video=tmp_path / "v.mp4", audio=tmp_path / "a.mp3", out=tmp_path / "o.mp4")
    )
    keep = build_mux_audio_command(
        MuxAudioRequest(
            video=tmp_path / "v.mp4",
            audio=tmp_path / "a.mp3",
            out=tmp_path / "o.mp4",
            audio_volume=1.25,
            keep_original_audio=True,
        )
    )

    assert replace[:6] == ["ffmpeg", "-y", "-i", str(tmp_path / "v.mp4"), "-i", str(tmp_path / "a.mp3")]
    assert "[1:a]volume=1.0[a]" in replace
    assert any("[base][voice]amix=inputs=2" in item for item in keep)
    assert any("volume=1.25" in item for item in keep)


def test_ffmpeg_text_overlay_escapes_drawtext(tmp_path) -> None:
    command = build_text_overlay_command(
        TextOverlayRequest(video=tmp_path / "v.mp4", out=tmp_path / "o.mp4", text="It's 10:00")
    )

    assert command[:4] == ["ffmpeg", "-y", "-i", str(tmp_path / "v.mp4")]
    assert any(r"It\\'s 10\:00" in item for item in command)
    assert any("between(t,0.00,2.50)" in item for item in command)


def test_ffmpeg_concat_writes_list_and_builds_command(tmp_path) -> None:
    videos = (tmp_path / "a.mp4", tmp_path / "b's.mp4")
    list_file = write_concat_list(videos, tmp_path / "concat" / "inputs.txt")
    escaped_second_path = str(tmp_path / "b's.mp4").replace("'", "'\\''")
    command = build_concat_videos_command(
        ConcatVideosRequest(videos=videos, out=tmp_path / "out.mp4"),
        list_file,
    )

    assert list_file.read_text().splitlines() == [
        f"file '{tmp_path / 'a.mp4'}'",
        f"file '{escaped_second_path}'",
    ]
    assert command == [
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
        str(tmp_path / "out.mp4"),
    ]


def _legacy_root(tmp_path: Path, monkeypatch) -> Path:
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    for name in [
        "make_short.py",
        "expand_ltx_workflow.py",
        "add_elevenlabs_voice.py",
        "add_voice.py",
    ]:
        (legacy_root / name).write_text("#!/usr/bin/env python3\n")
    monkeypatch.setenv("CONTENT_FACTORY_LEGACY_ROOT", str(legacy_root))
    get_settings.cache_clear()
    return legacy_root

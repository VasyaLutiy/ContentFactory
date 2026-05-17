from __future__ import annotations

from dataclasses import dataclass, replace
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


DEFAULT_ELEVENLABS_VOICE_ID = "7Uu6s58Uu5fPHvCtI4QZ"
DEFAULT_ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_F5_REF_AUDIO = "audio/ref_human.wav"


@dataclass(frozen=True)
class ElevenLabsVoiceRequest:
    video: Path
    text: str
    out: Path
    voice_id: str = DEFAULT_ELEVENLABS_VOICE_ID
    model_id: str = DEFAULT_ELEVENLABS_MODEL_ID
    voice_vol: float = 1.25
    keep_original_audio: bool = True


@dataclass(frozen=True)
class F5VoiceRequest:
    video: Path
    text: str
    out: Path | None = None
    voice_vol: float = 1.2
    speed: float = 1.0
    ref_audio: str = DEFAULT_F5_REF_AUDIO


def build_elevenlabs_voice_command(request: ElevenLabsVoiceRequest) -> list[str]:
    cmd = [
        "python",
        str(legacy_script_path("add_elevenlabs_voice.py")),
        str(request.video),
        request.text,
        "--out",
        str(request.out),
        "--voice-id",
        request.voice_id,
        "--model-id",
        request.model_id,
        "--voice-vol",
        str(request.voice_vol),
    ]
    if not request.keep_original_audio:
        cmd.append("--drop-original-audio")
    return cmd


def build_f5_voice_command(request: F5VoiceRequest) -> list[str]:
    cmd = [
        "python",
        str(legacy_script_path("add_voice.py")),
        str(request.video),
        request.text,
        "--vol",
        str(request.voice_vol),
        "--speed",
        str(request.speed),
        "--ref-audio",
        request.ref_audio,
    ]
    if request.out:
        cmd.extend(["--out", str(request.out)])
    return cmd


def expected_elevenlabs_artifacts(request: ElevenLabsVoiceRequest) -> tuple[ExpectedArtifact, ...]:
    return (ExpectedArtifact(request.out, AssetKind.VIDEO),)


def expected_f5_artifacts(request: F5VoiceRequest) -> tuple[ExpectedArtifact, ...]:
    out = request.out or request.video.resolve().with_name(f"{request.video.resolve().stem}_voice.mp4")
    return (ExpectedArtifact(out, AssetKind.VIDEO),)


def run_elevenlabs_voice(
    request: ElevenLabsVoiceRequest,
    *,
    storage: ArtifactStorage | None = None,
    namespace: str | None = None,
) -> LegacyScriptResult:
    return run_legacy_command(
        build_elevenlabs_voice_command(request),
        expected_artifacts=expected_elevenlabs_artifacts(request),
        storage=storage,
        namespace=namespace,
    )


def run_f5_voice(
    request: F5VoiceRequest,
    *,
    storage: ArtifactStorage | None = None,
    namespace: str | None = None,
) -> LegacyScriptResult:
    require_artifact_namespace(storage=storage, namespace=namespace)
    request = _with_namespaced_f5_default_out(request, storage=storage, namespace=namespace)
    for artifact in expected_f5_artifacts(request):
        artifact.path.parent.mkdir(parents=True, exist_ok=True)
    return run_legacy_command(
        build_f5_voice_command(request),
        expected_artifacts=expected_f5_artifacts(request),
        storage=storage,
        namespace=namespace,
    )


def _with_namespaced_f5_default_out(
    request: F5VoiceRequest,
    *,
    storage: ArtifactStorage | None,
    namespace: str | None,
) -> F5VoiceRequest:
    if storage is None or request.out is not None:
        return request
    if namespace is None:
        raise ValueError("namespace is required when artifact storage is enabled.")
    video = request.video.resolve()
    return replace(request, out=video.with_name(f"{video.stem}_{namespace}_voice.mp4"))

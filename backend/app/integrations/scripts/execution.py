from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.artifacts.storage import ArtifactStorage, StoredArtifact
from app.schemas.common import AssetKind


@dataclass(frozen=True)
class ExpectedArtifact:
    path: Path
    kind: AssetKind


@dataclass(frozen=True)
class LegacyScriptResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    artifacts: tuple[StoredArtifact, ...] = ()


def require_artifact_namespace(
    *,
    storage: ArtifactStorage | None,
    namespace: str | None,
) -> None:
    if storage is not None and namespace is None:
        raise ValueError("namespace is required when artifact storage is enabled.")


def run_legacy_command(
    command: list[str],
    *,
    expected_artifacts: tuple[ExpectedArtifact, ...] = (),
    storage: ArtifactStorage | None = None,
    namespace: str | None = None,
) -> LegacyScriptResult:
    if expected_artifacts:
        require_artifact_namespace(storage=storage, namespace=namespace)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    artifacts: list[StoredArtifact] = []
    if storage is not None:
        for artifact in expected_artifacts:
            if namespace is None:
                continue
            artifacts.append(storage.register_existing(artifact.path, artifact.kind, namespace))
    return LegacyScriptResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        artifacts=tuple(artifacts),
    )

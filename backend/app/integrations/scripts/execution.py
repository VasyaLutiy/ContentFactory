from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any

from app.artifacts.storage import ArtifactStorage, StoredArtifact
from app.db.repos.asset import AssetRepository
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
    asset_ids: tuple[int, ...] = ()


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
    asset_repository: AssetRepository | None = None,
    metadata: dict[str, Any] | None = None,
    render_job_id: str | None = None,
    render_step_kind: str | None = None,
    parent_asset_ids: tuple[int, ...] = (),
) -> LegacyScriptResult:
    if expected_artifacts:
        require_artifact_namespace(storage=storage, namespace=namespace)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    artifacts: list[StoredArtifact] = []
    asset_ids: list[int] = []
    copied_artifacts: list[StoredArtifact] = []
    if storage is not None:
        try:
            for artifact in expected_artifacts:
                if namespace is None:
                    continue
                stored = storage.register_existing(artifact.path, artifact.kind, namespace)
                artifacts.append(stored)
                if stored.path.resolve() != artifact.path.resolve():
                    copied_artifacts.append(stored)
                if asset_repository is not None:
                    asset = asset_repository.record_stored_artifact(
                        stored,
                        original_path=artifact.path,
                        metadata=metadata,
                        render_job_id=render_job_id,
                        render_step_kind=render_step_kind,
                        parent_asset_ids=parent_asset_ids,
                    )
                    asset_ids.append(asset.id)
        except Exception:
            for stored in copied_artifacts:
                stored.path.unlink(missing_ok=True)
            raise
    return LegacyScriptResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        artifacts=tuple(artifacts),
        asset_ids=tuple(asset_ids),
    )

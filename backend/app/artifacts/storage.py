from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import shutil

from app.schemas.common import AssetKind


@dataclass(frozen=True)
class StoredArtifact:
    kind: AssetKind
    path: Path
    checksum_sha256: str
    size_bytes: int
    namespace: str
    relative_path: str


class ArtifactStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def register_existing(self, source: Path, kind: AssetKind, namespace: str) -> StoredArtifact:
        namespace = validate_artifact_namespace(namespace)
        if not source.exists():
            raise FileNotFoundError(source)
        target_dir = self.root / namespace / kind.value
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self._target_for(source, target_dir)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return StoredArtifact(
            kind=kind,
            path=target,
            checksum_sha256=file_sha256(target),
            size_bytes=target.stat().st_size,
            namespace=namespace,
            relative_path=str(target.relative_to(self.root)),
        )

    @staticmethod
    def _target_for(source: Path, target_dir: Path) -> Path:
        target = target_dir / source.name
        if source.resolve() == target.resolve() or not target.exists():
            return target

        index = 2
        while True:
            candidate = target_dir / f"{source.stem}__{index}{source.suffix}"
            if not candidate.exists():
                return candidate
            index += 1


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact_namespace(namespace: str) -> str:
    if not namespace or namespace in {".", ".."}:
        raise ValueError("artifact namespace must be a non-empty safe path segment.")
    if Path(namespace).name != namespace or "/" in namespace or "\\" in namespace:
        raise ValueError("artifact namespace must be a single safe path segment.")
    return namespace

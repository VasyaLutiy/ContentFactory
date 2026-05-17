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


class ArtifactStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def register_existing(self, source: Path, kind: AssetKind, namespace: str) -> StoredArtifact:
        if not source.exists():
            raise FileNotFoundError(source)
        target_dir = self.root / namespace / kind.value
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return StoredArtifact(
            kind=kind,
            path=target,
            checksum_sha256=file_sha256(target),
            size_bytes=target.stat().st_size,
        )


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

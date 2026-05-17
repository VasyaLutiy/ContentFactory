from app.artifacts.storage import ArtifactStorage, file_sha256
from app.schemas.common import AssetKind


def test_register_existing_copies_and_hashes_file(tmp_path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("artifact")
    storage = ArtifactStorage(tmp_path / "artifacts")

    stored = storage.register_existing(source, AssetKind.LOG, "job-1")

    assert stored.path.exists()
    assert stored.kind == AssetKind.LOG
    assert stored.checksum_sha256 == file_sha256(stored.path)
    assert stored.size_bytes == len("artifact")

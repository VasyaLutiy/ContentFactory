import pytest

from app.artifacts.storage import ArtifactStorage, file_sha256
from app.schemas.common import AssetKind


def test_register_existing_copies_and_hashes_file(tmp_path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("artifact")
    storage = ArtifactStorage(tmp_path / "artifacts")

    stored = storage.register_existing(source, AssetKind.LOG, "job-1")

    assert stored.path.exists()
    assert stored.path == tmp_path / "artifacts" / "job-1" / "log" / "source.txt"
    assert stored.kind == AssetKind.LOG
    assert stored.checksum_sha256 == file_sha256(stored.path)
    assert stored.size_bytes == len("artifact")


def test_register_existing_raises_for_missing_source(tmp_path) -> None:
    storage = ArtifactStorage(tmp_path / "artifacts")

    missing = tmp_path / "does-not-exist.log"
    with pytest.raises(FileNotFoundError) as exc_info:
        storage.register_existing(missing, AssetKind.LOG, "job-1")

    assert exc_info.value.args[0] == missing


def test_register_existing_keeps_path_when_source_already_in_target_dir(tmp_path) -> None:
    storage = ArtifactStorage(tmp_path / "artifacts")
    source = tmp_path / "artifacts" / "job-1" / "log" / "existing.log"
    source.parent.mkdir(parents=True)
    source.write_text("already-there")

    stored = storage.register_existing(source, AssetKind.LOG, "job-1")

    assert stored.path == source
    assert stored.size_bytes == len("already-there")


def test_register_existing_overwrites_target_when_same_filename_reimported(tmp_path) -> None:
    storage = ArtifactStorage(tmp_path / "artifacts")
    source = tmp_path / "source.log"
    source.write_text("first")
    first = storage.register_existing(source, AssetKind.LOG, "job-1")

    source.write_text("second")
    second = storage.register_existing(source, AssetKind.LOG, "job-1")

    assert first.path == second.path
    assert second.path.read_text() == "second"
    assert second.checksum_sha256 == file_sha256(second.path)

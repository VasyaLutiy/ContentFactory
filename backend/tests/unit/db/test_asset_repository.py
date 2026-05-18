from app.artifacts.storage import ArtifactStorage
from app.db.repos.asset import AssetRepository
from app.db.session import get_session_maker
from app.schemas.common import AssetKind


def test_record_stored_artifact_captures_metadata_and_lookup(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_text("video")
    stored = ArtifactStorage(tmp_path / "artifacts").register_existing(
        source,
        AssetKind.VIDEO,
        "job-1",
    )

    session_maker = get_session_maker()
    with session_maker() as db:
        repo = AssetRepository(db)
        asset = repo.record_stored_artifact(
            stored,
            original_path=source,
            metadata={"prompt": "launch"},
            render_job_id="render-1",
            render_step_kind="video",
        )

        fetched = repo.get(asset.id)
        assert fetched is not None
        assert fetched.namespace == "job-1"
        assert fetched.kind == AssetKind.VIDEO.value
        assert fetched.relative_path == "job-1/video/clip.mp4"
        assert fetched.original_path == str(source)
        assert fetched.checksum_sha256 == stored.checksum_sha256
        assert fetched.metadata_json == {"prompt": "launch"}
        assert repo.list(namespace="job-1", kind=AssetKind.VIDEO) == [fetched]
        assert repo.list(render_job_id="render-1", render_step_kind="video") == [fetched]


def test_asset_repository_tracks_parent_child_lineage(tmp_path) -> None:
    storage = ArtifactStorage(tmp_path / "artifacts")
    keyframe_source = tmp_path / "keyframe.png"
    clip_source = tmp_path / "clip.mp4"
    keyframe_source.write_text("image")
    clip_source.write_text("video")

    session_maker = get_session_maker()
    with session_maker() as db:
        repo = AssetRepository(db)
        parent = repo.record_stored_artifact(
            storage.register_existing(keyframe_source, AssetKind.IMAGE, "job-2"),
        )
        child = repo.record_stored_artifact(
            storage.register_existing(clip_source, AssetKind.VIDEO, "job-2"),
            parent_asset_ids=(parent.id,),
        )
        duplicate = repo.add_lineage(parent_asset_id=parent.id, child_asset_id=child.id)

        lineage = repo.lineage(child.id)
        assert lineage is not None
        assert [asset.id for asset in lineage.parents] == [parent.id]
        assert lineage.children == ()
        assert [edge.id for edge in lineage.edges] == [duplicate.id]

        parent_lineage = repo.lineage(parent.id)
        assert parent_lineage is not None
        assert [asset.id for asset in parent_lineage.children] == [child.id]

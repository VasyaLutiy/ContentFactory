from pathlib import Path

from app.artifacts.storage import ArtifactStorage
from app.db.repos.asset import AssetRepository
from app.db.session import get_session_maker
from app.schemas.common import AssetKind


def _create_artifact(
    tmp_path: Path,
    *,
    filename: str,
    content: str,
    kind: AssetKind,
    namespace: str,
    parent_asset_ids: tuple[int, ...] = (),
) -> int:
    source = tmp_path / filename
    source.write_text(content)
    stored = ArtifactStorage(tmp_path / "artifacts").register_existing(source, kind, namespace)

    session_maker = get_session_maker()
    with session_maker() as db:
        asset = AssetRepository(db).record_stored_artifact(
            stored,
            original_path=source,
            metadata={"source": filename},
            parent_asset_ids=parent_asset_ids,
        )
        asset_id = asset.id
        db.commit()
    return asset_id


def test_list_artifacts_supports_namespace_and_kind_filters(client, tmp_path) -> None:
    video_id = _create_artifact(
        tmp_path,
        filename="clip.mp4",
        content="video",
        kind=AssetKind.VIDEO,
        namespace="job-1",
    )
    _create_artifact(
        tmp_path,
        filename="keyframe.png",
        content="image",
        kind=AssetKind.IMAGE,
        namespace="job-1",
    )
    _create_artifact(
        tmp_path,
        filename="other.mp4",
        content="other",
        kind=AssetKind.VIDEO,
        namespace="job-2",
    )

    response = client.get("/api/v1/artifacts", params={"namespace": "job-1", "kind": "video"})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [video_id]
    assert body[0]["namespace"] == "job-1"
    assert body[0]["kind"] == "video"
    assert body[0]["relative_path"] == "job-1/video/clip.mp4"
    assert body[0]["metadata"] == {"source": "clip.mp4"}
    assert "path" not in body[0]
    assert "original_path" not in body[0]


def test_get_artifact_returns_registered_asset(client, tmp_path) -> None:
    artifact_id = _create_artifact(
        tmp_path,
        filename="render.log",
        content="log",
        kind=AssetKind.LOG,
        namespace="job-logs",
    )

    response = client.get(f"/api/v1/artifacts/{artifact_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == artifact_id
    assert body["namespace"] == "job-logs"
    assert body["kind"] == "log"
    assert body["size_bytes"] == len("log")
    assert body["checksum_sha256"]


def test_get_artifact_lineage_returns_parents_children_and_edges(client, tmp_path) -> None:
    parent_id = _create_artifact(
        tmp_path,
        filename="prompt.txt",
        content="prompt",
        kind=AssetKind.PROMPT,
        namespace="job-lineage",
    )
    child_id = _create_artifact(
        tmp_path,
        filename="workflow.json",
        content="{}",
        kind=AssetKind.JSON,
        namespace="job-lineage",
        parent_asset_ids=(parent_id,),
    )

    response = client.get(f"/api/v1/artifacts/{child_id}/lineage")

    assert response.status_code == 200
    body = response.json()
    assert body["asset"]["id"] == child_id
    assert [item["id"] for item in body["parents"]] == [parent_id]
    assert body["children"] == []
    assert [
        (edge["parent_asset_id"], edge["child_asset_id"], edge["relationship_type"])
        for edge in body["edges"]
    ] == [(parent_id, child_id, "derived_from")]


def test_get_artifact_returns_not_found_for_missing_asset(client) -> None:
    response = client.get("/api/v1/artifacts/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found"


def test_get_artifact_lineage_returns_not_found_for_missing_asset(client) -> None:
    response = client.get("/api/v1/artifacts/999999/lineage")

    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found"

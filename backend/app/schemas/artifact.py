from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.db.models.asset import AssetModel
from app.db.models.asset_lineage import AssetLineageModel
from app.db.repos.asset import AssetLineage
from app.schemas.common import AssetKind


class ArtifactRead(BaseModel):
    id: int
    namespace: str
    kind: AssetKind
    relative_path: str
    checksum_sha256: str
    size_bytes: int
    metadata: dict[str, Any]
    render_job_id: str | None = None
    render_step_kind: str | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, asset: AssetModel) -> "ArtifactRead":
        return cls(
            id=asset.id,
            namespace=asset.namespace,
            kind=AssetKind(asset.kind),
            relative_path=asset.relative_path,
            checksum_sha256=asset.checksum_sha256,
            size_bytes=asset.size_bytes,
            metadata=asset.metadata_json,
            render_job_id=asset.render_job_id,
            render_step_kind=asset.render_step_kind,
            created_at=asset.created_at,
        )


class ArtifactLineageEdgeRead(BaseModel):
    id: int
    parent_asset_id: int
    child_asset_id: int
    relationship_type: str
    created_at: datetime

    @classmethod
    def from_model(cls, edge: AssetLineageModel) -> "ArtifactLineageEdgeRead":
        return cls(
            id=edge.id,
            parent_asset_id=edge.parent_asset_id,
            child_asset_id=edge.child_asset_id,
            relationship_type=edge.relationship_type,
            created_at=edge.created_at,
        )


class ArtifactLineageRead(BaseModel):
    asset: ArtifactRead
    parents: list[ArtifactRead]
    children: list[ArtifactRead]
    edges: list[ArtifactLineageEdgeRead]

    @classmethod
    def from_lineage(cls, lineage: AssetLineage) -> "ArtifactLineageRead":
        return cls(
            asset=ArtifactRead.from_model(lineage.asset),
            parents=[ArtifactRead.from_model(asset) for asset in lineage.parents],
            children=[ArtifactRead.from_model(asset) for asset in lineage.children],
            edges=[ArtifactLineageEdgeRead.from_model(edge) for edge in lineage.edges],
        )

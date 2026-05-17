from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts.storage import StoredArtifact
from app.db.models.asset import AssetModel
from app.db.models.asset_lineage import AssetLineageModel
from app.schemas.common import AssetKind


@dataclass(frozen=True)
class AssetLineage:
    asset: AssetModel
    parents: tuple[AssetModel, ...]
    children: tuple[AssetModel, ...]
    edges: tuple[AssetLineageModel, ...]


class AssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        *,
        namespace: str | None = None,
        kind: AssetKind | str | None = None,
        render_job_id: str | None = None,
        render_step_kind: str | None = None,
    ) -> list[AssetModel]:
        query = select(AssetModel)
        if namespace is not None:
            query = query.where(AssetModel.namespace == namespace)
        if kind is not None:
            query = query.where(AssetModel.kind == self._kind_value(kind))
        if render_job_id is not None:
            query = query.where(AssetModel.render_job_id == render_job_id)
        if render_step_kind is not None:
            query = query.where(AssetModel.render_step_kind == render_step_kind)
        query = query.order_by(AssetModel.id.asc())
        return list(self.session.scalars(query).all())

    def get(self, asset_id: int) -> AssetModel | None:
        return self.session.get(AssetModel, asset_id)

    def record_stored_artifact(
        self,
        stored: StoredArtifact,
        *,
        original_path: Path | str | None = None,
        metadata: dict[str, Any] | None = None,
        render_job_id: str | None = None,
        render_step_kind: str | None = None,
        parent_asset_ids: tuple[int, ...] = (),
        relationship_type: str = "derived_from",
    ) -> AssetModel:
        asset = AssetModel(
            namespace=stored.namespace,
            kind=stored.kind.value,
            relative_path=stored.relative_path,
            path=str(stored.path),
            original_path=str(original_path) if original_path is not None else None,
            checksum_sha256=stored.checksum_sha256,
            size_bytes=stored.size_bytes,
            metadata_json=metadata or {},
            render_job_id=render_job_id,
            render_step_kind=render_step_kind,
        )
        self.session.add(asset)
        self.session.flush()
        for parent_asset_id in parent_asset_ids:
            self.add_lineage(
                parent_asset_id=parent_asset_id,
                child_asset_id=asset.id,
                relationship_type=relationship_type,
            )
        return asset

    def add_lineage(
        self,
        *,
        parent_asset_id: int,
        child_asset_id: int,
        relationship_type: str = "derived_from",
    ) -> AssetLineageModel:
        existing = self.session.scalar(
            select(AssetLineageModel).where(
                AssetLineageModel.parent_asset_id == parent_asset_id,
                AssetLineageModel.child_asset_id == child_asset_id,
                AssetLineageModel.relationship_type == relationship_type,
            )
        )
        if existing is not None:
            return existing

        edge = AssetLineageModel(
            parent_asset_id=parent_asset_id,
            child_asset_id=child_asset_id,
            relationship_type=relationship_type,
        )
        self.session.add(edge)
        self.session.flush()
        return edge

    def lineage(self, asset_id: int) -> AssetLineage | None:
        asset = self.get(asset_id)
        if asset is None:
            return None

        parent_edges = list(
            self.session.scalars(
                select(AssetLineageModel)
                .where(AssetLineageModel.child_asset_id == asset_id)
                .order_by(AssetLineageModel.id.asc())
            ).all()
        )
        child_edges = list(
            self.session.scalars(
                select(AssetLineageModel)
                .where(AssetLineageModel.parent_asset_id == asset_id)
                .order_by(AssetLineageModel.id.asc())
            ).all()
        )
        parent_ids = [edge.parent_asset_id for edge in parent_edges]
        child_ids = [edge.child_asset_id for edge in child_edges]
        parents = self._assets_by_ids(parent_ids)
        children = self._assets_by_ids(child_ids)
        return AssetLineage(
            asset=asset,
            parents=tuple(parents),
            children=tuple(children),
            edges=tuple(parent_edges + child_edges),
        )

    def _assets_by_ids(self, asset_ids: list[int]) -> list[AssetModel]:
        if not asset_ids:
            return []
        assets = {
            asset.id: asset
            for asset in self.session.scalars(select(AssetModel).where(AssetModel.id.in_(asset_ids)))
        }
        return [assets[asset_id] for asset_id in asset_ids if asset_id in assets]

    @staticmethod
    def _kind_value(kind: AssetKind | str) -> str:
        return kind.value if isinstance(kind, AssetKind) else kind

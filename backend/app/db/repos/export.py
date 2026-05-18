from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.export import ExportModel


class ExportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        campaign_id: int,
        episode_id: int | None = None,
        asset_id: int | None = None,
        render_job_id: str | None = None,
        platform: str = "tiktok",
        tiktok_video_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExportModel:
        export = ExportModel(
            campaign_id=campaign_id,
            episode_id=episode_id,
            asset_id=asset_id,
            render_job_id=render_job_id,
            platform=platform,
            tiktok_video_id=tiktok_video_id,
            metadata_json=metadata or {},
        )
        self.session.add(export)
        self.session.flush()
        return export

    def list(
        self,
        *,
        campaign_id: int | None = None,
        episode_id: int | None = None,
        platform: str | None = None,
        render_job_id: str | None = None,
    ) -> list[ExportModel]:
        query = select(ExportModel)
        if campaign_id is not None:
            query = query.where(ExportModel.campaign_id == campaign_id)
        if episode_id is not None:
            query = query.where(ExportModel.episode_id == episode_id)
        if platform is not None:
            query = query.where(ExportModel.platform == platform)
        if render_job_id is not None:
            query = query.where(ExportModel.render_job_id == render_job_id)
        query = query.order_by(ExportModel.id.asc())
        return list(self.session.scalars(query).all())

    def get(self, export_id: int) -> ExportModel | None:
        return self.session.get(ExportModel, export_id)

    def get_by_tiktok_video_id(self, tiktok_video_id: str) -> ExportModel | None:
        return self.session.scalar(
            select(ExportModel).where(ExportModel.tiktok_video_id == tiktok_video_id)
        )

    def update_tiktok_video_id(
        self,
        export: ExportModel,
        tiktok_video_id: str | None,
    ) -> ExportModel:
        export.tiktok_video_id = tiktok_video_id
        self.session.add(export)
        self.session.flush()
        return export

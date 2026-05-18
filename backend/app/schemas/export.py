from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.export import ExportModel


class ExportCreate(BaseModel):
    campaign_id: int
    episode_id: int | None = None
    asset_id: int | None = None
    render_job_id: str | None = None
    platform: str = "tiktok"
    tiktok_video_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportTikTokVideoIdUpdate(BaseModel):
    tiktok_video_id: str | None = None


class ExportRead(BaseModel):
    id: int
    campaign_id: int
    episode_id: int | None = None
    asset_id: int | None = None
    render_job_id: str | None = None
    platform: str
    tiktok_video_id: str | None = None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, export: ExportModel) -> "ExportRead":
        return cls(
            id=export.id,
            campaign_id=export.campaign_id,
            episode_id=export.episode_id,
            asset_id=export.asset_id,
            render_job_id=export.render_job_id,
            platform=export.platform,
            tiktok_video_id=export.tiktok_video_id,
            metadata=export.metadata_json,
            created_at=export.created_at,
            updated_at=export.updated_at,
        )

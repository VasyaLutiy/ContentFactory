from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.db.models.analytics_snapshot import AnalyticsSnapshotModel


class AnalyticsSnapshotCreate(BaseModel):
    export_id: int
    campaign_id: int
    video_id: str
    snapshot_at: datetime
    views: int | None = None
    views_est: int | None = None
    total_play_seconds: int | None = None
    avg_watch_seconds: float | None = None
    full_watch_percent: float | None = None
    retention_note: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    screenshot_asset_id: int | None = None
    source_json_asset_id: int | None = None


class AnalyticsSnapshotRead(BaseModel):
    id: int
    export_id: int
    campaign_id: int
    video_id: str
    snapshot_at: datetime
    views: int | None = None
    views_est: int | None = None
    total_play_seconds: int | None = None
    avg_watch_seconds: float | None = None
    full_watch_percent: float | None = None
    retention_note: str | None = None
    raw_payload: dict[str, Any]
    screenshot_asset_id: int | None = None
    source_json_asset_id: int | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, snapshot: AnalyticsSnapshotModel) -> "AnalyticsSnapshotRead":
        return cls(
            id=snapshot.id,
            export_id=snapshot.export_id,
            campaign_id=snapshot.campaign_id,
            video_id=snapshot.video_id,
            snapshot_at=snapshot.snapshot_at,
            views=snapshot.views,
            views_est=snapshot.views_est,
            total_play_seconds=snapshot.total_play_seconds,
            avg_watch_seconds=snapshot.avg_watch_seconds,
            full_watch_percent=snapshot.full_watch_percent,
            retention_note=snapshot.retention_note,
            raw_payload=snapshot.raw_payload_json,
            screenshot_asset_id=snapshot.screenshot_asset_id,
            source_json_asset_id=snapshot.source_json_asset_id,
            created_at=snapshot.created_at,
        )


class TikTokAnalyticsIngestPayload(BaseModel):
    export_id: int
    legacy_json: dict[str, Any] | None = None
    summary_row: dict[str, Any] | None = None
    screenshot_asset_id: int | None = None
    source_json_asset_id: int | None = None

    @model_validator(mode="after")
    def validate_single_source(self) -> "TikTokAnalyticsIngestPayload":
        source_count = sum(
            source is not None for source in (self.legacy_json, self.summary_row)
        )
        if source_count != 1:
            raise ValueError("Provide exactly one of legacy_json or summary_row.")
        return self

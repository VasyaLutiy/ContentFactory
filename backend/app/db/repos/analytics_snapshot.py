from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.analytics_snapshot import AnalyticsSnapshotModel


class AnalyticsSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        export_id: int,
        campaign_id: int,
        video_id: str,
        snapshot_at: datetime,
        views: int | None = None,
        views_est: int | None = None,
        total_play_seconds: int | None = None,
        avg_watch_seconds: float | None = None,
        full_watch_percent: float | None = None,
        retention_note: str | None = None,
        raw_payload: dict[str, Any] | None = None,
        screenshot_asset_id: int | None = None,
        source_json_asset_id: int | None = None,
    ) -> AnalyticsSnapshotModel:
        snapshot = AnalyticsSnapshotModel(
            export_id=export_id,
            campaign_id=campaign_id,
            video_id=video_id,
            snapshot_at=snapshot_at,
            views=views,
            views_est=views_est,
            total_play_seconds=total_play_seconds,
            avg_watch_seconds=avg_watch_seconds,
            full_watch_percent=full_watch_percent,
            retention_note=retention_note,
            raw_payload_json=raw_payload or {},
            screenshot_asset_id=screenshot_asset_id,
            source_json_asset_id=source_json_asset_id,
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def list(
        self,
        *,
        campaign_id: int | None = None,
        export_id: int | None = None,
    ) -> list[AnalyticsSnapshotModel]:
        query = select(AnalyticsSnapshotModel)
        if campaign_id is not None:
            query = query.where(AnalyticsSnapshotModel.campaign_id == campaign_id)
        if export_id is not None:
            query = query.where(AnalyticsSnapshotModel.export_id == export_id)
        query = query.order_by(
            AnalyticsSnapshotModel.snapshot_at.asc(),
            AnalyticsSnapshotModel.id.asc(),
        )
        return list(self.session.scalars(query).all())

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.analytics_snapshot import AnalyticsSnapshotModel
from app.db.models.export import ExportModel
from app.db.repos.analytics_snapshot import AnalyticsSnapshotRepository
from app.db.repos.export import ExportRepository
from app.providers.tiktok.analytics import TikTokAnalyticsSnapshot


@dataclass(frozen=True)
class TikTokSnapshotArtifactLinks:
    screenshot_asset_id: int | None = None
    source_json_asset_id: int | None = None


class TikTokAnalyticsIngestionError(ValueError):
    pass


def write_tiktok_analytics_snapshot(
    db: Session,
    *,
    export: ExportModel,
    snapshot: TikTokAnalyticsSnapshot,
    artifacts: TikTokSnapshotArtifactLinks | None = None,
) -> AnalyticsSnapshotModel:
    video_id = snapshot.video_id or export.tiktok_video_id
    if not video_id:
        raise TikTokAnalyticsIngestionError("TikTok analytics snapshot requires a video ID.")
    if export.tiktok_video_id is not None and snapshot.video_id:
        if export.tiktok_video_id != snapshot.video_id:
            raise TikTokAnalyticsIngestionError(
                "TikTok analytics snapshot video ID does not match export."
            )
    if snapshot.snapshot_at is None:
        raise TikTokAnalyticsIngestionError("TikTok analytics snapshot requires snapshot_at.")

    if export.tiktok_video_id is None:
        ExportRepository(db).update_tiktok_video_id(export, video_id)

    links = artifacts or TikTokSnapshotArtifactLinks()
    return AnalyticsSnapshotRepository(db).create(
        export_id=export.id,
        campaign_id=export.campaign_id,
        video_id=video_id,
        snapshot_at=snapshot.snapshot_at,
        views=snapshot.views,
        views_est=snapshot.views_est,
        total_play_seconds=_to_int(snapshot.total_play_seconds),
        avg_watch_seconds=snapshot.avg_watch_seconds,
        full_watch_percent=snapshot.full_watch_percent,
        retention_note=snapshot.retention_note,
        raw_payload=snapshot.raw_payload,
        screenshot_asset_id=links.screenshot_asset_id,
        source_json_asset_id=links.source_json_asset_id,
    )


def _to_int(value: float | None) -> int | None:
    if value is None:
        return None
    return int(value)

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.repos.analytics_snapshot import AnalyticsSnapshotRepository
from app.db.repos.campaign import CampaignRepository
from app.db.repos.export import ExportRepository
from app.db.session import get_session_maker
from app.schemas.analytics import AnalyticsSnapshotRead


def test_analytics_snapshot_repository_creates_and_filters_snapshots() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign_a = CampaignRepository(db).create({"name": "Launch A", "description": None})
        campaign_b = CampaignRepository(db).create({"name": "Launch B", "description": None})
        export_a = ExportRepository(db).create(
            campaign_id=campaign_a.id,
            tiktok_video_id="7639445229749259540",
        )
        export_b = ExportRepository(db).create(
            campaign_id=campaign_b.id,
            tiktok_video_id="7639445229749259541",
        )
        repo = AnalyticsSnapshotRepository(db)
        snapshot_at = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)

        snapshot_a = repo.create(
            export_id=export_a.id,
            campaign_id=campaign_a.id,
            video_id="7639445229749259540",
            snapshot_at=snapshot_at,
            views=1200,
            views_est=None,
            total_play_seconds=278,
            avg_watch_seconds=3.4,
            full_watch_percent=42.5,
            retention_note="Most viewers stopped watching at 0:01",
            raw_payload={"kpis": {"Video views": "1200"}},
        )
        snapshot_b = repo.create(
            export_id=export_b.id,
            campaign_id=campaign_b.id,
            video_id="7639445229749259541",
            snapshot_at=snapshot_at,
            views_est=900,
        )

        assert repo.list(campaign_id=campaign_a.id) == [snapshot_a]
        assert repo.list(export_id=export_a.id) == [snapshot_a]
        assert repo.list() == [snapshot_a, snapshot_b]

        read = AnalyticsSnapshotRead.from_model(snapshot_a)
        assert read.raw_payload == {"kpis": {"Video views": "1200"}}
        assert read.avg_watch_seconds == 3.4
        assert read.full_watch_percent == 42.5


def test_analytics_snapshot_unique_per_export_and_snapshot_at() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        export = ExportRepository(db).create(campaign_id=campaign.id, tiktok_video_id="video-1")
        repo = AnalyticsSnapshotRepository(db)
        snapshot_at = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
        repo.create(
            export_id=export.id,
            campaign_id=campaign.id,
            video_id="video-1",
            snapshot_at=snapshot_at,
        )

        with pytest.raises(IntegrityError):
            repo.create(
                export_id=export.id,
                campaign_id=campaign.id,
                video_id="video-1",
                snapshot_at=snapshot_at,
            )

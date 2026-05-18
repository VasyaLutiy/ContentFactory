import pytest
from sqlalchemy.exc import IntegrityError

from app.db.repos.campaign import CampaignRepository
from app.db.repos.export import ExportRepository
from app.db.session import get_session_maker
from app.schemas.export import ExportRead


def test_export_repository_creates_lists_and_updates_tiktok_video_id() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        repo = ExportRepository(db)

        export = repo.create(
            campaign_id=campaign.id,
            render_job_id="render-1",
            metadata={"variant": "hook-a"},
        )
        updated = repo.update_tiktok_video_id(export, "7639445229749259540")

        assert updated.platform == "tiktok"
        assert updated.tiktok_video_id == "7639445229749259540"
        assert updated.metadata_json == {"variant": "hook-a"}
        assert repo.get(export.id) == updated
        assert repo.get_by_tiktok_video_id("7639445229749259540") == updated
        assert repo.list(campaign_id=campaign.id) == [updated]
        assert repo.list(render_job_id="render-1") == [updated]

        read = ExportRead.from_model(updated)
        assert read.metadata == {"variant": "hook-a"}
        assert read.tiktok_video_id == "7639445229749259540"


def test_export_tiktok_video_id_is_unique_when_present() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        repo = ExportRepository(db)
        repo.create(campaign_id=campaign.id, tiktok_video_id="video-1")

        with pytest.raises(IntegrityError):
            repo.create(campaign_id=campaign.id, tiktok_video_id="video-1")

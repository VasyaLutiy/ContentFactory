from datetime import datetime, timezone

from app.db.repos.analytics_snapshot import AnalyticsSnapshotRepository
from app.db.repos.campaign import CampaignRepository
from app.db.repos.episode import EpisodeRepository
from app.db.repos.export import ExportRepository
from app.db.repos.scene import SceneRepository
from app.db.repos.text_beat import TextBeatRepository
from app.db.session import get_session_maker
from app.domain.services.recommendation_cards import build_recommendation_cards


def test_build_recommendation_cards_compares_variants_and_uses_latest_snapshot() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        export_a = ExportRepository(db).create(
            campaign_id=campaign.id,
            metadata={
                "variant_label": "Hook-A",
                "text_beats": [
                    {"start": 0.1, "end": 0.7, "text": "Mystery unlocked", "style_preset": "hook_default"}
                ]
            },
        )
        export_b = ExportRepository(db).create(
            campaign_id=campaign.id,
            metadata={"on_screen_text_beats": [{"start": 0.2, "end": 0.8, "text": "Wait for it"}]},
        )
        snapshots = AnalyticsSnapshotRepository(db)
        snapshots.create(
            export_id=export_a.id,
            campaign_id=campaign.id,
            video_id="a-vid",
            snapshot_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
            avg_watch_seconds=2.0,
            full_watch_percent=20.0,
            retention_note="older snapshot",
        )
        snapshots.create(
            export_id=export_a.id,
            campaign_id=campaign.id,
            video_id="a-vid",
            snapshot_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
            avg_watch_seconds=6.5,
            full_watch_percent=49.0,
            retention_note="latest snapshot",
        )
        snapshots.create(
            export_id=export_b.id,
            campaign_id=campaign.id,
            video_id="b-vid",
            snapshot_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
            avg_watch_seconds=4.0,
            full_watch_percent=35.0,
            retention_note="slower opener",
        )
        db.commit()

        cards = build_recommendation_cards(
            db,
            campaign_id=campaign.id,
            export_ids=[export_a.id, export_b.id],
        )

        assert [card.export_id for card in cards] == [export_a.id, export_b.id]
        assert cards[0].avg_watch_seconds == 6.5
        assert cards[0].export_ids == [export_a.id]
        assert cards[0].variant_label == "Hook-A"
        assert cards[0].full_watch_percent == 49.0
        assert cards[0].retention_note == "latest snapshot"
        assert cards[0].confidence == "high"
        assert cards[0].reason == "Top-performing variant by latest watch-time and completion metrics."
        assert cards[1].reason == "Underperforming variant by latest watch-time and completion metrics."
        assert cards[0].on_screen_text_beats[0].text == "Mystery unlocked"
        assert cards[1].on_screen_text_beats[0].text == "Wait for it"


def test_build_recommendation_cards_falls_back_to_episode_beats_and_warns_when_missing() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        episode = EpisodeRepository(db).create(
            {"campaign_id": campaign.id, "title": "Episode 1", "synopsis": None, "order_index": 0}
        )
        scene = SceneRepository(db).create(
            {"episode_id": episode.id, "title": "Scene 1", "summary": None, "order_index": 0}
        )
        TextBeatRepository(db).create(
            {
                "scene_id": scene.id,
                "start": 0.0,
                "end": 0.4,
                "text": "Fallback beat",
                "style_preset": "hook_default",
                "priority": 0,
            }
        )

        export_with_fallback = ExportRepository(db).create(campaign_id=campaign.id, episode_id=episode.id)
        export_no_text = ExportRepository(db).create(
            campaign_id=campaign.id,
            episode_id=episode.id,
            metadata={"no_text_experiment": True},
        )
        export_missing = ExportRepository(db).create(campaign_id=campaign.id)
        db.commit()

        cards = build_recommendation_cards(
            db,
            campaign_id=campaign.id,
            export_ids=[export_with_fallback.id, export_no_text.id, export_missing.id],
        )

        assert cards[0].text_metadata_source == "episode.scenes.text_beats"
        assert cards[0].on_screen_text_beats[0].text == "Fallback beat"
        assert cards[0].warnings == []
        assert cards[1].no_text_experiment is True
        assert cards[1].text_metadata_source == "export.metadata_json"
        assert cards[1].on_screen_text_beats == []
        assert cards[1].warnings == []
        assert cards[2].text_metadata_source is None
        assert cards[2].on_screen_text_beats == []
        assert cards[2].warnings == ["Missing on-screen text beats in export metadata and episode scenes."]


def test_build_recommendation_cards_can_compare_all_campaign_exports_and_rejects_unknown_ids() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        other_campaign = CampaignRepository(db).create({"name": "Other", "description": None})
        export_a = ExportRepository(db).create(campaign_id=campaign.id)
        export_b = ExportRepository(db).create(campaign_id=campaign.id)
        other_export = ExportRepository(db).create(campaign_id=other_campaign.id)
        db.commit()

        cards = build_recommendation_cards(db, campaign_id=campaign.id)

        assert [card.export_id for card in cards] == [export_a.id, export_b.id]

        try:
            build_recommendation_cards(
                db,
                campaign_id=campaign.id,
                export_ids=[export_a.id, other_export.id],
            )
        except ValueError as exc:
            assert str(exc) == f"Exports not found in campaign: {other_export.id}"
        else:
            raise AssertionError("Expected unknown campaign export to be rejected.")


def test_build_recommendation_cards_uses_neutral_reason_for_equal_scores() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        export_a = ExportRepository(db).create(campaign_id=campaign.id)
        export_b = ExportRepository(db).create(campaign_id=campaign.id)
        snapshots = AnalyticsSnapshotRepository(db)
        for export in (export_a, export_b):
            snapshots.create(
                export_id=export.id,
                campaign_id=campaign.id,
                video_id=f"v-{export.id}",
                snapshot_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
                avg_watch_seconds=5.0,
                full_watch_percent=42.0,
                retention_note="same score",
            )
        db.commit()

        cards = build_recommendation_cards(
            db,
            campaign_id=campaign.id,
            export_ids=[export_a.id, export_b.id],
        )

        assert [card.reason for card in cards] == [
            "Variant is tied on latest watch-time and completion metrics.",
            "Variant is tied on latest watch-time and completion metrics.",
        ]
        assert all("Top-performing" not in card.reason for card in cards)
        assert all("Underperforming" not in card.reason for card in cards)


def test_build_recommendation_cards_uses_neutral_reason_for_partial_ties() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        campaign = CampaignRepository(db).create({"name": "Launch", "description": None})
        exports = [ExportRepository(db).create(campaign_id=campaign.id) for _ in range(4)]
        snapshots = AnalyticsSnapshotRepository(db)
        scores = [(5.0, 50.0), (5.0, 50.0), (3.0, 20.0), (3.0, 20.0)]
        for export, (avg_watch_seconds, full_watch_percent) in zip(exports, scores, strict=True):
            snapshots.create(
                export_id=export.id,
                campaign_id=campaign.id,
                video_id=f"v-{export.id}",
                snapshot_at=datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
                avg_watch_seconds=avg_watch_seconds,
                full_watch_percent=full_watch_percent,
                retention_note="partial tie",
            )
        db.commit()

        cards = build_recommendation_cards(
            db,
            campaign_id=campaign.id,
            export_ids=[export.id for export in exports],
        )

        assert [card.reason for card in cards] == [
            "Variant is tied on latest watch-time and completion metrics.",
            "Variant is tied on latest watch-time and completion metrics.",
            "Variant is tied on latest watch-time and completion metrics.",
            "Variant is tied on latest watch-time and completion metrics.",
        ]
        assert all("Top-performing" not in card.reason for card in cards)
        assert all("Underperforming" not in card.reason for card in cards)

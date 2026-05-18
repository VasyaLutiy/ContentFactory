from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.integrations.scripts.execution import ExpectedArtifact
from app.integrations.scripts.tiktok_analytics_adapter import (
    TikTokAnalyticsRequest,
    build_tiktok_analytics_command,
    expected_tiktok_analytics_artifacts,
    extract_tiktok_video_id,
)
from app.providers.tiktok.analytics import (
    parse_legacy_summary_csv,
    parse_legacy_summary_row,
    parse_legacy_video_json,
    parse_legacy_video_json_file,
)
from app.schemas.common import AssetKind


def test_parse_legacy_video_json_normalizes_kpis() -> None:
    payload = {
        "video_id": "7639445229749259540",
        "scraped_at": "2026-05-18T12:34:56Z",
        "kpis": {
            "Video views": "1,234",
            "Total play time": "0h:04m:38s",
            "Average watch time": "3.4s",
            "Watched full video": "42%",
        },
        "engagement": {"views_top": "999"},
        "retention_note": "Most viewers stopped watching at 0:01",
        "xhr_payloads_count": 0,
    }

    snapshot = parse_legacy_video_json(json.dumps(payload))

    assert snapshot.video_id == "7639445229749259540"
    assert snapshot.snapshot_at == datetime(2026, 5, 18, 12, 34, 56, tzinfo=UTC)
    assert snapshot.views == 1234
    assert snapshot.views_est == 1234
    assert snapshot.total_play_seconds == 278
    assert snapshot.avg_watch_seconds == 3.4
    assert snapshot.full_watch_percent == 42.0
    assert snapshot.retention_note == "Most viewers stopped watching at 0:01"
    assert snapshot.raw_payload == payload


def test_parse_legacy_video_json_file_and_suffix_views(tmp_path) -> None:
    path = tmp_path / "7639445229749259541.json"
    path.write_text(
        json.dumps(
            {
                "video_id": "7639445229749259541",
                "snapshot_at": "2026-05-18T12:34:56+00:00",
                "kpis": {
                    "Video views": "2.5K",
                    "Total play time": "04m:38s",
                    "Average watch time": "12s",
                    "Watched full video": "12.5%",
                },
            }
        )
    )

    snapshot = parse_legacy_video_json_file(path)

    assert snapshot.views is None
    assert snapshot.views_est == 2500
    assert snapshot.total_play_seconds == 278
    assert snapshot.avg_watch_seconds == 12
    assert snapshot.full_watch_percent == 12.5


def test_parse_legacy_summary_csv_rows_with_commas_and_m_suffix() -> None:
    csv_text = "\n".join(
        [
            "video_id,scraped_at,Video views,Total play time,Average watch time,"
            "Watched full video,New followers,likes_top,comments_top,shares_top,"
            "saves_top,retention_note",
            '7639445229749259540,2026-05-18T12:34:56Z,"1,234",0h:04m:38s,'
            "3.4s,42%,1,9,8,7,6,Most viewers stopped watching at 0:01",
            "7639445229749259541,2026-05-18T12:35:56Z,1.2M,1h:02m:03s,"
            "0:07,51.5%,2,9,8,7,6,",
        ]
    )

    first, second = parse_legacy_summary_csv(csv_text)

    assert first.views == 1234
    assert first.views_est == 1234
    assert first.total_play_seconds == 278
    assert first.avg_watch_seconds == 3.4
    assert first.full_watch_percent == 42.0
    assert first.raw_payload["likes_top"] == "9"
    assert second.views is None
    assert second.views_est == 1_200_000
    assert second.total_play_seconds == 3723
    assert second.avg_watch_seconds == 7
    assert second.retention_note is None


def test_parse_legacy_summary_row_keeps_unavailable_values_as_none() -> None:
    snapshot = parse_legacy_summary_row(
        {
            "video_id": "7639445229749259542",
            "scraped_at": "",
            "Video views": "ERROR",
            "Total play time": "<unavailable>",
            "Average watch time": "N/A",
            "Watched full video": "",
            "retention_note": "blocked",
        }
    )

    assert snapshot.snapshot_at is None
    assert snapshot.views is None
    assert snapshot.views_est is None
    assert snapshot.total_play_seconds is None
    assert snapshot.avg_watch_seconds is None
    assert snapshot.full_watch_percent is None
    assert snapshot.retention_note == "blocked"


def test_build_tiktok_analytics_command_preserves_legacy_flags(tmp_path, monkeypatch) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    request = TikTokAnalyticsRequest(
        video_ids=(
            "7639445229749259540",
            "https://www.tiktok.com/tiktokstudio/analytics/7639445229749259541",
        ),
        cdp_endpoint="http://localhost:9222",
        cookies_path=tmp_path / "cookies.json",
        show=True,
    )

    command = build_tiktok_analytics_command(request)

    assert command == [
        "python",
        str(legacy_root / "tt_analytics.py"),
        "--cdp",
        "http://localhost:9222",
        "--cookies",
        str(tmp_path / "cookies.json"),
        "--show",
        "7639445229749259540",
        "https://www.tiktok.com/tiktokstudio/analytics/7639445229749259541",
    ]


def test_tiktok_analytics_expected_artifacts_include_json_and_screenshot(
    tmp_path, monkeypatch
) -> None:
    legacy_root = _legacy_root(tmp_path, monkeypatch)
    request = TikTokAnalyticsRequest(
        video_ids=(
            "7639445229749259540",
            "https://www.tiktok.com/@user/video/7639445229749259541",
        ),
    )

    assert expected_tiktok_analytics_artifacts(request) == (
        ExpectedArtifact(legacy_root / "tt_data" / "7639445229749259540.json", AssetKind.JSON),
        ExpectedArtifact(legacy_root / "tt_data" / "7639445229749259540.png", AssetKind.SCREENSHOT),
        ExpectedArtifact(legacy_root / "tt_data" / "7639445229749259541.json", AssetKind.JSON),
        ExpectedArtifact(legacy_root / "tt_data" / "7639445229749259541.png", AssetKind.SCREENSHOT),
    )


def test_extract_tiktok_video_id_rejects_unknown_shape() -> None:
    with pytest.raises(ValueError, match="Can't extract TikTok video ID"):
        extract_tiktok_video_id("https://www.tiktok.com/@user")


def _legacy_root(tmp_path: Path, monkeypatch) -> Path:
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    (legacy_root / "tt_analytics.py").write_text("#!/usr/bin/env python3\n")
    monkeypatch.setenv("CONTENT_FACTORY_LEGACY_ROOT", str(legacy_root))
    get_settings.cache_clear()
    return legacy_root

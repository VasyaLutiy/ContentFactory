from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


VIDEO_VIEWS_LABEL = "Video views"
TOTAL_PLAY_TIME_LABEL = "Total play time"
AVERAGE_WATCH_TIME_LABEL = "Average watch time"
FULL_WATCH_LABEL = "Watched full video"


@dataclass(frozen=True)
class TikTokAnalyticsSnapshot:
    video_id: str
    snapshot_at: datetime | None
    views: int | None
    views_est: int | None
    total_play_seconds: float | None
    avg_watch_seconds: float | None
    full_watch_percent: float | None
    retention_note: str | None
    raw_payload: dict[str, Any]


def parse_legacy_video_json_file(path: Path) -> TikTokAnalyticsSnapshot:
    return parse_legacy_video_json(json.loads(path.read_text()))


def parse_legacy_video_json(payload: str | Mapping[str, Any]) -> TikTokAnalyticsSnapshot:
    data = _json_payload(payload)
    kpis = _mapping(data.get("kpis"))
    engagement = _mapping(data.get("engagement"))
    raw_views = _first_present(
        kpis.get(VIDEO_VIEWS_LABEL),
        data.get("views"),
        engagement.get("views_top"),
    )
    views, views_est = _parse_count(raw_views)
    return TikTokAnalyticsSnapshot(
        video_id=str(data.get("video_id") or ""),
        snapshot_at=_parse_snapshot_at(
            _first_present(data.get("scraped_at"), data.get("snapshot_at"))
        ),
        views=views,
        views_est=views_est,
        total_play_seconds=_parse_duration_seconds(kpis.get(TOTAL_PLAY_TIME_LABEL)),
        avg_watch_seconds=_parse_duration_seconds(kpis.get(AVERAGE_WATCH_TIME_LABEL)),
        full_watch_percent=_parse_percent(kpis.get(FULL_WATCH_LABEL)),
        retention_note=_clean_text(data.get("retention_note")),
        raw_payload=dict(data),
    )


def parse_legacy_summary_csv_file(path: Path) -> tuple[TikTokAnalyticsSnapshot, ...]:
    return parse_legacy_summary_csv(path.read_text())


def parse_legacy_summary_csv(text: str) -> tuple[TikTokAnalyticsSnapshot, ...]:
    rows = csv.DictReader(text.splitlines())
    return tuple(parse_legacy_summary_row(row) for row in rows)


def parse_legacy_summary_row(row: Mapping[str, Any]) -> TikTokAnalyticsSnapshot:
    raw_views = row.get(VIDEO_VIEWS_LABEL)
    views, views_est = _parse_count(raw_views)
    return TikTokAnalyticsSnapshot(
        video_id=str(row.get("video_id") or ""),
        snapshot_at=_parse_snapshot_at(
            _first_present(row.get("scraped_at"), row.get("snapshot_at"))
        ),
        views=views,
        views_est=views_est,
        total_play_seconds=_parse_duration_seconds(row.get(TOTAL_PLAY_TIME_LABEL)),
        avg_watch_seconds=_parse_duration_seconds(row.get(AVERAGE_WATCH_TIME_LABEL)),
        full_watch_percent=_parse_percent(row.get(FULL_WATCH_LABEL)),
        retention_note=_clean_text(row.get("retention_note")),
        raw_payload=dict(row),
    )


def _json_payload(payload: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, str):
        loaded = json.loads(payload)
    else:
        loaded = dict(payload)
    if not isinstance(loaded, dict):
        raise ValueError("TikTok analytics JSON payload must be an object.")
    return loaded


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if _clean_text(value) is not None:
            return value
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {
        "ERROR",
        "N/A",
        "NA",
        "<UNAVAILABLE>",
        "UNAVAILABLE",
        "NONE",
        "NULL",
    }:
        return None
    return text


def _parse_snapshot_at(value: Any) -> datetime | None:
    text = _clean_text(value)
    if text is None:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_count(value: Any) -> tuple[int | None, int | None]:
    text = _clean_text(value)
    if text is None:
        return None, None
    compact = text.replace(",", "").strip()
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<suffix>[KkMm]?)", compact)
    if match is None:
        return None, None
    number = float(match.group("number"))
    suffix = match.group("suffix").lower()
    if suffix == "k":
        return None, int(number * 1_000)
    if suffix == "m":
        return None, int(number * 1_000_000)
    if not number.is_integer():
        return None, int(number)
    exact = int(number)
    return exact, exact


def _parse_duration_seconds(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    compact = text.strip().lower().replace(" ", "")
    legacy_match = re.fullmatch(
        r"(?:(?P<hours>\d+(?:\.\d+)?)h:?)?"
        r"(?:(?P<minutes>\d+(?:\.\d+)?)m:?)?"
        r"(?:(?P<seconds>\d+(?:\.\d+)?)s?)?",
        compact,
    )
    if legacy_match and any(legacy_match.group(name) for name in ("hours", "minutes", "seconds")):
        hours = float(legacy_match.group("hours") or 0)
        minutes = float(legacy_match.group("minutes") or 0)
        seconds = float(legacy_match.group("seconds") or 0)
        return hours * 3600 + minutes * 60 + seconds
    colon_match = re.fullmatch(
        r"(?:(?P<hours>\d+):)?"
        r"(?P<minutes>\d{1,2}):"
        r"(?P<seconds>\d{1,2}(?:\.\d+)?)",
        compact,
    )
    if colon_match:
        hours = float(colon_match.group("hours") or 0)
        minutes = float(colon_match.group("minutes"))
        seconds = float(colon_match.group("seconds"))
        return hours * 3600 + minutes * 60 + seconds
    seconds_match = re.fullmatch(r"(?P<seconds>\d+(?:\.\d+)?)s?", compact)
    if seconds_match:
        return float(seconds_match.group("seconds"))
    return None


def _parse_percent(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)\s*%", text.replace(",", ""))
    if match is None:
        return None
    return float(match.group("number"))


def snapshots_by_video_id(
    snapshots: Iterable[TikTokAnalyticsSnapshot],
) -> dict[str, TikTokAnalyticsSnapshot]:
    return {snapshot.video_id: snapshot for snapshot in snapshots}

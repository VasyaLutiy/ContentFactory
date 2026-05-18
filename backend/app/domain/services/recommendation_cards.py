from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.analytics_snapshot import AnalyticsSnapshotModel
from app.db.models.export import ExportModel
from app.db.models.scene import SceneModel
from app.db.models.text_beat import TextBeatModel
from app.schemas.recommendation import RecommendationCard, RecommendationTextBeat


@dataclass(frozen=True)
class _SnapshotMetrics:
    avg_watch_seconds: float | None
    full_watch_percent: float | None
    retention_note: str | None


class RecommendationCardInputError(ValueError):
    pass


def build_recommendation_cards(
    db: Session,
    *,
    campaign_id: int,
    export_ids: list[int] | None = None,
) -> list[RecommendationCard]:
    requested_ids = _unique_ids(export_ids or [])

    exports_query = select(ExportModel).where(ExportModel.campaign_id == campaign_id)
    if requested_ids:
        exports_query = exports_query.where(ExportModel.id.in_(requested_ids))
    exports_query = exports_query.order_by(ExportModel.id.asc())
    exports = list(db.scalars(exports_query).all())
    exports_by_id = {item.id: item for item in exports}
    if requested_ids:
        missing_ids = [export_id for export_id in requested_ids if export_id not in exports_by_id]
        if missing_ids:
            raise RecommendationCardInputError(
                f"Exports not found in campaign: {', '.join(str(item) for item in missing_ids)}"
            )
        ordered_exports = [exports_by_id[export_id] for export_id in requested_ids]
    else:
        ordered_exports = exports
    if not ordered_exports:
        return []

    snapshots = list(
        db.scalars(
            select(AnalyticsSnapshotModel)
            .where(
                AnalyticsSnapshotModel.campaign_id == campaign_id,
                AnalyticsSnapshotModel.export_id.in_([item.id for item in ordered_exports]),
            )
            .order_by(
                AnalyticsSnapshotModel.export_id.asc(),
                AnalyticsSnapshotModel.snapshot_at.desc(),
                AnalyticsSnapshotModel.id.desc(),
            )
        ).all()
    )
    latest_metrics_by_export: dict[int, _SnapshotMetrics] = {}
    for snapshot in snapshots:
        if snapshot.export_id in latest_metrics_by_export:
            continue
        latest_metrics_by_export[snapshot.export_id] = _SnapshotMetrics(
            avg_watch_seconds=snapshot.avg_watch_seconds,
            full_watch_percent=snapshot.full_watch_percent,
            retention_note=snapshot.retention_note,
        )

    scored = [(item.id, _metric_score(latest_metrics_by_export.get(item.id))) for item in ordered_exports]
    best_score = max(score for _, score in scored)
    worst_score = min(score for _, score in scored)
    best_score_is_unique = _score_is_unique(scored, best_score)
    worst_score_is_unique = _score_is_unique(scored, worst_score)
    best_export_id = (
        max(scored, key=lambda entry: (entry[1], -entry[0]))[0] if best_score_is_unique else None
    )
    worst_export_id = (
        min(scored, key=lambda entry: (entry[1], entry[0]))[0] if worst_score_is_unique else None
    )

    cards: list[RecommendationCard] = []
    for export in ordered_exports:
        metrics = latest_metrics_by_export.get(export.id)
        text_metadata = _extract_text_metadata(db, export)
        evidence = _build_evidence(export.id, metrics, text_metadata)

        score = _metric_score(metrics)
        if score == 0:
            reason = "Insufficient analytics signal; recommendation is based on available retention note/text metadata."
            suggested_next_hook = _suggest_hook(text_metadata, lead_variant=False)
            suggested_next_edit = (
                "Collect another analytics snapshot before making this variant the control."
            )
        elif not _score_is_unique(scored, score):
            reason = "Variant is tied on latest watch-time and completion metrics."
            suggested_next_hook = _suggest_hook(text_metadata, lead_variant=False)
            suggested_next_edit = (
                "Keep this variant in the test set and isolate the next hook/edit change before re-ranking."
            )
        elif export.id == best_export_id:
            reason = "Top-performing variant by latest watch-time and completion metrics."
            suggested_next_hook = _suggest_hook(text_metadata, lead_variant=True)
            suggested_next_edit = (
                "Preserve this cut as control and test one isolated hook variation against it."
            )
        elif export.id == worst_export_id:
            reason = "Underperforming variant by latest watch-time and completion metrics."
            suggested_next_hook = _suggest_hook(text_metadata, lead_variant=False)
            suggested_next_edit = (
                "Trim first-second setup and tighten pacing before the first payoff to recover retention."
            )
        else:
            reason = "Middle-performing variant; useful baseline for iterative hook and pacing tests."
            suggested_next_hook = _suggest_hook(text_metadata, lead_variant=False)
            suggested_next_edit = (
                "Keep narrative structure, but test one sharper first-frame text and one shorter intro cut."
            )

        cards.append(
            RecommendationCard(
                export_id=export.id,
                export_ids=[export.id],
                variant_label=_variant_label(export),
                confidence=_confidence(metrics, text_metadata),
                reason=reason,
                evidence=evidence,
                suggested_next_hook=suggested_next_hook,
                suggested_next_edit=suggested_next_edit,
                avg_watch_seconds=metrics.avg_watch_seconds if metrics else None,
                full_watch_percent=metrics.full_watch_percent if metrics else None,
                retention_note=metrics.retention_note if metrics else None,
                no_text_experiment=text_metadata.no_text_experiment,
                on_screen_text_beats=text_metadata.beats,
                text_metadata_source=text_metadata.source,
                warnings=text_metadata.warnings,
            )
        )
    return cards


def _unique_ids(values: list[int]) -> list[int]:
    seen: set[int] = set()
    unique: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _score_is_unique(scored: list[tuple[int, float]], target_score: float) -> bool:
    return sum(1 for _, score in scored if abs(score - target_score) <= 0.000001) == 1


@dataclass(frozen=True)
class _TextMetadata:
    beats: list[RecommendationTextBeat]
    no_text_experiment: bool
    source: str | None
    warnings: list[str]


def _extract_text_metadata(db: Session, export: ExportModel) -> _TextMetadata:
    metadata = export.metadata_json if isinstance(export.metadata_json, dict) else {}
    beats = _beats_from_metadata(metadata)
    no_text_experiment = bool(metadata.get("no_text_experiment") is True)
    if beats:
        return _TextMetadata(
            beats=beats,
            no_text_experiment=no_text_experiment,
            source="export.metadata_json",
            warnings=[],
        )
    if no_text_experiment:
        return _TextMetadata(
            beats=[],
            no_text_experiment=True,
            source="export.metadata_json",
            warnings=[],
        )

    fallback_beats = _beats_from_episode(db, export.episode_id)
    if fallback_beats:
        return _TextMetadata(
            beats=fallback_beats,
            no_text_experiment=no_text_experiment,
            source="episode.scenes.text_beats",
            warnings=[],
        )

    warnings: list[str] = []
    if not no_text_experiment:
        warnings.append("Missing on-screen text beats in export metadata and episode scenes.")
    return _TextMetadata(
        beats=[],
        no_text_experiment=no_text_experiment,
        source=None,
        warnings=warnings,
    )


def _beats_from_metadata(metadata: dict[str, Any]) -> list[RecommendationTextBeat]:
    raw_beats = metadata.get("text_beats", metadata.get("on_screen_text_beats", ()))
    if not isinstance(raw_beats, list):
        return []

    beats: list[RecommendationTextBeat] = []
    for item in raw_beats:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        beats.append(
            RecommendationTextBeat(
                start=_to_float(item.get("start")),
                end=_to_float(item.get("end")),
                text=text.strip(),
                style_preset=_to_str(item.get("style_preset")),
            )
        )
    return beats


def _beats_from_episode(db: Session, episode_id: int | None) -> list[RecommendationTextBeat]:
    if episode_id is None:
        return []
    query = (
        select(TextBeatModel, SceneModel)
        .join(SceneModel, SceneModel.id == TextBeatModel.scene_id)
        .where(SceneModel.episode_id == episode_id)
        .order_by(
            SceneModel.order_index.asc(),
            TextBeatModel.priority.asc(),
            TextBeatModel.start.asc(),
            TextBeatModel.id.asc(),
        )
    )
    rows = db.execute(query).all()
    return [
        RecommendationTextBeat(
            start=text_beat.start,
            end=text_beat.end,
            text=text_beat.text,
            style_preset=text_beat.style_preset,
        )
        for text_beat, _scene in rows
    ]


def _build_evidence(
    export_id: int,
    metrics: _SnapshotMetrics | None,
    text_metadata: _TextMetadata,
) -> list[str]:
    evidence: list[str] = [f"Variant export_id={export_id}"]
    if metrics is None:
        evidence.append("No analytics snapshot found for this export.")
    else:
        evidence.append(f"Latest avg_watch_seconds={metrics.avg_watch_seconds}")
        evidence.append(f"Latest full_watch_percent={metrics.full_watch_percent}")
        if metrics.retention_note:
            evidence.append(f"Retention note: {metrics.retention_note}")
    evidence.append(
        f"On-screen text beats count={len(text_metadata.beats)} source={text_metadata.source or 'missing'}."
    )
    return evidence


def _metric_score(metrics: _SnapshotMetrics | None) -> float:
    if metrics is None:
        return 0.0
    return (metrics.avg_watch_seconds or 0.0) + (metrics.full_watch_percent or 0.0)


def _confidence(metrics: _SnapshotMetrics | None, text_metadata: _TextMetadata) -> str:
    if metrics is None:
        return "low"
    if text_metadata.warnings:
        return "medium"
    if metrics.avg_watch_seconds is not None and metrics.full_watch_percent is not None:
        return "high"
    return "medium"


def _suggest_hook(text_metadata: _TextMetadata, *, lead_variant: bool) -> str:
    if text_metadata.no_text_experiment:
        return "No-text test is enabled; open with immediate visual action and a cleaner first-frame motion cue."
    if text_metadata.beats:
        first = text_metadata.beats[0]
        return f"Iterate first beat '{first.text}' with a shorter, clearer hook under 0.30s."
    if lead_variant:
        return "Keep the opening hook but test one concise text beat at 0.00-0.30s for incremental lift."
    return "Add a concise first-frame hook beat at 0.00-0.30s and re-test against the current leader."


def _to_float(value: Any) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    return None


def _to_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _variant_label(export: ExportModel) -> str | None:
    metadata = export.metadata_json if isinstance(export.metadata_json, dict) else {}
    for key in ("variant_label", "variant", "label"):
        value = _to_str(metadata.get(key))
        if value:
            return value
    return None

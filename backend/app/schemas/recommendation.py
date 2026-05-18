from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationTextBeat(BaseModel):
    start: float | None = None
    end: float | None = None
    text: str
    style_preset: str | None = None


class RecommendationCard(BaseModel):
    export_id: int
    export_ids: list[int] = Field(default_factory=list)
    variant_label: str | None = None
    confidence: str = "medium"
    reason: str
    evidence: list[str] = Field(default_factory=list)
    suggested_next_hook: str
    suggested_next_edit: str
    avg_watch_seconds: float | None = None
    full_watch_percent: float | None = None
    retention_note: str | None = None
    no_text_experiment: bool = False
    on_screen_text_beats: list[RecommendationTextBeat] = Field(default_factory=list)
    text_metadata_source: str | None = None
    warnings: list[str] = Field(default_factory=list)

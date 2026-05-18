from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalyticsSnapshotModel(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "export_id",
            "snapshot_at",
            name="uq_analytics_snapshot_export_snapshot_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    export_id: Mapped[int] = mapped_column(
        ForeignKey("exports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_est: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_play_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_watch_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    full_watch_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    retention_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    screenshot_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_json_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    export = relationship("ExportModel", back_populates="snapshots")

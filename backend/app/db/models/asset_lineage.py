from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetLineageModel(Base):
    __tablename__ = "asset_lineage"
    __table_args__ = (
        UniqueConstraint(
            "parent_asset_id",
            "child_asset_id",
            "relationship_type",
            name="uq_asset_lineage_edge",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parent_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, default="derived_from")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

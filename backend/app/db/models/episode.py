from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EpisodeModel(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text(), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    campaign = relationship("CampaignModel", back_populates="episodes")
    scenes = relationship("SceneModel", back_populates="episode", cascade="all, delete-orphan")

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SceneModel(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    episode = relationship("EpisodeModel", back_populates="scenes")
    voice_lines = relationship("VoiceLineModel", back_populates="scene", cascade="all, delete-orphan")
    text_beats = relationship("TextBeatModel", back_populates="scene", cascade="all, delete-orphan")

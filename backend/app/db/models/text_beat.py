from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TextBeatModel(Base):
    __tablename__ = "text_beats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    start: Mapped[float] = mapped_column(Float, nullable=False)
    end: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(String(160), nullable=False)
    style_preset: Mapped[str] = mapped_column(String(100), nullable=False, default="hook_default")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scene = relationship("SceneModel", back_populates="text_beats")

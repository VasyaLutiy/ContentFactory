from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CampaignModel(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    characters = relationship("CharacterModel", back_populates="campaign", cascade="all, delete-orphan")
    episodes = relationship("EpisodeModel", back_populates="campaign", cascade="all, delete-orphan")

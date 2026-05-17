from app.db.base import Base
from app.db.models import campaign, character, episode, scene, text_beat, voice_line  # noqa: F401
from app.db.session import get_engine


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())

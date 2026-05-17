from app.db.base import Base
from app.db.models import (  # noqa: F401
    agent_approval,
    agent_event,
    agent_message,
    agent_session,
    agent_tool_call,
    campaign,
    character,
    episode,
    scene,
    text_beat,
    voice_line,
)
from app.db.session import get_engine


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())

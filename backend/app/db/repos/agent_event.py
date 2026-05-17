from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agent_event import AgentEventModel


class AgentEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_event(self, session_id: int, event_type: str, payload: dict) -> AgentEventModel:
        item = AgentEventModel(
            session_id=session_id,
            event_type=event_type,
            payload_json=payload,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def list_events(self, session_id: int, after_id: int | None = None) -> list[AgentEventModel]:
        query = select(AgentEventModel).where(AgentEventModel.session_id == session_id)
        if after_id is not None:
            query = query.where(AgentEventModel.id > after_id)
        query = query.order_by(AgentEventModel.id.asc())
        return list(self.session.scalars(query).all())

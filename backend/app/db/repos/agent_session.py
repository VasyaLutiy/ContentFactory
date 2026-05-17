from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agent_event import AgentEventModel
from app.db.models.agent_message import AgentMessageModel
from app.db.models.agent_session import AgentSessionModel


class AgentSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_session(self, session_id: int) -> AgentSessionModel | None:
        return self.session.get(AgentSessionModel, session_id)

    def create_session(self, title: str | None = None) -> AgentSessionModel:
        item = AgentSessionModel(title=title)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def create_user_and_placeholder_assistant_messages(
        self,
        session_id: int,
        user_content: str,
    ) -> tuple[AgentMessageModel, AgentMessageModel]:
        user_message = AgentMessageModel(
            session_id=session_id,
            role="user",
            content=user_content,
            event_type="message.created",
        )
        self.session.add(user_message)
        self.session.flush()

        assistant_message = AgentMessageModel(
            session_id=session_id,
            role="assistant",
            content=f"Factory Agent received message {user_message.id}. Context capture is ready.",
            event_type="message.created",
        )
        self.session.add(assistant_message)
        self.session.flush()

        self.session.add(
            AgentEventModel(
                session_id=session_id,
                event_type="message.created",
                payload_json=self._to_message_payload(user_message),
            )
        )
        self.session.add(
            AgentEventModel(
                session_id=session_id,
                event_type="message.created",
                payload_json=self._to_message_payload(assistant_message),
            )
        )

        self.session.commit()
        self.session.refresh(user_message)
        self.session.refresh(assistant_message)
        return user_message, assistant_message

    def list_messages(
        self,
        session_id: int,
        after_id: int | None = None,
    ) -> list[AgentMessageModel]:
        query = select(AgentMessageModel).where(AgentMessageModel.session_id == session_id)
        if after_id is not None:
            query = query.where(AgentMessageModel.id > after_id)
        query = query.order_by(AgentMessageModel.id.asc())
        return list(self.session.scalars(query).all())

    @staticmethod
    def _to_message_payload(message: AgentMessageModel) -> dict:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }

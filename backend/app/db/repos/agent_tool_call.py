from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.agent_tool_call import AgentToolCallModel
from app.domain.services.agent_tool_registry import AgentToolAuditSink, AgentToolCallRecord


class AgentToolCallRepository(AgentToolAuditSink):
    def __init__(self, session: Session, *, session_id: int | None = None) -> None:
        self.session = session
        self.session_id = session_id

    def record_tool_call(self, record: AgentToolCallRecord) -> None:
        item = AgentToolCallModel(
            session_id=self.session_id,
            tool_name=record.tool_name,
            safety_class=record.safety_class,
            status=record.result.status.value,
            input_json=dict(record.input),
            result_json=asdict(record.result),
            context_snapshot_json=dict(record.context_snapshot),
            duration_ms=record.duration_ms,
            created_at=record.created_at,
        )
        self.session.add(item)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def list_for_session(self, session_id: int) -> list[AgentToolCallModel]:
        query = (
            select(AgentToolCallModel)
            .where(AgentToolCallModel.session_id == session_id)
            .order_by(AgentToolCallModel.id.asc())
        )
        return list(self.session.scalars(query).all())

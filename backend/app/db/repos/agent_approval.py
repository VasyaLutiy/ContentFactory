from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.agent_approval import AgentApprovalModel
from app.schemas.common import ApprovalStatus


class AgentApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_create_render_job_approval(
        self,
        session_id: int,
        episode_id: int,
        *,
        estimated_cost: str | None,
        estimated_duration_seconds: int | None,
        output_location: str | None,
        expires_in_seconds: int,
    ) -> AgentApprovalModel:
        now = datetime.now(timezone.utc)
        item = AgentApprovalModel(
            session_id=session_id,
            action="create_render_job",
            episode_id=episode_id,
            status=ApprovalStatus.PENDING.value,
            estimated_cost=estimated_cost,
            estimated_duration_seconds=estimated_duration_seconds,
            output_location=output_location,
            created_at=now,
            expires_at=now + timedelta(seconds=expires_in_seconds),
        )
        self.session.add(item)
        self.session.flush()
        return item

    def get_for_session(self, session_id: int, approval_id: int) -> AgentApprovalModel | None:
        query = select(AgentApprovalModel).where(
            AgentApprovalModel.id == approval_id,
            AgentApprovalModel.session_id == session_id,
        )
        return self.session.scalar(query)

    def expire(self, approval: AgentApprovalModel) -> AgentApprovalModel:
        approval.status = ApprovalStatus.EXPIRED.value
        approval.decided_at = datetime.now(timezone.utc)
        self.session.add(approval)
        self.session.flush()
        return approval

    def decide(
        self,
        approval: AgentApprovalModel,
        *,
        status: ApprovalStatus,
        decided_by: str,
        reason: str | None,
        now: datetime | None = None,
    ) -> AgentApprovalModel | None:
        decided_at = now or datetime.now(timezone.utc)
        statement = (
            update(AgentApprovalModel)
            .where(
                AgentApprovalModel.id == approval.id,
                AgentApprovalModel.session_id == approval.session_id,
                AgentApprovalModel.status == ApprovalStatus.PENDING.value,
                AgentApprovalModel.expires_at > decided_at,
            )
            .values(
                status=status.value,
                decided_by=decided_by,
                reason=reason,
                decided_at=decided_at,
            )
            .execution_options(synchronize_session=False)
        )
        result = self.session.execute(statement)
        self.session.flush()
        if result.rowcount != 1:
            return None
        self.session.refresh(approval)
        return approval

    def claim_render_job(self, approval: AgentApprovalModel, *, job_id: str) -> bool:
        now = datetime.now(timezone.utc)
        statement = (
            update(AgentApprovalModel)
            .where(
                AgentApprovalModel.id == approval.id,
                AgentApprovalModel.session_id == approval.session_id,
                AgentApprovalModel.status == ApprovalStatus.APPROVED.value,
                AgentApprovalModel.render_job_id.is_(None),
                AgentApprovalModel.expires_at > now,
            )
            .values(render_job_id=job_id)
            .execution_options(synchronize_session=False)
        )
        result = self.session.execute(statement)
        self.session.flush()
        if result.rowcount != 1:
            return False
        approval.render_job_id = job_id
        return True

    @staticmethod
    def is_expired(approval: AgentApprovalModel) -> bool:
        expires_at = approval.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires_at

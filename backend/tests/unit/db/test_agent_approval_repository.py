from datetime import timedelta

from app.db.repos.agent_approval import AgentApprovalRepository
from app.db.repos.agent_session import AgentSessionRepository
from app.db.session import get_session_maker
from app.schemas.common import ApprovalStatus


def test_decide_does_not_approve_when_expired_at_write_boundary() -> None:
    session_maker = get_session_maker()
    with session_maker() as db:
        agent_session = AgentSessionRepository(db).create_session(title="approval-boundary")
        approval_repo = AgentApprovalRepository(db)
        approval = approval_repo.create_create_render_job_approval(
            session_id=agent_session.id,
            episode_id=10,
            estimated_cost=None,
            estimated_duration_seconds=None,
            output_location=None,
            expires_in_seconds=1,
        )
        stale_decision_time = approval.expires_at + timedelta(microseconds=1)

        decided = approval_repo.decide(
            approval,
            status=ApprovalStatus.APPROVED,
            decided_by="operator",
            reason=None,
            now=stale_decision_time,
        )

        assert decided is None
        db.refresh(approval)
        assert approval.status == ApprovalStatus.PENDING.value
        assert approval.decided_at is None

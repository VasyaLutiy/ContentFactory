import json
from collections.abc import Iterator
import logging
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.agent_approval import AgentApprovalRepository
from app.db.repos.agent_event import AgentEventRepository
from app.db.repos.agent_session import AgentSessionRepository
from app.db.session import get_db_session
from app.schemas.common import ApprovalStatus
from app.schemas.agent import (
    AgentMessageCreate,
    AgentMessageCreateResponse,
    AgentMessageRead,
    ApprovalCreate,
    ApprovalDecisionRequest,
    ApprovalRead,
    CreateRenderJobRequest,
    RenderJobCreateResponse,
    AgentSessionCreate,
    AgentSessionRead,
)
from app.workers.queue import render_queue

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/sessions",
    response_model=AgentSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    payload: AgentSessionCreate,
    db: Session = Depends(get_db_session),
) -> AgentSessionRead:
    repo = AgentSessionRepository(db)
    try:
        return repo.create_session(title=payload.title)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session conflict",
        ) from exc


@router.post(
    "/sessions/{session_id}/messages",
    response_model=AgentMessageCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    session_id: int,
    payload: AgentMessageCreate,
    db: Session = Depends(get_db_session),
) -> AgentMessageCreateResponse:
    repo = AgentSessionRepository(db)
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    try:
        user_message, assistant_message = repo.create_user_and_placeholder_assistant_messages(
            session_id=session_id,
            user_content=payload.content,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Message conflict",
        ) from exc
    return AgentMessageCreateResponse(
        user_message=AgentMessageRead.model_validate(user_message),
        assistant_message=AgentMessageRead.model_validate(assistant_message),
    )


@router.get("/sessions/{session_id}/events")
def stream_events(
    session_id: int,
    after_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    session_repo = AgentSessionRepository(db)
    session = session_repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    events = AgentEventRepository(db).list_events(session_id=session_id, after_id=after_id)
    return StreamingResponse(_iter_sse_events(events), media_type="text/event-stream")


@router.post(
    "/sessions/{session_id}/approvals",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def request_create_render_job_approval(
    session_id: int,
    payload: ApprovalCreate,
    db: Session = Depends(get_db_session),
) -> ApprovalRead:
    session_repo = AgentSessionRepository(db)
    session = session_repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    approval = AgentApprovalRepository(db).create_create_render_job_approval(
        session_id=session_id,
        episode_id=payload.episode_id,
        estimated_cost=payload.estimated_cost,
        estimated_duration_seconds=payload.estimated_duration_seconds,
        output_location=payload.output_location,
        expires_in_seconds=payload.expires_in_seconds,
    )
    AgentEventRepository(db).create_event(
        session_id=session_id,
        event_type="approval.required",
        payload={
            "approval_id": approval.id,
            "action": approval.action,
            "episode_id": approval.episode_id,
            "status": approval.status,
            "estimated_cost": approval.estimated_cost,
            "estimated_duration_seconds": approval.estimated_duration_seconds,
            "output_location": approval.output_location,
            "created_at": approval.created_at.isoformat(),
            "expires_at": approval.expires_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(approval)
    return ApprovalRead.model_validate(approval)


@router.post(
    "/sessions/{session_id}/approvals/{approval_id}/approve",
    response_model=ApprovalRead,
)
def approve_create_render_job(
    session_id: int,
    approval_id: int,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db_session),
) -> ApprovalRead:
    approval_repo = AgentApprovalRepository(db)
    approval = approval_repo.get_for_session(session_id=session_id, approval_id=approval_id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    if approval.status != ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval already resolved",
        )
    if approval_repo.is_expired(approval):
        approval = approval_repo.expire(approval)
        _emit_approval_resolved(db, session_id=session_id, approval=approval)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired")

    decided_approval = approval_repo.decide(
        approval,
        status=ApprovalStatus.APPROVED,
        decided_by=payload.decided_by,
        reason=payload.reason,
    )
    if decided_approval is None:
        db.refresh(approval)
        if approval.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approval already resolved",
            )
        approval = approval_repo.expire(approval)
        _emit_approval_resolved(db, session_id=session_id, approval=approval)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired")
    approval = decided_approval
    _emit_approval_resolved(db, session_id=session_id, approval=approval)
    db.commit()
    db.refresh(approval)
    return ApprovalRead.model_validate(approval)


@router.post("/sessions/{session_id}/approvals/{approval_id}/reject", response_model=ApprovalRead)
def reject_create_render_job(
    session_id: int,
    approval_id: int,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db_session),
) -> ApprovalRead:
    approval_repo = AgentApprovalRepository(db)
    approval = approval_repo.get_for_session(session_id=session_id, approval_id=approval_id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    if approval.status != ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval already resolved",
        )
    if approval_repo.is_expired(approval):
        approval = approval_repo.expire(approval)
        _emit_approval_resolved(db, session_id=session_id, approval=approval)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired")

    decided_approval = approval_repo.decide(
        approval,
        status=ApprovalStatus.REJECTED,
        decided_by=payload.decided_by,
        reason=payload.reason,
    )
    if decided_approval is None:
        db.refresh(approval)
        if approval.status != ApprovalStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approval already resolved",
            )
        approval = approval_repo.expire(approval)
        _emit_approval_resolved(db, session_id=session_id, approval=approval)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired")
    approval = decided_approval
    _emit_approval_resolved(db, session_id=session_id, approval=approval)
    db.commit()
    db.refresh(approval)
    return ApprovalRead.model_validate(approval)


@router.post(
    "/sessions/{session_id}/render-jobs",
    response_model=RenderJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_render_job(
    session_id: int,
    payload: CreateRenderJobRequest,
    db: Session = Depends(get_db_session),
) -> RenderJobCreateResponse:
    approval_repo = AgentApprovalRepository(db)
    approval = approval_repo.get_for_session(
        session_id=session_id,
        approval_id=payload.approval_id,
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    if approval.action != "create_render_job" or approval.episode_id != payload.episode_id:
        _emit_error(
            db,
            session_id=session_id,
            code="approval_mismatch",
            message="Approval does not match render job",
            approval_id=payload.approval_id,
            retryable=False,
            status_code=status.HTTP_409_CONFLICT,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval does not match render job",
        )
    if approval.status != ApprovalStatus.APPROVED.value:
        _emit_error(
            db,
            session_id=session_id,
            code="approval_required",
            message="Approval required",
            approval_id=payload.approval_id,
            retryable=False,
            status_code=status.HTTP_409_CONFLICT,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval required")
    if approval_repo.is_expired(approval):
        approval = approval_repo.expire(approval)
        _emit_approval_resolved(db, session_id=session_id, approval=approval)
        _emit_error(
            db,
            session_id=session_id,
            code="approval_expired",
            message="Approval expired",
            approval_id=payload.approval_id,
            retryable=False,
            status_code=status.HTTP_409_CONFLICT,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired")
    job_id = _resolve_render_job_id(
        session_id=session_id,
        approval_id=approval.id,
        episode_id=payload.episode_id,
        idempotency_key=payload.idempotency_key,
    )
    if not approval_repo.claim_render_job(approval, job_id=job_id):
        db.refresh(approval)
        if approval.render_job_id is not None:
            if payload.idempotency_key and approval.render_job_id == job_id:
                existing = render_queue.get(approval.render_job_id)
                queue_recovered = existing is None
                if existing is None:
                    existing = render_queue.enqueue(
                        episode_id=str(payload.episode_id),
                        job_id=approval.render_job_id,
                    )
                logger.info(
                    "render_job_create_idempotent_replay",
                    extra={
                        "session_id": session_id,
                        "approval_id": approval.id,
                        "episode_id": payload.episode_id,
                        "job_id": approval.render_job_id,
                        "idempotency_key_present": True,
                        "queue_recovered": queue_recovered,
                        "status": existing.status.value,
                    },
                )
                return RenderJobCreateResponse(
                    id=approval.render_job_id,
                    episode_id=str(payload.episode_id),
                    status=existing.status.value,
                    approval_id=approval.id,
                )
            _emit_error(
                db,
                session_id=session_id,
                code="approval_consumed",
                message="Approval already used",
                approval_id=payload.approval_id,
                retryable=False,
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "render_job_id": approval.render_job_id,
                    "idempotency_key_present": payload.idempotency_key is not None,
                },
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approval already used",
            )
        if approval_repo.is_expired(approval):
            approval = approval_repo.expire(approval)
            _emit_approval_resolved(db, session_id=session_id, approval=approval)
            _emit_error(
                db,
                session_id=session_id,
                code="approval_expired",
                message="Approval expired",
                approval_id=payload.approval_id,
                retryable=False,
                status_code=status.HTTP_409_CONFLICT,
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired")
        _emit_error(
            db,
            session_id=session_id,
            code="approval_required",
            message="Approval required",
            approval_id=payload.approval_id,
            retryable=False,
            status_code=status.HTTP_409_CONFLICT,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval required")

    AgentEventRepository(db).create_event(
        session_id=session_id,
        event_type="tool.started",
        payload={
            "tool_name": "create_render_job",
            "approval_id": approval.id,
            "episode_id": approval.episode_id,
            "job_id": job_id,
            "idempotency_key_present": payload.idempotency_key is not None,
        },
    )
    job_status = "queued"
    AgentEventRepository(db).create_event(
        session_id=session_id,
        event_type="tool.result",
        payload={
            "tool_name": "create_render_job",
            "job_id": job_id,
            "episode_id": str(payload.episode_id),
            "status": job_status,
            "approval_id": approval.id,
            "idempotency_key_present": payload.idempotency_key is not None,
        },
    )
    AgentEventRepository(db).create_event(
        session_id=session_id,
        event_type="done",
        payload={
            "tool_name": "create_render_job",
            "job_id": job_id,
            "approval_id": approval.id,
        },
    )
    db.commit()
    job = render_queue.enqueue(episode_id=str(payload.episode_id), job_id=job_id)
    logger.info(
        "render_job_created",
        extra={
            "session_id": session_id,
            "approval_id": approval.id,
            "episode_id": payload.episode_id,
            "job_id": job.id,
            "status": job.status.value,
            "idempotency_key_present": payload.idempotency_key is not None,
        },
    )
    return RenderJobCreateResponse(
        id=job.id,
        episode_id=job.episode_id,
        status=job.status.value,
        approval_id=approval.id,
    )


def _resolve_render_job_id(
    *,
    session_id: int,
    approval_id: int,
    episode_id: int,
    idempotency_key: str | None,
) -> str:
    if not idempotency_key:
        return str(uuid4())
    return str(
        uuid5(
            NAMESPACE_URL,
            f"agent-render-job:{session_id}:{approval_id}:{episode_id}:{idempotency_key}",
        )
    )


def _iter_sse_events(events: list) -> Iterator[str]:
    for item in events:
        payload = dict(item.payload_json)
        payload.setdefault("session_id", item.session_id)
        payload.setdefault("emitted_at", item.created_at.isoformat())
        yield f"id: {item.id}\n"
        yield f"event: {item.event_type}\n"
        yield f"data: {json.dumps(payload)}\n\n"


def _emit_approval_resolved(db: Session, *, session_id: int, approval) -> None:
    AgentEventRepository(db).create_event(
        session_id=session_id,
        event_type="approval.resolved",
        payload={
            "approval_id": approval.id,
            "action": approval.action,
            "episode_id": approval.episode_id,
            "status": approval.status,
            "decided_by": approval.decided_by,
            "reason": approval.reason,
            "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        },
    )


def _emit_error(
    db: Session,
    *,
    session_id: int,
    code: str,
    message: str,
    approval_id: int,
    retryable: bool,
    status_code: int,
    details: dict | None = None,
) -> None:
    payload = {
        "status": "error",
        "code": code,
        "message": message,
        "approval_id": approval_id,
        "retryable": retryable,
        "status_code": status_code,
    }
    if details:
        payload["details"] = details
    AgentEventRepository(db).create_event(
        session_id=session_id,
        event_type="error",
        payload=payload,
    )

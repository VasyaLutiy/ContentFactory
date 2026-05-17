import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.agent_session import AgentSessionRepository
from app.db.session import get_db_session
from app.schemas.agent import (
    AgentMessageCreate,
    AgentMessageCreateResponse,
    AgentMessageRead,
    AgentSessionCreate,
    AgentSessionRead,
)

router = APIRouter()


@router.post("/sessions", response_model=AgentSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: AgentSessionCreate, db: Session = Depends(get_db_session)) -> AgentSessionRead:
    repo = AgentSessionRepository(db)
    try:
        return repo.create_session(title=payload.title)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session conflict") from exc


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Message conflict") from exc
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
    repo = AgentSessionRepository(db)
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = repo.list_messages(session_id=session_id, after_id=after_id)
    return StreamingResponse(_iter_sse_messages(messages), media_type="text/event-stream")


def _iter_sse_messages(messages: list) -> Iterator[str]:
    for message in messages:
        payload = {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        yield f"id: {message.id}\n"
        yield f"event: {message.event_type}\n"
        yield f"data: {json.dumps(payload)}\n\n"

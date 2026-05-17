from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.voice_line import VoiceLineRepository
from app.db.session import get_db_session
from app.schemas.voice_line import VoiceLineCreate, VoiceLineRead, VoiceLineUpdate

router = APIRouter()


@router.get("", response_model=list[VoiceLineRead])
def list_voice_lines(db: Session = Depends(get_db_session)) -> list[VoiceLineRead]:
    return VoiceLineRepository(db).list()


@router.post("", response_model=VoiceLineRead, status_code=status.HTTP_201_CREATED)
def create_voice_line(payload: VoiceLineCreate, db: Session = Depends(get_db_session)) -> VoiceLineRead:
    repo = VoiceLineRepository(db)
    try:
        return repo.create(payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Voice line conflict") from exc


@router.get("/{voice_line_id}", response_model=VoiceLineRead)
def get_voice_line(voice_line_id: int, db: Session = Depends(get_db_session)) -> VoiceLineRead:
    repo = VoiceLineRepository(db)
    voice_line = repo.get(voice_line_id)
    if voice_line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice line not found")
    return voice_line


@router.put("/{voice_line_id}", response_model=VoiceLineRead)
def update_voice_line(
    voice_line_id: int,
    payload: VoiceLineUpdate,
    db: Session = Depends(get_db_session),
) -> VoiceLineRead:
    repo = VoiceLineRepository(db)
    voice_line = repo.get(voice_line_id)
    if voice_line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice line not found")

    try:
        return repo.update(voice_line, payload.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Voice line conflict") from exc


@router.delete("/{voice_line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_line(voice_line_id: int, db: Session = Depends(get_db_session)) -> Response:
    repo = VoiceLineRepository(db)
    voice_line = repo.get(voice_line_id)
    if voice_line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice line not found")

    repo.delete(voice_line)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

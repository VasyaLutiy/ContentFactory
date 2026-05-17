from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.text_beat import TextBeatRepository
from app.db.session import get_db_session
from app.schemas.text_beat_crud import TextBeatCreate, TextBeatRead, TextBeatUpdate

router = APIRouter()


@router.get("", response_model=list[TextBeatRead])
def list_text_beats(db: Session = Depends(get_db_session)) -> list[TextBeatRead]:
    return TextBeatRepository(db).list()


@router.post("", response_model=TextBeatRead, status_code=status.HTTP_201_CREATED)
def create_text_beat(payload: TextBeatCreate, db: Session = Depends(get_db_session)) -> TextBeatRead:
    repo = TextBeatRepository(db)
    try:
        return repo.create(payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Text beat conflict") from exc


@router.get("/{text_beat_id}", response_model=TextBeatRead)
def get_text_beat(text_beat_id: int, db: Session = Depends(get_db_session)) -> TextBeatRead:
    repo = TextBeatRepository(db)
    text_beat = repo.get(text_beat_id)
    if text_beat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Text beat not found")
    return text_beat


@router.put("/{text_beat_id}", response_model=TextBeatRead)
def update_text_beat(
    text_beat_id: int,
    payload: TextBeatUpdate,
    db: Session = Depends(get_db_session),
) -> TextBeatRead:
    repo = TextBeatRepository(db)
    text_beat = repo.get(text_beat_id)
    if text_beat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Text beat not found")

    try:
        return repo.update(text_beat, payload.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Text beat conflict") from exc


@router.delete("/{text_beat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_text_beat(text_beat_id: int, db: Session = Depends(get_db_session)) -> Response:
    repo = TextBeatRepository(db)
    text_beat = repo.get(text_beat_id)
    if text_beat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Text beat not found")

    repo.delete(text_beat)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

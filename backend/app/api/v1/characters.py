from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.character import CharacterRepository
from app.db.session import get_db_session
from app.schemas.character import CharacterCreate, CharacterRead, CharacterUpdate

router = APIRouter()


@router.get("", response_model=list[CharacterRead])
def list_characters(db: Session = Depends(get_db_session)) -> list[CharacterRead]:
    return CharacterRepository(db).list()


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def create_character(payload: CharacterCreate, db: Session = Depends(get_db_session)) -> CharacterRead:
    repo = CharacterRepository(db)
    try:
        return repo.create(payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Character conflict") from exc


@router.get("/{character_id}", response_model=CharacterRead)
def get_character(character_id: int, db: Session = Depends(get_db_session)) -> CharacterRead:
    repo = CharacterRepository(db)
    character = repo.get(character_id)
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    return character


@router.put("/{character_id}", response_model=CharacterRead)
def update_character(
    character_id: int,
    payload: CharacterUpdate,
    db: Session = Depends(get_db_session),
) -> CharacterRead:
    repo = CharacterRepository(db)
    character = repo.get(character_id)
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    try:
        return repo.update(character, payload.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Character conflict") from exc


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(character_id: int, db: Session = Depends(get_db_session)) -> Response:
    repo = CharacterRepository(db)
    character = repo.get(character_id)
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    repo.delete(character)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

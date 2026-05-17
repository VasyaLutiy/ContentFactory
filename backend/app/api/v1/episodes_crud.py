from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.episode import EpisodeRepository
from app.db.session import get_db_session
from app.schemas.episode_crud import EpisodeCreate, EpisodeRead, EpisodeUpdate

router = APIRouter()


@router.get("", response_model=list[EpisodeRead])
def list_episodes(db: Session = Depends(get_db_session)) -> list[EpisodeRead]:
    return EpisodeRepository(db).list()


@router.post("", response_model=EpisodeRead, status_code=status.HTTP_201_CREATED)
def create_episode(payload: EpisodeCreate, db: Session = Depends(get_db_session)) -> EpisodeRead:
    repo = EpisodeRepository(db)
    try:
        return repo.create(payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Episode conflict") from exc


@router.get("/{episode_id}", response_model=EpisodeRead)
def get_episode(episode_id: int, db: Session = Depends(get_db_session)) -> EpisodeRead:
    repo = EpisodeRepository(db)
    episode = repo.get(episode_id)
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")
    return episode


@router.put("/{episode_id}", response_model=EpisodeRead)
def update_episode(
    episode_id: int,
    payload: EpisodeUpdate,
    db: Session = Depends(get_db_session),
) -> EpisodeRead:
    repo = EpisodeRepository(db)
    episode = repo.get(episode_id)
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    try:
        return repo.update(episode, payload.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Episode conflict") from exc


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: int, db: Session = Depends(get_db_session)) -> Response:
    repo = EpisodeRepository(db)
    episode = repo.get(episode_id)
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found")

    repo.delete(episode)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

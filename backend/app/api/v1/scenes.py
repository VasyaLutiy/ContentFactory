from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.scene import SceneRepository
from app.db.session import get_db_session
from app.schemas.scene import SceneCreate, SceneRead, SceneUpdate

router = APIRouter()


@router.get("", response_model=list[SceneRead])
def list_scenes(db: Session = Depends(get_db_session)) -> list[SceneRead]:
    return SceneRepository(db).list()


@router.post("", response_model=SceneRead, status_code=status.HTTP_201_CREATED)
def create_scene(payload: SceneCreate, db: Session = Depends(get_db_session)) -> SceneRead:
    repo = SceneRepository(db)
    try:
        return repo.create(payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Scene conflict") from exc


@router.get("/{scene_id}", response_model=SceneRead)
def get_scene(scene_id: int, db: Session = Depends(get_db_session)) -> SceneRead:
    repo = SceneRepository(db)
    scene = repo.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    return scene


@router.put("/{scene_id}", response_model=SceneRead)
def update_scene(
    scene_id: int,
    payload: SceneUpdate,
    db: Session = Depends(get_db_session),
) -> SceneRead:
    repo = SceneRepository(db)
    scene = repo.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    try:
        return repo.update(scene, payload.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Scene conflict") from exc


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(scene_id: int, db: Session = Depends(get_db_session)) -> Response:
    repo = SceneRepository(db)
    scene = repo.get(scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    repo.delete(scene)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

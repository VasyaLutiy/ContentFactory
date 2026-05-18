from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.export import ExportRepository
from app.db.session import get_db_session
from app.schemas.export import ExportCreate, ExportRead, ExportTikTokVideoIdUpdate

router = APIRouter()


@router.get("", response_model=list[ExportRead])
def list_exports(
    campaign_id: int | None = None,
    episode_id: int | None = None,
    platform: str | None = None,
    render_job_id: str | None = None,
    db: Session = Depends(get_db_session),
) -> list[ExportRead]:
    exports = ExportRepository(db).list(
        campaign_id=campaign_id,
        episode_id=episode_id,
        platform=platform,
        render_job_id=render_job_id,
    )
    return [ExportRead.from_model(export) for export in exports]


@router.post("", response_model=ExportRead, status_code=status.HTTP_201_CREATED)
def create_export(payload: ExportCreate, db: Session = Depends(get_db_session)) -> ExportRead:
    repo = ExportRepository(db)
    try:
        export = repo.create(**payload.model_dump())
        db.commit()
        db.refresh(export)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export conflict") from exc
    return ExportRead.from_model(export)


@router.get("/{export_id}", response_model=ExportRead)
def get_export(export_id: int, db: Session = Depends(get_db_session)) -> ExportRead:
    export = ExportRepository(db).get(export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return ExportRead.from_model(export)


@router.put("/{export_id}/tiktok-video", response_model=ExportRead)
def update_export_tiktok_video(
    export_id: int,
    payload: ExportTikTokVideoIdUpdate,
    db: Session = Depends(get_db_session),
) -> ExportRead:
    repo = ExportRepository(db)
    export = repo.get(export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    try:
        export = repo.update_tiktok_video_id(export, payload.tiktok_video_id)
        db.commit()
        db.refresh(export)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export conflict") from exc
    return ExportRead.from_model(export)

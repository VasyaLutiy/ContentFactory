from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.analytics_snapshot import AnalyticsSnapshotRepository
from app.db.repos.export import ExportRepository
from app.db.session import get_db_session
from app.domain.services.tiktok_analytics_ingestion import (
    TikTokAnalyticsIngestionError,
    TikTokSnapshotArtifactLinks,
    write_tiktok_analytics_snapshot,
)
from app.providers.tiktok.analytics import parse_legacy_summary_row, parse_legacy_video_json
from app.schemas.analytics import (
    AnalyticsSnapshotCreate,
    AnalyticsSnapshotRead,
    TikTokAnalyticsIngestPayload,
)

router = APIRouter()


@router.get("/snapshots", response_model=list[AnalyticsSnapshotRead])
def list_snapshots(
    campaign_id: int | None = None,
    export_id: int | None = None,
    db: Session = Depends(get_db_session),
) -> list[AnalyticsSnapshotRead]:
    snapshots = AnalyticsSnapshotRepository(db).list(campaign_id=campaign_id, export_id=export_id)
    return [AnalyticsSnapshotRead.from_model(snapshot) for snapshot in snapshots]


@router.post("/snapshots", response_model=AnalyticsSnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    payload: AnalyticsSnapshotCreate,
    db: Session = Depends(get_db_session),
) -> AnalyticsSnapshotRead:
    export = ExportRepository(db).get(payload.export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if export.campaign_id != payload.campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analytics snapshot campaign does not match export",
        )
    try:
        snapshot = AnalyticsSnapshotRepository(db).create(**payload.model_dump())
        db.commit()
        db.refresh(snapshot)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analytics snapshot conflict") from exc
    return AnalyticsSnapshotRead.from_model(snapshot)


@router.post(
    "/tiktok/ingest",
    response_model=AnalyticsSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_tiktok_snapshot(
    payload: TikTokAnalyticsIngestPayload,
    db: Session = Depends(get_db_session),
) -> AnalyticsSnapshotRead:
    export = ExportRepository(db).get(payload.export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    parsed = (
        parse_legacy_video_json(payload.legacy_json)
        if payload.legacy_json is not None
        else parse_legacy_summary_row(payload.summary_row or {})
    )
    try:
        snapshot = write_tiktok_analytics_snapshot(
            db,
            export=export,
            snapshot=parsed,
            artifacts=TikTokSnapshotArtifactLinks(
                screenshot_asset_id=payload.screenshot_asset_id,
                source_json_asset_id=payload.source_json_asset_id,
            ),
        )
        db.commit()
        db.refresh(snapshot)
    except TikTokAnalyticsIngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analytics snapshot conflict") from exc
    return AnalyticsSnapshotRead.from_model(snapshot)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.repos.asset import AssetRepository
from app.db.session import get_db_session
from app.schemas.artifact import ArtifactLineageRead, ArtifactRead
from app.schemas.common import AssetKind

router = APIRouter()


@router.get("", response_model=list[ArtifactRead])
def list_artifacts(
    namespace: str | None = None,
    kind: AssetKind | None = None,
    db: Session = Depends(get_db_session),
) -> list[ArtifactRead]:
    assets = AssetRepository(db).list(namespace=namespace, kind=kind)
    return [ArtifactRead.from_model(asset) for asset in assets]


@router.get("/{artifact_id}", response_model=ArtifactRead)
def get_artifact(artifact_id: int, db: Session = Depends(get_db_session)) -> ArtifactRead:
    asset = AssetRepository(db).get(artifact_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return ArtifactRead.from_model(asset)


@router.get("/{artifact_id}/lineage", response_model=ArtifactLineageRead)
def get_artifact_lineage(
    artifact_id: int,
    db: Session = Depends(get_db_session),
) -> ArtifactLineageRead:
    lineage = AssetRepository(db).lineage(artifact_id)
    if lineage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return ArtifactLineageRead.from_lineage(lineage)

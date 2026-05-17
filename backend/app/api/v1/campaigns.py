from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repos.campaign import CampaignRepository
from app.db.session import get_db_session
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate

router = APIRouter()


@router.get("", response_model=list[CampaignRead])
def list_campaigns(db: Session = Depends(get_db_session)) -> list[CampaignRead]:
    return CampaignRepository(db).list()


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db_session)) -> CampaignRead:
    repo = CampaignRepository(db)
    try:
        return repo.create(payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign conflict") from exc


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: int, db: Session = Depends(get_db_session)) -> CampaignRead:
    repo = CampaignRepository(db)
    campaign = repo.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.put("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db_session),
) -> CampaignRead:
    repo = CampaignRepository(db)
    campaign = repo.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    data = payload.model_dump(exclude_unset=True)
    try:
        return repo.update(campaign, data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign conflict") from exc


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db_session)) -> Response:
    repo = CampaignRepository(db)
    campaign = repo.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    repo.delete(campaign)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

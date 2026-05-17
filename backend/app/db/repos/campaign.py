from app.db.models.campaign import CampaignModel
from app.db.repos.base import CRUDRepository


class CampaignRepository(CRUDRepository[CampaignModel]):
    def __init__(self, session):
        super().__init__(session=session, model_cls=CampaignModel)

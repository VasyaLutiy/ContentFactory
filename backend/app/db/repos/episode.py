from app.db.models.episode import EpisodeModel
from app.db.repos.base import CRUDRepository


class EpisodeRepository(CRUDRepository[EpisodeModel]):
    def __init__(self, session):
        super().__init__(session=session, model_cls=EpisodeModel)

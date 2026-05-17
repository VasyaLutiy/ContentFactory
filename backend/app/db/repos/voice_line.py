from app.db.models.voice_line import VoiceLineModel
from app.db.repos.base import CRUDRepository


class VoiceLineRepository(CRUDRepository[VoiceLineModel]):
    def __init__(self, session):
        super().__init__(session=session, model_cls=VoiceLineModel)

from app.db.models.text_beat import TextBeatModel
from app.db.repos.base import CRUDRepository


class TextBeatRepository(CRUDRepository[TextBeatModel]):
    def __init__(self, session):
        super().__init__(session=session, model_cls=TextBeatModel)

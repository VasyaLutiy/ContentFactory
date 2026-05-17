from app.db.models.character import CharacterModel
from app.db.repos.base import CRUDRepository


class CharacterRepository(CRUDRepository[CharacterModel]):
    def __init__(self, session):
        super().__init__(session=session, model_cls=CharacterModel)

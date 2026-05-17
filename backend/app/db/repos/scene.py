from app.db.models.scene import SceneModel
from app.db.repos.base import CRUDRepository


class SceneRepository(CRUDRepository[SceneModel]):
    def __init__(self, session):
        super().__init__(session=session, model_cls=SceneModel)

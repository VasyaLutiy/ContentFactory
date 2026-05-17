from pydantic import BaseModel, Field


class SceneBase(BaseModel):
    episode_id: int
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = None
    order_index: int = 0


class SceneCreate(SceneBase):
    pass


class SceneUpdate(BaseModel):
    episode_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = None
    order_index: int | None = None


class SceneRead(SceneBase):
    id: int

    model_config = {"from_attributes": True}

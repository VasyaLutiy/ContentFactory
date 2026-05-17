from pydantic import BaseModel, Field


class EpisodeBase(BaseModel):
    campaign_id: int
    title: str = Field(min_length=1, max_length=200)
    synopsis: str | None = None
    order_index: int = 0


class EpisodeCreate(EpisodeBase):
    pass


class EpisodeUpdate(BaseModel):
    campaign_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    synopsis: str | None = None
    order_index: int | None = None


class EpisodeRead(EpisodeBase):
    id: int

    model_config = {"from_attributes": True}

from pydantic import BaseModel, Field


class CampaignBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class CampaignRead(CampaignBase):
    id: int

    model_config = {"from_attributes": True}

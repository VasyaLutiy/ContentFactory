from pydantic import BaseModel, Field


class CharacterBase(BaseModel):
    campaign_id: int
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=80)
    description: str | None = None


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseModel):
    campaign_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=80)
    description: str | None = None


class CharacterRead(CharacterBase):
    id: int

    model_config = {"from_attributes": True}

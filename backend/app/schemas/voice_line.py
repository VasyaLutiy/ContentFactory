from pydantic import BaseModel, Field


class VoiceLineBase(BaseModel):
    scene_id: int
    character_id: int | None = None
    text: str = Field(min_length=1)
    start_ms: int | None = None
    end_ms: int | None = None


class VoiceLineCreate(VoiceLineBase):
    pass


class VoiceLineUpdate(BaseModel):
    scene_id: int | None = None
    character_id: int | None = None
    text: str | None = Field(default=None, min_length=1)
    start_ms: int | None = None
    end_ms: int | None = None


class VoiceLineRead(VoiceLineBase):
    id: int

    model_config = {"from_attributes": True}

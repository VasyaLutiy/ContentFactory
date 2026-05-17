from pydantic import BaseModel, Field


class TextBeatBase(BaseModel):
    scene_id: int
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=160)
    style_preset: str = Field(default="hook_default", min_length=1, max_length=100)
    priority: int = 0


class TextBeatCreate(TextBeatBase):
    pass


class TextBeatUpdate(BaseModel):
    scene_id: int | None = None
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0)
    text: str | None = Field(default=None, min_length=1, max_length=160)
    style_preset: str | None = Field(default=None, min_length=1, max_length=100)
    priority: int | None = None


class TextBeatRead(TextBeatBase):
    id: int

    model_config = {"from_attributes": True}

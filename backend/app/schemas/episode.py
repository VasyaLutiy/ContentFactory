from pydantic import BaseModel, Field


class SafeArea(BaseModel):
    x: float = Field(default=0.08, ge=0.0, le=1.0)
    y: float = Field(default=0.12, ge=0.0, le=1.0)
    width: float = Field(default=0.84, gt=0.0, le=1.0)
    height: float = Field(default=0.22, gt=0.0, le=1.0)


class OnScreenTextBeat(BaseModel):
    id: str | None = None
    scene_id: str | None = None
    start: float = Field(ge=0.0)
    end: float = Field(gt=0.0)
    text: str = Field(min_length=1, max_length=160)
    style_preset: str = "hook_default"
    safe_area: SafeArea = Field(default_factory=SafeArea)
    priority: int = 0


class TextBeatValidationIssue(BaseModel):
    code: str
    message: str
    beat_id: str | None = None


class TextBeatValidationResult(BaseModel):
    valid: bool
    issues: list[TextBeatValidationIssue] = Field(default_factory=list)


class TextBeatValidationRequest(BaseModel):
    beats: list[OnScreenTextBeat] = Field(default_factory=list)
    no_text_experiment: bool = False

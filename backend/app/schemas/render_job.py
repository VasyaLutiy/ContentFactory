from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.common import RenderJobStatus, RenderStepKind


class RenderStep(BaseModel):
    kind: RenderStepKind
    status: RenderJobStatus = RenderJobStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    retry_count: int = 0
    error_code: str | None = None
    error_details: str | None = None


class RenderJob(BaseModel):
    id: str
    episode_id: str
    status: RenderJobStatus = RenderJobStatus.QUEUED
    steps: list[RenderStep] = Field(default_factory=list)
    retry_count: int = 0

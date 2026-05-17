from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ApprovalStatus


class AgentSessionCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class AgentSessionRead(BaseModel):
    id: int
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1)


class AgentMessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    event_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentMessageCreateResponse(BaseModel):
    user_message: AgentMessageRead
    assistant_message: AgentMessageRead


class ApprovalCreate(BaseModel):
    episode_id: int = Field(gt=0)
    estimated_cost: str | None = Field(default=None, max_length=120)
    estimated_duration_seconds: int | None = Field(default=None, ge=0)
    output_location: str | None = Field(default=None, max_length=300)
    expires_in_seconds: int = Field(default=300, ge=0, le=86_400)


class ApprovalRead(BaseModel):
    id: int
    session_id: int
    action: str
    episode_id: int
    status: ApprovalStatus
    estimated_cost: str | None
    estimated_duration_seconds: int | None
    output_location: str | None
    render_job_id: str | None
    reason: str | None
    decided_by: str | None
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


class ApprovalDecisionRequest(BaseModel):
    decided_by: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=400)


class CreateRenderJobRequest(BaseModel):
    approval_id: int = Field(gt=0)
    episode_id: int = Field(gt=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)


class RenderJobCreateResponse(BaseModel):
    id: str
    episode_id: str
    status: str
    approval_id: int

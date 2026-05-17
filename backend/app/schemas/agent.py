from datetime import datetime

from pydantic import BaseModel, Field


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

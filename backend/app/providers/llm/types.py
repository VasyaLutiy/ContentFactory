from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


LLMProviderName = Literal["openai", "azure_openai", "gemini_compat", "custom_openai_compat"]
LLMResponseMode = Literal["native_tool_calling", "structured_json_proposals", "advisor_only"]
LLMRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class LLMCapabilities:
    supports_tools: bool
    supports_vision: bool
    supports_structured_output: bool
    supports_reasoning_controls: bool = False
    supports_streaming: bool = True

    def response_mode(self) -> LLMResponseMode:
        if self.supports_tools:
            return "native_tool_calling"
        if self.supports_structured_output:
            return "structured_json_proposals"
        return "advisor_only"


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str
    name: str | None = None


@dataclass(frozen=True)
class LLMToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class LLMRequest:
    messages: Sequence[LLMMessage]
    model: str | None = None
    max_tokens: int | None = None
    temperature: float = 0.2
    tools: Sequence[LLMToolSpec] = field(default_factory=tuple)
    response_format: Mapping[str, Any] | None = None
    requires_vision: bool = False


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    finish_reason: str | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMStreamEvent:
    type: Literal["delta", "done", "error"]
    text: str = ""
    response: LLMResponse | None = None
    error: str | None = None


class LLMProviderError(RuntimeError):
    pass


class LLMProviderTimeout(LLMProviderError):
    pass


class LLMProvider(Protocol):
    name: LLMProviderName
    capabilities: LLMCapabilities

    async def create_response(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    def stream_response(self, request: LLMRequest) -> AsyncIterator[LLMStreamEvent]:
        raise NotImplementedError

    async def createResponse(self, request: LLMRequest) -> LLMResponse:  # noqa: N802
        raise NotImplementedError

    def streamResponse(self, request: LLMRequest) -> AsyncIterator[LLMStreamEvent]:  # noqa: N802
        raise NotImplementedError

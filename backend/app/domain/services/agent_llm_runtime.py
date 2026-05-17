from __future__ import annotations

from dataclasses import dataclass
import logging
from time import perf_counter

from app.domain.services.agent_prompt_registry import (
    AgentPromptRegistry,
    PromptAssemblyInput,
    PromptFallbackMode,
)
from app.domain.services.agent_tool_registry import AgentToolRegistry
from app.providers.llm.types import LLMProvider, LLMProviderError, LLMProviderTimeout, LLMRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentLLMRuntimeResult:
    assistant_text: str
    prompt_fingerprint: str
    fallback_mode: PromptFallbackMode
    tool_names: tuple[str, ...]


@dataclass(frozen=True)
class AgentRuntimeError(RuntimeError):
    code: str
    message: str
    details: dict[str, object]

    def __str__(self) -> str:
        return self.message


class AgentLLMRuntime:
    def __init__(
        self,
        *,
        prompt_registry: AgentPromptRegistry,
        tool_registry: AgentToolRegistry,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_registry = prompt_registry
        self._tool_registry = tool_registry
        self._llm_provider = llm_provider

    async def respond(
        self,
        *,
        profile_key: str,
        user_message: str,
        project_rules: tuple[str, ...] = (),
        experiment_objective: str | None = None,
        runtime_context: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.2,
        session_id: int | None = None,
        message_id: int | None = None,
    ) -> AgentLLMRuntimeResult:
        started = perf_counter()
        assembly_input = PromptAssemblyInput(
            profile_key=profile_key,
            project_rules=project_rules,
            experiment_objective=experiment_objective,
            runtime_context=runtime_context,
            user_message=user_message,
            capabilities=self._llm_provider.capabilities,
        )
        assembly = self._prompt_registry.assemble(assembly_input)
        tools = (
            self._tool_registry.llm_tool_specs()
            if assembly.fallback_mode == PromptFallbackMode.NATIVE_TOOL_CALLING
            else ()
        )
        try:
            response = await self._llm_provider.create_response(
                LLMRequest(
                    messages=assembly.messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                )
            )
        except LLMProviderTimeout as exc:
            logger.warning(
                "agent_runtime_provider_timeout",
                extra={
                    "session_id": session_id,
                    "message_id": message_id,
                    "provider": self._llm_provider.name,
                    "model": model,
                    "latency_ms": max(0, int((perf_counter() - started) * 1000)),
                    "status": "failed",
                    "error_code": "provider_timeout",
                },
            )
            raise AgentRuntimeError(
                code="provider_timeout",
                message="Advisor unavailable: provider request timed out.",
                details={"provider": self._llm_provider.name},
            ) from exc
        except LLMProviderError as exc:
            logger.warning(
                "agent_runtime_provider_error",
                extra={
                    "session_id": session_id,
                    "message_id": message_id,
                    "provider": self._llm_provider.name,
                    "model": model,
                    "latency_ms": max(0, int((perf_counter() - started) * 1000)),
                    "status": "failed",
                    "error_code": "provider_unavailable",
                },
            )
            raise AgentRuntimeError(
                code="provider_unavailable",
                message="Advisor unavailable: provider request failed.",
                details={"provider": self._llm_provider.name},
            ) from exc
        logger.info(
            "agent_runtime_response",
            extra={
                "session_id": session_id,
                "message_id": message_id,
                "provider": self._llm_provider.name,
                "model": response.model,
                "latency_ms": max(0, int((perf_counter() - started) * 1000)),
                "tokens_prompt": response.usage.get("prompt_tokens"),
                "tokens_completion": response.usage.get("completion_tokens"),
                "estimated_cost": response.usage.get("estimated_cost"),
                "status": "succeeded",
                "error_code": None,
            },
        )
        return AgentLLMRuntimeResult(
            assistant_text=response.text,
            prompt_fingerprint=assembly.deterministic_fingerprint,
            fallback_mode=assembly.fallback_mode,
            tool_names=tuple(tool.name for tool in tools),
        )

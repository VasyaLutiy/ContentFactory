from __future__ import annotations

from dataclasses import dataclass

from app.domain.services.agent_prompt_registry import (
    AgentPromptRegistry,
    PromptAssemblyInput,
    PromptFallbackMode,
)
from app.domain.services.agent_tool_registry import AgentToolRegistry
from app.providers.llm.types import LLMProvider, LLMRequest


@dataclass(frozen=True)
class AgentLLMRuntimeResult:
    assistant_text: str
    prompt_fingerprint: str
    fallback_mode: PromptFallbackMode
    tool_names: tuple[str, ...]


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
    ) -> AgentLLMRuntimeResult:
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
        response = await self._llm_provider.create_response(
            LLMRequest(
                messages=assembly.messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            )
        )
        return AgentLLMRuntimeResult(
            assistant_text=response.text,
            prompt_fingerprint=assembly.deterministic_fingerprint,
            fallback_mode=assembly.fallback_mode,
            tool_names=tuple(tool.name for tool in tools),
        )

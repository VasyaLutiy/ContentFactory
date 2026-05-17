from __future__ import annotations

import pytest

from app.domain.services.agent_llm_runtime import AgentLLMRuntime, AgentRuntimeError
from app.domain.services.agent_prompt_registry import AgentPromptRegistry, PromptFallbackMode
from app.domain.services.agent_tool_registry import build_default_agent_tool_registry
from app.providers.llm.types import LLMCapabilities, LLMProviderTimeout, LLMRequest, LLMResponse


class _RecordingLLMProvider:
    def __init__(self, capabilities: LLMCapabilities) -> None:
        self.name = "openai"
        self.capabilities = capabilities
        self.requests: list[LLMRequest] = []

    async def create_response(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text="done", model=request.model or "test-model")


class _TimeoutLLMProvider:
    def __init__(self) -> None:
        self.name = "openai"
        self.capabilities = LLMCapabilities(True, False, True)

    async def create_response(self, request: LLMRequest) -> LLMResponse:
        raise LLMProviderTimeout("slow")


def test_runtime_attaches_read_only_tool_specs_when_native_tool_calling(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_ARTIFACT_ROOT", str(tmp_path))
    provider = _RecordingLLMProvider(LLMCapabilities(True, False, True))
    runtime = AgentLLMRuntime(
        prompt_registry=AgentPromptRegistry(),
        tool_registry=build_default_agent_tool_registry(),
        llm_provider=provider,
    )

    result = _run(runtime.respond(profile_key="operator", user_message="Inspect artifacts."))

    assert result.assistant_text == "done"
    assert result.fallback_mode == PromptFallbackMode.NATIVE_TOOL_CALLING
    assert set(result.tool_names) == {
        "list_artifacts",
        "inspect_video",
        "extract_keyframes",
        "analyze_tiktok_stats",
        "compare_variants",
    }
    assert [tool.name for tool in provider.requests[0].tools] == list(result.tool_names)


def test_runtime_omits_tools_when_provider_lacks_native_tool_calling(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_ARTIFACT_ROOT", str(tmp_path))
    provider = _RecordingLLMProvider(LLMCapabilities(False, False, True))
    runtime = AgentLLMRuntime(
        prompt_registry=AgentPromptRegistry(),
        tool_registry=build_default_agent_tool_registry(),
        llm_provider=provider,
    )

    result = _run(runtime.respond(profile_key="operator", user_message="Advise."))

    assert result.fallback_mode == PromptFallbackMode.STRUCTURED_JSON_PROPOSALS
    assert result.tool_names == ()
    assert provider.requests[0].tools == ()


def test_runtime_forwards_generation_controls(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_ARTIFACT_ROOT", str(tmp_path))
    provider = _RecordingLLMProvider(LLMCapabilities(True, False, True))
    runtime = AgentLLMRuntime(
        prompt_registry=AgentPromptRegistry(),
        tool_registry=build_default_agent_tool_registry(),
        llm_provider=provider,
    )

    result = _run(
        runtime.respond(
            profile_key="caption_strategist",
            user_message="Draft captions.",
            project_rules=("Cite artifact IDs.",),
            model="test-override",
            max_tokens=333,
            temperature=0.1,
        )
    )

    request = provider.requests[0]
    assert result.prompt_fingerprint
    assert request.model == "test-override"
    assert request.max_tokens == 333
    assert request.temperature == 0.1
    assert request.messages[-1].content == "Draft captions."


def test_runtime_normalizes_provider_timeouts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_ARTIFACT_ROOT", str(tmp_path))
    runtime = AgentLLMRuntime(
        prompt_registry=AgentPromptRegistry(),
        tool_registry=build_default_agent_tool_registry(),
        llm_provider=_TimeoutLLMProvider(),
    )

    with pytest.raises(AgentRuntimeError, match="timed out") as exc:
        _run(runtime.respond(profile_key="operator", user_message="Inspect artifacts."))

    assert exc.value.code == "provider_timeout"


def _run(coro):
    import asyncio

    return asyncio.run(coro)

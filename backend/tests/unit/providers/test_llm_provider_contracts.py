from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from app.core.config import get_settings
from app.providers.llm import (
    LLMCapabilities,
    LLMMessage,
    LLMProviderError,
    LLMProviderTimeout,
    LLMRequest,
    LLMToolSpec,
    OpenAICompatibleProvider,
    OpenAICompatibleTransport,
    build_llm_provider,
)


class RecordingTransport(OpenAICompatibleTransport):
    def __init__(
        self,
        response: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or {
            "model": "compat-model",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 12},
        }
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def create_chat_completion(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error:
            raise self.error
        return self.response


def test_llm_settings_parse_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_API_KEY", "secret")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_MODEL", "model-a")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_REASONING_MODEL", "model-r")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_VISION_MODEL", "model-v")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_TOKEN_BUDGET", "8192")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_TOOLS", "true")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_VISION", "yes")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_STRUCTURED_OUTPUT", "0")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.llm_provider == "openai"
    assert settings.llm_base_url == "https://example.invalid/v1"
    assert settings.llm_api_key == "secret"
    assert settings.llm_model == "model-a"
    assert settings.llm_reasoning_model == "model-r"
    assert settings.llm_vision_model == "model-v"
    assert settings.llm_timeout_seconds == 7.5
    assert settings.llm_token_budget == 8192
    assert settings.llm_supports_tools is True
    assert settings.llm_supports_vision is True
    assert settings.llm_supports_structured_output is False

    get_settings.cache_clear()


def test_llm_settings_default_openai_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONTENT_FACTORY_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("CONTENT_FACTORY_LLM_BASE_URL", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.llm_provider == "openai"
    assert settings.llm_base_url == "https://api.openai.com/v1"

    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("capabilities", "mode"),
    [
        (LLMCapabilities(True, False, False), "native_tool_calling"),
        (LLMCapabilities(False, False, True), "structured_json_proposals"),
        (LLMCapabilities(False, True, False), "advisor_only"),
    ],
)
def test_capabilities_select_safe_response_mode(
    capabilities: LLMCapabilities,
    mode: str,
) -> None:
    assert capabilities.response_mode() == mode


def test_openai_compatible_provider_builds_payload_without_frontend_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_API_KEY", "server-only")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_MODEL", "agent-model")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_TOOLS", "true")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_STRUCTURED_OUTPUT", "true")
    get_settings.cache_clear()
    transport = RecordingTransport()
    provider = OpenAICompatibleProvider(
        name="custom_openai_compat",
        settings=get_settings(),
        transport=transport,
    )

    response = asyncio.run(
        provider.create_response(
            LLMRequest(
                messages=[LLMMessage(role="user", content="Inspect job 1")],
                tools=[
                    LLMToolSpec(
                        name="list_artifacts",
                        description="List artifacts",
                        input_schema={"type": "object", "properties": {}},
                    )
                ],
                response_format={"type": "json_object"},
            )
        )
    )

    call = transport.calls[0]
    assert call["base_url"] == "https://llm.invalid/v1"
    assert call["api_key"] == "server-only"
    assert call["payload"]["model"] == "agent-model"
    assert call["payload"]["tools"][0]["function"]["name"] == "list_artifacts"
    assert call["payload"]["response_format"] == {"type": "json_object"}
    assert response.text == "ok"
    assert response.usage == {"total_tokens": 12}
    get_settings.cache_clear()


def test_build_provider_can_execute_with_injected_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_MODEL", "factory-model")
    get_settings.cache_clear()
    transport = RecordingTransport()

    provider = build_llm_provider(transport=transport)
    response = asyncio.run(
        provider.createResponse(LLMRequest(messages=[LLMMessage(role="user", content="ping")]))
    )

    assert response.text == "ok"
    assert transport.calls[0]["payload"]["model"] == "factory-model"
    assert transport.calls[0]["base_url"] == "https://api.openai.com/v1"
    get_settings.cache_clear()


def test_openai_compatible_provider_routes_vision_requests_to_vision_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_MODEL", "text-model")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_VISION_MODEL", "vision-model")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_ENABLE_VISION", "true")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_VISION", "true")
    get_settings.cache_clear()
    transport = RecordingTransport()
    provider = OpenAICompatibleProvider(
        name="custom_openai_compat",
        settings=get_settings(),
        transport=transport,
    )

    asyncio.run(
        provider.create_response(
            LLMRequest(
                messages=[LLMMessage(role="user", content="Inspect frame")],
                requires_vision=True,
            )
        )
    )

    assert transport.calls[0]["payload"]["model"] == "vision-model"
    assert provider.capabilities.supports_vision is True
    get_settings.cache_clear()


def test_openai_compatible_provider_rejects_vision_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_LLM_ENABLE_VISION", "false")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_VISION", "true")
    get_settings.cache_clear()
    provider = OpenAICompatibleProvider(
        name="custom_openai_compat",
        settings=get_settings(),
        transport=RecordingTransport(),
    )

    with pytest.raises(LLMProviderError, match="does not support vision"):
        asyncio.run(
            provider.create_response(
                LLMRequest(
                    messages=[LLMMessage(role="user", content="Inspect frame")],
                    requires_vision=True,
                )
            )
        )

    get_settings.cache_clear()


def test_openai_compatible_provider_normalizes_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    provider = OpenAICompatibleProvider(
        name="custom_openai_compat",
        settings=get_settings(),
        transport=RecordingTransport(error=TimeoutError("slow")),
    )

    with pytest.raises(LLMProviderTimeout, match="timed out"):
        asyncio.run(
            provider.create_response(LLMRequest(messages=[LLMMessage(role="user", content="hi")]))
        )

    get_settings.cache_clear()


def test_openai_compatible_provider_normalizes_generic_errors() -> None:
    provider = OpenAICompatibleProvider(
        name="custom_openai_compat",
        settings=get_settings(),
        transport=RecordingTransport(error=RuntimeError("boom")),
    )

    with pytest.raises(LLMProviderError, match="boom"):
        asyncio.run(
            provider.create_response(LLMRequest(messages=[LLMMessage(role="user", content="hi")]))
        )


def test_build_provider_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTENT_FACTORY_LLM_PROVIDER", "raw_shell_agent")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        build_llm_provider()

    get_settings.cache_clear()

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
import json
import logging
from typing import Any
from urllib import error, request

from app.core.config import Settings
from app.providers.llm.types import (
    LLMCapabilities,
    LLMMessage,
    LLMProviderError,
    LLMProviderName,
    LLMProviderTimeout,
    LLMRequest,
    LLMResponse,
    LLMStreamEvent,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleTransport:
    async def create_chat_completion(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        raise NotImplementedError("LLM transport is not configured.")


class UrlLibOpenAICompatibleTransport(OpenAICompatibleTransport):
    async def create_chat_completion(
        self,
        *,
        base_url: str | None,
        api_key: str | None,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        if not base_url:
            raise LLMProviderError("LLM base URL is required for this provider.")
        return await asyncio.to_thread(
            self._create_chat_completion,
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _create_chat_completion(
        *,
        base_url: str,
        api_key: str | None,
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except TimeoutError:
            raise
        except error.URLError as exc:
            raise LLMProviderError(f"LLM provider HTTP request failed: {exc}") from exc
        parsed = json.loads(raw)
        if not isinstance(parsed, Mapping):
            raise LLMProviderError("LLM provider returned a non-object response.")
        return parsed


class OpenAICompatibleProvider:
    _MAX_RETRIES = 1
    _RETRY_BACKOFF_SECONDS = 0.2

    def __init__(
        self,
        *,
        name: LLMProviderName,
        settings: Settings,
        transport: OpenAICompatibleTransport | None = None,
    ) -> None:
        self.name = name
        self._settings = settings
        self._transport = transport or UrlLibOpenAICompatibleTransport()
        self.capabilities = LLMCapabilities(
            supports_tools=settings.llm_supports_tools,
            supports_vision=settings.llm_supports_vision and settings.llm_enable_vision,
            supports_structured_output=settings.llm_supports_structured_output,
            supports_reasoning_controls=settings.llm_reasoning_level is not None,
        )

    async def create_response(self, request: LLMRequest) -> LLMResponse:
        if request.requires_vision and not self.capabilities.supports_vision:
            raise LLMProviderError("LLM provider does not support vision requests.")
        payload = self._payload(request)
        raw: Mapping[str, Any] | None = None
        last_error: Exception | None = None
        retry_count = 0
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                raw = await self._transport.create_chat_completion(
                    base_url=self._settings.llm_base_url,
                    api_key=self._settings.llm_api_key,
                    payload=payload,
                    timeout_seconds=self._settings.llm_timeout_seconds,
                )
                retry_count = attempt
                break
            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt < self._MAX_RETRIES:
                    await asyncio.sleep(self._RETRY_BACKOFF_SECONDS)
                    continue
                logger.warning(
                    "llm_provider_timeout",
                    extra={
                        "provider": self.name,
                        "model": payload.get("model"),
                        "timeout_seconds": self._settings.llm_timeout_seconds,
                        "retry_count": attempt,
                        "status": "failed",
                        "error_code": "provider_timeout",
                    },
                )
                raise LLMProviderTimeout("LLM provider request timed out.") from exc
            except LLMProviderError as exc:
                last_error = exc
                logger.warning(
                    "llm_provider_error",
                    extra={
                        "provider": self.name,
                        "model": payload.get("model"),
                        "timeout_seconds": self._settings.llm_timeout_seconds,
                        "retry_count": attempt,
                        "status": "failed",
                        "error_code": "provider_error",
                    },
                )
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm_provider_error",
                    extra={
                        "provider": self.name,
                        "model": payload.get("model"),
                        "timeout_seconds": self._settings.llm_timeout_seconds,
                        "retry_count": attempt,
                        "status": "failed",
                        "error_code": "provider_error",
                    },
                )
                raise LLMProviderError(f"LLM provider request failed: {exc}") from exc

        if raw is None:
            if isinstance(last_error, (TimeoutError, asyncio.TimeoutError)):
                raise LLMProviderTimeout("LLM provider request timed out.") from last_error
            raise LLMProviderError("LLM provider request failed.")
        response = self._response(raw, model=str(payload["model"]))
        logger.info(
            "llm_provider_response",
            extra={
                "provider": self.name,
                "model": response.model,
                "timeout_seconds": self._settings.llm_timeout_seconds,
                "retry_count": retry_count,
                "tokens_prompt": response.usage.get("prompt_tokens"),
                "tokens_completion": response.usage.get("completion_tokens"),
                "estimated_cost": response.usage.get("estimated_cost"),
                "status": "succeeded",
                "error_code": None,
            },
        )
        return response

    async def createResponse(self, request: LLMRequest) -> LLMResponse:  # noqa: N802
        return await self.create_response(request)

    async def stream_response(self, request: LLMRequest) -> AsyncIterator[LLMStreamEvent]:
        response = await self.create_response(request)
        if response.text:
            yield LLMStreamEvent(type="delta", text=response.text)
        yield LLMStreamEvent(type="done", response=response)

    async def streamResponse(  # noqa: N802
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamEvent]:
        async for event in self.stream_response(request):
            yield event

    def _payload(self, request: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model_for(request),
            "messages": [self._message(message) for message in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or self._settings.llm_token_budget,
        }
        if self.capabilities.supports_reasoning_controls and self._settings.llm_reasoning_level:
            payload["reasoning"] = {"effort": self._settings.llm_reasoning_level}
        if request.tools and self.capabilities.supports_tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": dict(tool.input_schema),
                    },
                }
                for tool in request.tools
            ]
        if request.response_format and self.capabilities.supports_structured_output:
            payload["response_format"] = dict(request.response_format)
        return payload

    def _model_for(self, request: LLMRequest) -> str:
        if request.model:
            return request.model
        if request.requires_vision and self._settings.llm_vision_model:
            return self._settings.llm_vision_model
        if self._settings.llm_reasoning_level and self._settings.llm_reasoning_model:
            return self._settings.llm_reasoning_model
        return self._settings.llm_model

    @staticmethod
    def _message(message: LLMMessage) -> dict[str, str]:
        payload = {"role": message.role, "content": message.content}
        if message.name:
            payload["name"] = message.name
        return payload

    @staticmethod
    def _response(raw: Mapping[str, Any], *, model: str) -> LLMResponse:
        choices = raw.get("choices") or []
        first = choices[0] if choices else {}
        message = first.get("message") or {}
        content = message.get("content") or first.get("text") or ""
        return LLMResponse(
            text=str(content),
            model=str(raw.get("model") or model),
            finish_reason=first.get("finish_reason"),
            usage=raw.get("usage") or {},
            raw=raw,
        )

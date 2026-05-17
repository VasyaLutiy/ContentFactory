from __future__ import annotations

from app.core.config import Settings, get_settings
from app.providers.llm.openai_compatible import OpenAICompatibleProvider, OpenAICompatibleTransport
from app.providers.llm.types import LLMProvider, LLMProviderName


SUPPORTED_PROVIDERS: set[str] = {
    "openai",
    "azure_openai",
    "gemini_compat",
    "custom_openai_compat",
}


def build_llm_provider(
    settings: Settings | None = None,
    *,
    transport: OpenAICompatibleTransport | None = None,
) -> LLMProvider:
    resolved = settings or get_settings()
    if resolved.llm_provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(
            f"Unsupported LLM provider {resolved.llm_provider!r}. Use one of: {supported}."
        )
    return OpenAICompatibleProvider(
        name=resolved.llm_provider,  # type: ignore[arg-type]
        settings=resolved,
        transport=transport,
    )


def normalize_provider_name(name: str) -> LLMProviderName:
    if name not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(f"Unsupported LLM provider {name!r}. Use one of: {supported}.")
    return name  # type: ignore[return-value]

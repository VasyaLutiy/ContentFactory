from app.core.config import get_settings


def test_reads_llm_settings_from_environment(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("CONTENT_FACTORY_LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("CONTENT_FACTORY_REDIS_URL", "redis://localhost:6379/2")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_BASE_URL", "https://azure.example.test")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_API_KEY", "secret")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_REASONING_LEVEL", "low")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_ENABLE_VISION", "1")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_RETRY_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_RETRY_BACKOFF_SECONDS", "0.3")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_RETRY_BACKOFF_MULTIPLIER", "2.5")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_RETRY_BACKOFF_MAX_SECONDS", "3.5")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_TOKEN_BUDGET", "2222")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_TOOLS", "false")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_VISION", "true")
    monkeypatch.setenv("CONTENT_FACTORY_LLM_SUPPORTS_STRUCTURED_OUTPUT", "true")
    monkeypatch.setenv("CONTENT_FACTORY_LOG_LEVEL", "warning")
    monkeypatch.setenv("CONTENT_FACTORY_LOG_JSON", "false")

    settings = get_settings()

    assert settings.redis_url == "redis://localhost:6379/2"
    assert settings.llm_provider == "azure_openai"
    assert settings.llm_base_url == "https://azure.example.test"
    assert settings.llm_api_key == "secret"
    assert settings.llm_model == "gpt-4.1"
    assert settings.llm_reasoning_level == "low"
    assert settings.llm_enable_vision is True
    assert settings.llm_timeout_seconds == 12.5
    assert settings.llm_retry_max_attempts == 3
    assert settings.llm_retry_backoff_seconds == 0.3
    assert settings.llm_retry_backoff_multiplier == 2.5
    assert settings.llm_retry_backoff_max_seconds == 3.5
    assert settings.llm_token_budget == 2222
    assert settings.llm_supports_tools is False
    assert settings.llm_supports_vision is True
    assert settings.llm_supports_structured_output is True
    assert settings.log_level == "WARNING"
    assert settings.log_json is False

    get_settings.cache_clear()

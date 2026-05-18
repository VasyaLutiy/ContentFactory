import io
import json
import logging

from app.core.config import Settings
from app.core.logging import JsonFormatter, configure_logging


def test_json_formatter_includes_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="content_factory.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="provider_response",
        args=(),
        exc_info=None,
    )
    setattr(record, "provider", "openai")
    setattr(record, "retry_count", 1)

    raw = formatter.format(record)
    payload = json.loads(raw)

    assert payload["message"] == "provider_response"
    assert payload["provider"] == "openai"
    assert payload["retry_count"] == 1
    assert payload["level"] == "INFO"
    assert payload["logger"] == "content_factory.test"


def test_configure_logging_replaces_previous_formatter(tmp_path) -> None:
    settings = Settings(
        project_root=tmp_path,
        legacy_content_root=tmp_path,
        artifact_root=tmp_path / "artifacts",
        comfy_url="http://localhost:8188",
        enable_docs=True,
        database_url="sqlite+pysqlite:///:memory:",
        redis_url=None,
        llm_provider="openai",
        llm_base_url="https://api.openai.com/v1",
        llm_api_key=None,
        llm_model="gpt-4o-mini",
        llm_reasoning_model=None,
        llm_vision_model=None,
        llm_reasoning_level=None,
        llm_enable_vision=False,
        llm_timeout_seconds=60.0,
        llm_retry_max_attempts=1,
        llm_retry_backoff_seconds=0.2,
        llm_retry_backoff_multiplier=2.0,
        llm_retry_backoff_max_seconds=2.0,
        llm_token_budget=4096,
        llm_supports_tools=True,
        llm_supports_vision=False,
        llm_supports_structured_output=True,
        log_level="INFO",
        log_json=True,
    )

    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        configure_logging(settings)
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

        plain_settings = Settings(**{**settings.__dict__, "log_json": False})
        configure_logging(plain_settings)
        assert not isinstance(root.handlers[0].formatter, JsonFormatter)

        stream = io.StringIO()
        root.handlers[0].stream = stream
        logging.getLogger("content_factory.test").info("plain_message")
        assert "plain_message" in stream.getvalue()
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)

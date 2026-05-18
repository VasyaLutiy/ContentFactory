from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _default_llm_base_url(provider: str) -> str | None:
    if provider == "openai":
        return "https://api.openai.com/v1"
    return None


@dataclass(frozen=True)
class Settings:
    project_root: Path
    legacy_content_root: Path
    artifact_root: Path
    comfy_url: str
    enable_docs: bool
    database_url: str
    redis_url: str | None
    llm_provider: str
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str
    llm_reasoning_model: str | None
    llm_vision_model: str | None
    llm_reasoning_level: str | None
    llm_enable_vision: bool
    llm_timeout_seconds: float
    llm_retry_max_attempts: int
    llm_retry_backoff_seconds: float
    llm_retry_backoff_multiplier: float
    llm_retry_backoff_max_seconds: float
    llm_token_budget: int
    llm_supports_tools: bool
    llm_supports_vision: bool
    llm_supports_structured_output: bool
    log_level: str
    log_json: bool


@lru_cache
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    legacy_content_root = Path(os.getenv("CONTENT_FACTORY_LEGACY_ROOT", project_root.parent))
    artifact_root = Path(
        os.getenv("CONTENT_FACTORY_ARTIFACT_ROOT", project_root / "var" / "artifacts")
    )
    llm_provider = os.getenv("CONTENT_FACTORY_LLM_PROVIDER", "openai")
    return Settings(
        project_root=project_root,
        legacy_content_root=legacy_content_root,
        artifact_root=artifact_root,
        comfy_url=os.getenv("CONTENT_FACTORY_COMFY_URL", "http://localhost:8188"),
        enable_docs=_bool_env("CONTENT_FACTORY_ENABLE_DOCS", True),
        database_url=os.getenv("CONTENT_FACTORY_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        redis_url=os.getenv("CONTENT_FACTORY_REDIS_URL"),
        llm_provider=llm_provider,
        llm_base_url=os.getenv(
            "CONTENT_FACTORY_LLM_BASE_URL",
            _default_llm_base_url(llm_provider),
        ),
        llm_api_key=os.getenv("CONTENT_FACTORY_LLM_API_KEY"),
        llm_model=os.getenv("CONTENT_FACTORY_LLM_MODEL", "gpt-4o-mini"),
        llm_reasoning_model=os.getenv("CONTENT_FACTORY_LLM_REASONING_MODEL"),
        llm_vision_model=os.getenv("CONTENT_FACTORY_LLM_VISION_MODEL"),
        llm_reasoning_level=os.getenv("CONTENT_FACTORY_LLM_REASONING_LEVEL"),
        llm_enable_vision=_bool_env("CONTENT_FACTORY_LLM_ENABLE_VISION", False),
        llm_timeout_seconds=_float_env("CONTENT_FACTORY_LLM_TIMEOUT_SECONDS", 60.0),
        llm_retry_max_attempts=_int_env("CONTENT_FACTORY_LLM_RETRY_MAX_ATTEMPTS", 1),
        llm_retry_backoff_seconds=_float_env("CONTENT_FACTORY_LLM_RETRY_BACKOFF_SECONDS", 0.2),
        llm_retry_backoff_multiplier=_float_env(
            "CONTENT_FACTORY_LLM_RETRY_BACKOFF_MULTIPLIER", 2.0
        ),
        llm_retry_backoff_max_seconds=_float_env(
            "CONTENT_FACTORY_LLM_RETRY_BACKOFF_MAX_SECONDS", 2.0
        ),
        llm_token_budget=_int_env("CONTENT_FACTORY_LLM_TOKEN_BUDGET", 4096),
        llm_supports_tools=_bool_env("CONTENT_FACTORY_LLM_SUPPORTS_TOOLS", True),
        llm_supports_vision=_bool_env("CONTENT_FACTORY_LLM_SUPPORTS_VISION", False),
        llm_supports_structured_output=_bool_env(
            "CONTENT_FACTORY_LLM_SUPPORTS_STRUCTURED_OUTPUT", True
        ),
        log_level=os.getenv("CONTENT_FACTORY_LOG_LEVEL", "INFO").upper(),
        log_json=_bool_env("CONTENT_FACTORY_LOG_JSON", True),
    )

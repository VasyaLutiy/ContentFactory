from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    project_root: Path
    legacy_content_root: Path
    artifact_root: Path
    comfy_url: str
    enable_docs: bool
    database_url: str


@lru_cache
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    legacy_content_root = Path(os.getenv("CONTENT_FACTORY_LEGACY_ROOT", project_root.parent))
    artifact_root = Path(
        os.getenv("CONTENT_FACTORY_ARTIFACT_ROOT", project_root / "var" / "artifacts")
    )
    return Settings(
        project_root=project_root,
        legacy_content_root=legacy_content_root,
        artifact_root=artifact_root,
        comfy_url=os.getenv("CONTENT_FACTORY_COMFY_URL", "http://localhost:8188"),
        enable_docs=_bool_env("CONTENT_FACTORY_ENABLE_DOCS", True),
        database_url=os.getenv("CONTENT_FACTORY_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
    )

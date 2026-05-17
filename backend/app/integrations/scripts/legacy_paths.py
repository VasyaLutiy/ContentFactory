from pathlib import Path

from app.core.config import get_settings


def legacy_script_path(name: str) -> Path:
    path = get_settings().legacy_content_root / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path

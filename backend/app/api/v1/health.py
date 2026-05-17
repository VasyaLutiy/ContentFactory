from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "content-factory",
        "artifact_root": str(settings.artifact_root),
        "legacy_content_root": str(settings.legacy_content_root),
        "comfy_url": settings.comfy_url,
    }

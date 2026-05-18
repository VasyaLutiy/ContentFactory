from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

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


@router.get("/ready")
def readiness() -> dict[str, object]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready",
        ) from exc
    return {
        "status": "ready",
        "service": "content-factory",
        "database": "ok",
    }

from fastapi import APIRouter

from app.api.v1 import episodes, health

api_router = APIRouter()
api_router.include_router(episodes.router, prefix="/episodes", tags=["episodes"])
api_router.include_router(health.router, prefix="/health", tags=["health"])

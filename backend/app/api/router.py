from fastapi import APIRouter

from app.api.v1 import campaigns, characters, episodes, episodes_crud, health, scenes, text_beats, voice_lines

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(episodes.router, prefix="/episodes", tags=["episodes-validation"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(characters.router, prefix="/characters", tags=["characters"])
api_router.include_router(episodes_crud.router, prefix="/episode-items", tags=["episodes"])
api_router.include_router(scenes.router, prefix="/scenes", tags=["scenes"])
api_router.include_router(voice_lines.router, prefix="/voice-lines", tags=["voice-lines"])
api_router.include_router(text_beats.router, prefix="/text-beats", tags=["text-beats"])

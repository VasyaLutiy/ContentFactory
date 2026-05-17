from fastapi import APIRouter

from app.domain.services.narrative_validator import validate_text_beats
from app.schemas.episode import TextBeatValidationRequest, TextBeatValidationResult

router = APIRouter()


@router.post("/validate-text-beats", response_model=TextBeatValidationResult)
def validate_episode_text_beats(
    request: TextBeatValidationRequest,
) -> TextBeatValidationResult:
    return validate_text_beats(
        request.beats,
        no_text_experiment=request.no_text_experiment,
    )

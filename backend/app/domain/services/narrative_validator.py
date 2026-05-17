from app.schemas.episode import (
    OnScreenTextBeat,
    TextBeatValidationIssue,
    TextBeatValidationResult,
)

HOOK_TEXT_DEADLINE_SECONDS = 0.3


def validate_text_beats(
    beats: list[OnScreenTextBeat],
    *,
    no_text_experiment: bool = False,
) -> TextBeatValidationResult:
    issues: list[TextBeatValidationIssue] = []

    if no_text_experiment:
        return TextBeatValidationResult(valid=True, issues=[])

    if not beats:
        issues.append(
            TextBeatValidationIssue(
                code="VALIDATION_NO_TEXT_BEATS",
                message="TikTok export requires at least one burned-in text beat.",
            )
        )
        return TextBeatValidationResult(valid=False, issues=issues)

    has_hook = any(beat.start <= HOOK_TEXT_DEADLINE_SECONDS for beat in beats)
    if not has_hook:
        issues.append(
            TextBeatValidationIssue(
                code="VALIDATION_NO_HOOK_TEXT",
                message="TikTok export requires hook text starting at or before 0.3s.",
            )
        )

    for beat in beats:
        if beat.end <= beat.start:
            issues.append(
                TextBeatValidationIssue(
                    code="VALIDATION_INVALID_TEXT_BEAT_TIME",
                    message="Text beat end must be greater than start.",
                    beat_id=beat.id,
                )
            )

        area = beat.safe_area
        if area.x + area.width > 1.0 or area.y + area.height > 1.0:
            issues.append(
                TextBeatValidationIssue(
                    code="VALIDATION_TEXT_OUTSIDE_SAFE_AREA",
                    message="Text beat safe area must stay inside the normalized video frame.",
                    beat_id=beat.id,
                )
            )

    return TextBeatValidationResult(valid=not issues, issues=issues)

from app.domain.services.narrative_validator import validate_text_beats
from app.schemas.episode import OnScreenTextBeat, SafeArea


def test_requires_first_hook_text_before_deadline() -> None:
    result = validate_text_beats(
        [OnScreenTextBeat(start=0.5, end=2.0, text="Too late")]
    )

    assert not result.valid
    assert result.issues[0].code == "VALIDATION_NO_HOOK_TEXT"


def test_accepts_hook_text_at_deadline() -> None:
    result = validate_text_beats(
        [OnScreenTextBeat(start=0.3, end=2.0, text="This machine reincarnates souls.")]
    )

    assert result.valid


def test_no_text_experiment_bypasses_hook_requirement() -> None:
    result = validate_text_beats([], no_text_experiment=True)

    assert result.valid


def test_rejects_text_outside_safe_area() -> None:
    result = validate_text_beats(
        [
            OnScreenTextBeat(
                start=0.0,
                end=2.0,
                text="Hook",
                safe_area=SafeArea(x=0.8, y=0.1, width=0.3, height=0.2),
            )
        ]
    )

    assert not result.valid
    assert any(issue.code == "VALIDATION_TEXT_OUTSIDE_SAFE_AREA" for issue in result.issues)

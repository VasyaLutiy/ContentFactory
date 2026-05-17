import pytest

from app.domain.services.render_state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidRenderJobTransition,
    can_cancel,
    can_retry,
    transition_status,
)
from app.schemas.common import RenderJobStatus


@pytest.mark.parametrize("current,allowed_targets", ALLOWED_TRANSITIONS.items())
def test_allowed_transitions_matrix(current, allowed_targets) -> None:
    for target in allowed_targets:
        assert transition_status(current, target) == target


def test_invalid_transition_raises_with_clear_message() -> None:
    with pytest.raises(InvalidRenderJobTransition) as exc_info:
        transition_status(RenderJobStatus.SUCCEEDED, RenderJobStatus.RUNNING)

    assert "succeeded -> running" in str(exc_info.value)


@pytest.mark.parametrize(
    "status,expected",
    [
        (RenderJobStatus.QUEUED, False),
        (RenderJobStatus.RUNNING, False),
        (RenderJobStatus.SUCCEEDED, False),
        (RenderJobStatus.FAILED, True),
        (RenderJobStatus.CANCELED, False),
    ],
)
def test_can_retry_only_for_failed_jobs(status, expected) -> None:
    assert can_retry(status) is expected


@pytest.mark.parametrize(
    "status,expected",
    [
        (RenderJobStatus.QUEUED, True),
        (RenderJobStatus.RUNNING, True),
        (RenderJobStatus.SUCCEEDED, False),
        (RenderJobStatus.FAILED, True),
        (RenderJobStatus.CANCELED, False),
    ],
)
def test_can_cancel_for_active_or_failed_jobs(status, expected) -> None:
    assert can_cancel(status) is expected


def test_retry_then_cancel_flow_stays_within_state_machine_contract() -> None:
    status = transition_status(RenderJobStatus.FAILED, RenderJobStatus.QUEUED)
    status = transition_status(status, RenderJobStatus.RUNNING)
    status = transition_status(status, RenderJobStatus.FAILED)
    status = transition_status(status, RenderJobStatus.CANCELED)

    assert status == RenderJobStatus.CANCELED

import pytest

from app.domain.services.render_state_machine import (
    InvalidRenderJobTransition,
    can_cancel,
    can_retry,
    transition_status,
)
from app.schemas.common import RenderJobStatus


def test_success_path_transitions() -> None:
    status = transition_status(RenderJobStatus.QUEUED, RenderJobStatus.RUNNING)
    status = transition_status(status, RenderJobStatus.SUCCEEDED)

    assert status == RenderJobStatus.SUCCEEDED


def test_failed_job_can_be_requeued_for_retry() -> None:
    assert can_retry(RenderJobStatus.FAILED)
    assert transition_status(RenderJobStatus.FAILED, RenderJobStatus.QUEUED)


def test_completed_job_cannot_be_canceled() -> None:
    assert not can_cancel(RenderJobStatus.SUCCEEDED)

    with pytest.raises(InvalidRenderJobTransition):
        transition_status(RenderJobStatus.SUCCEEDED, RenderJobStatus.CANCELED)

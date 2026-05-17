from app.schemas.common import RenderJobStatus


ALLOWED_TRANSITIONS: dict[RenderJobStatus, set[RenderJobStatus]] = {
    RenderJobStatus.QUEUED: {
        RenderJobStatus.RUNNING,
        RenderJobStatus.CANCELED,
        RenderJobStatus.FAILED,
    },
    RenderJobStatus.RUNNING: {
        RenderJobStatus.SUCCEEDED,
        RenderJobStatus.FAILED,
        RenderJobStatus.CANCELED,
    },
    RenderJobStatus.FAILED: {
        RenderJobStatus.QUEUED,
        RenderJobStatus.CANCELED,
    },
    RenderJobStatus.SUCCEEDED: set(),
    RenderJobStatus.CANCELED: set(),
}


class InvalidRenderJobTransition(ValueError):
    def __init__(self, current: RenderJobStatus, target: RenderJobStatus) -> None:
        super().__init__(f"Invalid render job transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


def assert_transition_allowed(current: RenderJobStatus, target: RenderJobStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidRenderJobTransition(current, target)


def transition_status(current: RenderJobStatus, target: RenderJobStatus) -> RenderJobStatus:
    assert_transition_allowed(current, target)
    return target


def can_retry(status: RenderJobStatus) -> bool:
    return status == RenderJobStatus.FAILED


def can_cancel(status: RenderJobStatus) -> bool:
    return status in {RenderJobStatus.QUEUED, RenderJobStatus.RUNNING, RenderJobStatus.FAILED}

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.schemas.common import RenderJobStatus, RenderStepKind
from app.schemas.render_job import RenderJob, RenderStep


DEFAULT_RENDER_STEPS: tuple[RenderStepKind, ...] = (
    RenderStepKind.VALIDATE,
    RenderStepKind.KEYFRAME,
    RenderStepKind.VIDEO,
    RenderStepKind.VOICE,
    RenderStepKind.OVERLAY,
    RenderStepKind.MUX,
    RenderStepKind.EXPORT,
)


@dataclass
class QueuedRenderJob:
    job: RenderJob
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryRenderQueue:
    def __init__(self) -> None:
        self._lock = Lock()
        self._queue: deque[str] = deque()
        self._jobs: dict[str, QueuedRenderJob] = {}

    def enqueue(self, episode_id: str, steps: tuple[RenderStepKind, ...] = DEFAULT_RENDER_STEPS) -> RenderJob:
        job = RenderJob(
            id=str(uuid4()),
            episode_id=episode_id,
            status=RenderJobStatus.QUEUED,
            steps=[RenderStep(kind=step) for step in steps],
        )
        with self._lock:
            self._jobs[job.id] = QueuedRenderJob(job=job)
            self._queue.append(job.id)
        return job

    def next_job(self) -> RenderJob | None:
        with self._lock:
            if not self._queue:
                return None
            job_id = self._queue.popleft()
            return self._jobs[job_id].job

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            queued = self._jobs.get(job_id)
            return queued.job if queued else None

    def list(self) -> list[RenderJob]:
        with self._lock:
            return [queued.job for queued in self._jobs.values()]


render_queue = InMemoryRenderQueue()

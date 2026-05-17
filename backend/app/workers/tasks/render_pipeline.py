from __future__ import annotations

from datetime import datetime, timezone

from app.domain.services.render_state_machine import transition_status
from app.schemas.common import RenderJobStatus
from app.schemas.render_job import RenderJob, RenderStep


def run_dry_render_pipeline(job: RenderJob) -> RenderJob:
    job.status = transition_status(job.status, RenderJobStatus.RUNNING)
    for step in job.steps:
        _run_dry_step(step)
    job.status = transition_status(job.status, RenderJobStatus.SUCCEEDED)
    return job


def fail_render_job(job: RenderJob, error_code: str, error_details: str) -> RenderJob:
    job.status = transition_status(job.status, RenderJobStatus.FAILED)
    unfinished = next((step for step in job.steps if step.status != RenderJobStatus.SUCCEEDED), None)
    if unfinished is not None:
        unfinished.status = RenderJobStatus.FAILED
        unfinished.finished_at = datetime.now(timezone.utc)
        unfinished.error_code = error_code
        unfinished.error_details = error_details
    return job


def _run_dry_step(step: RenderStep) -> None:
    now = datetime.now(timezone.utc)
    step.status = RenderJobStatus.RUNNING
    step.started_at = now
    step.status = RenderJobStatus.SUCCEEDED
    step.finished_at = datetime.now(timezone.utc)

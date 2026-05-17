from app.schemas.common import RenderJobStatus
from app.workers.queue import render_queue
from app.workers.tasks.render_pipeline import fail_render_job, run_dry_render_pipeline


def test_dry_render_pipeline_marks_all_steps_succeeded() -> None:
    job = render_queue.enqueue("episode-1")

    result = run_dry_render_pipeline(job)

    assert result.status == RenderJobStatus.SUCCEEDED
    assert all(step.status == RenderJobStatus.SUCCEEDED for step in result.steps)
    assert all(step.started_at is not None for step in result.steps)
    assert all(step.finished_at is not None for step in result.steps)


def test_fail_render_job_marks_first_unfinished_step() -> None:
    job = render_queue.enqueue("episode-2")
    job.status = RenderJobStatus.RUNNING

    result = fail_render_job(job, "COMFY_TIMEOUT", "ComfyUI did not finish in time.")

    assert result.status == RenderJobStatus.FAILED
    assert result.steps[0].status == RenderJobStatus.FAILED
    assert result.steps[0].error_code == "COMFY_TIMEOUT"

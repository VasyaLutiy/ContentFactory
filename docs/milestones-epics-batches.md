# Milestones, Epics, Batches

This document is the execution backlog for ContentFactory. GitHub Issues should
mirror these items before implementation starts beyond the initial scaffold.

## Milestone M0: Repo And Workflow Bootstrap

Goal: make the repository reviewable before implementation continues.

Epics:

- E7 Test Harness And Delivery Workflow

Batches:

- B0.1 Repository workflow, labels, issue templates, and GitHub issue backlog.
- B0.2 Initial CI skeleton for backend/frontend checks.

Acceptance:

- Remote is configured.
- Milestones, labels, epics, and batch issues are ready for owner review.
- Implementation issues remain `status:needs-review` until approved.

## Milestone M1: Foundation And Control Plane

Goal: establish a reliable API/control plane with persistence, job state, and
tests before running expensive generation jobs.

Epics:

- E1 Backend Core And Persistence
- E2 Job Queue And Render State
- E7 Test Harness And Delivery Workflow

Batches:

- B1.1 FastAPI config, health checks, dependency boundaries.
- B1.2 SQLAlchemy models and migrations for core domain entities.
- B1.3 CRUD API for Campaign, Character, Episode, Scene, VoiceLine, TextBeat.
- B1.4 RenderJob/RenderStep state machine with retry and cancel semantics.

Acceptance:

- API starts locally.
- Unit tests run without ComfyUI/GPU/TikTok.
- Domain records can be created and queried.
- Render jobs can be enqueued as state records even before real rendering.

## Milestone M2: Render Pipeline Integration

Goal: wrap existing creative scripts as controlled provider adapters without
changing their generation behavior.

Epics:

- E3 Legacy Script And Provider Adapters
- E4 Narrative Overlay And Export Policy
- E2 Job Queue And Render State

Batches:

- B2.1 ComfyUI client, workflow validation, queue/status polling.
- B2.2 Adapter for `expand_ltx_workflow.py` and LTX i2v jobs.
- B2.3 Adapter for `make_short.py` as a pass-through render path.
- B2.4 ElevenLabs and F5-TTS voice provider adapters.
- B2.5 FFmpeg compose provider for mux, overlay, concat, and crossfade.
- B2.6 Artifact registration and lineage for all generated files.

Acceptance:

- One low-cost render job can progress through validate -> keyframe -> video ->
  audio/text -> export under worker control.
- Failed provider steps store clear error details and can be retried safely.

## Milestone M3: Factory UI Vertical Slice

Goal: build a usable UI for creating an episode, validating text beats, and
watching render progress.

Epics:

- E5 Frontend Factory UI
- E4 Narrative Overlay And Export Policy

Batches:

- B3.1 App shell, navigation, dashboard status.
- B3.2 Campaign Lab and Episode Editor CRUD flows.
- B3.3 Storyboard scene list and voice line editor.
- B3.4 Text Beats timeline with safe-area preview.
- B3.5 Render Queue and job details drawer.

Acceptance:

- User can create a campaign and episode from UI.
- User can add scenes and text beats.
- UI calls backend validation and blocks standard TikTok render without hook
  text by `0.3s`.
- Render queue shows status and failure reasons.

## Milestone M4: Analytics And Recommendation Loop

Goal: turn manual TikTok posting into measurable experiment tracking.

Epics:

- E6 Analytics And KPI Insights
- E3 Legacy Script And Provider Adapters

Batches:

- B4.1 TikTok analytics adapter around `tt_analytics.py`.
- B4.2 Snapshot ingestion replacing CSV-only tracking with DB records.
- B4.3 Export-to-video-id attachment flow.
- B4.4 Campaign analytics board and variant comparison.
- B4.5 Recommendation cards using retention and full-watch metrics.

Acceptance:

- User can attach TikTok video ID to an export.
- Scrape job stores snapshots and screenshots as artifacts.
- Dashboard compares variants with and without on-screen text.

## Milestone M5: Production Hardening

Goal: make the workstation setup recoverable, observable, and safer for repeated
production use.

Epics:

- E7 Test Harness And Delivery Workflow
- E2 Job Queue And Render State

Batches:

- B5.1 Structured logs and error taxonomy.
- B5.2 Provider timeout, backoff, and cancellation handling.
- B5.3 Docker Compose for API, worker, Redis, Postgres, frontend.
- B5.4 Backup/export and artifact cleanup policy.
- B5.5 Nightly integration tests for ComfyUI and TikTok CDP.

Acceptance:

- Worker failures are diagnosable.
- Restarting API/worker does not lose job/artifact state.
- Local deployment has a documented start/stop/recovery flow.

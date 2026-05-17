# Architecture Notes

## Decision: Start With Control Plane

The existing system already generates content. The missing production layer is
state, retries, artifact lineage, validation, and observability. The first
implementation phase therefore builds a control plane before replacing script
internals.

## Legacy Integration Rule

Legacy scripts in the parent folder are treated as behavior owners during v1:

- `make_short.py`: one-shot keyframe -> LTX -> audio/text/mux pipeline.
- `expand_ltx_workflow.py`: current LTX workflow expansion.
- `add_elevenlabs_voice.py`: ElevenLabs voice generation and muxing.
- `add_voice.py`: F5-TTS fallback through ComfyUI.
- `tt_analytics.py` and `track_snapshot.py`: TikTok analytics scrape/history.

Adapters may validate inputs, capture logs, and register artifacts. They should
not silently change prompts, model names, volumes, durations, or overlay defaults.

## Required TikTok Text Policy

Standard TikTok exports must include burned-in hook text starting no later than
`0.3s`. A no-text export is valid only when explicitly marked as
`no_text_experiment`.

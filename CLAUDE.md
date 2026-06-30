# Project Guide

## Project Purpose

Auto Translate Video is a Python video dubbing pipeline with a FastAPI backend.
It downloads or accepts a source video, extracts audio, transcribes speech,
waits for a translated transcript, synthesizes target-language narration, mixes
audio with optional background preservation, and exports dubbed media.

## Current Layout

- `backend/` - FastAPI entrypoints and backend orchestration services.
- `frontend/` - Static SPA served by FastAPI at `/`.
- `src/` - Core pipeline modules: download, audio extraction, ASR, TTS, merge, SRT.
- `scripts/` - Utility and batch scripts.
- `tests/` - Unit tests for core modules and backend services.
- `docs/specs/` - Product and architecture specifications.
- `docs/plans/` - Implementation plans.
- `docs/api/` - API documentation.
- `data/examples/` - Example JSON inputs.
- `output/`, `downloads/`, `input/`, `logs/` - Runtime data, ignored by git.

## Common Commands

```bash
python -m pytest tests -v
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
python pipeline_vi.py --url "https://..." --source-lang zh --voice male
python pipeline.py --url "https://..." --source-lang en
python scripts/batch_run_vi.py --excel output/video_link.xlsx --source-lang zh --voice male
```

## Conventions

- Keep root files limited to project config, primary CLI entrypoints, and docs.
- Put reusable pipeline logic in `src/`, not in `scripts/`.
- Put backend orchestration logic in `backend/services/`.
- Keep public translation API under `/api/translate`; do not add `/job` or `/jobs` routes.
- Put one-off or batch utilities in `scripts/`.
- Put example data in `data/examples/`; keep real data in ignored folders.
- Do not commit generated media, logs, caches, `.env`, or output folders.
- Preserve existing CLI compatibility unless the user explicitly asks to remove it.

## Verification

Before reporting backend or structure work as done, run:

```bash
python -m pytest tests -v
python -c "from backend.main import app; print(app.title)"
```

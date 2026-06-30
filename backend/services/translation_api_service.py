from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models.translation import TranslateRequest
from backend.services.pipeline_job_service import (
    PipelineJob,
    PipelineJobService,
    install_pipeline_job_log_handler,
    run_pipeline_with_job_logging,
)


max_workers = int(os.getenv("BACKEND_MAX_WORKERS", "2"))
translation_service = PipelineJobService(
    log_dir=os.getenv("PIPELINE_LOG_DIR", os.path.join("logs", "debug", "jobs"))
)
install_pipeline_job_log_handler(translation_service)
executor = ThreadPoolExecutor(max_workers=max_workers)

app = FastAPI(
    title="Auto Translate Video Backend",
    version="0.2.0",
    description="FastAPI backend that runs video translation/dubbing tasks in the background.",
)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_frontend():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"name": "Auto Translate Video", "docs": "/docs"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "max_workers": max_workers}


@app.post("/api/translate", status_code=202)
def start_translation(payload: TranslateRequest) -> dict:
    return _start_translation_job(payload)


@app.post("/api/translate/upload", status_code=202)
async def start_translation_upload(
    request: Request,
    filename: str = Query(..., min_length=1),
    target_language: Literal["vi", "jp"] = Query(default="vi"),
    source_lang: str = Query(default="zh"),
    asr_provider: Literal["auto", "azure", "whisper"] = Query(default="auto"),
    bgm_mode: Literal["demucs", "duck", "none"] = Query(default="demucs"),
    bg_duck_db: float = Query(default=-12.0),
    target_voice: str = Query(default="male"),
    voice_id: str | None = Query(default=None),
    skip_video: bool = Query(default=False),
    sub_style: Literal["white", "yellow", "red", "cyan", "black", "bold", "neon", "soft"] = Query(default="white"),
    overlay_type: Literal["blur", "default", "solid", "soft", "none"] = Query(default="blur"),
    overlay_x: float | None = Query(default=None, ge=0.0, le=1.0),
    overlay_y: float | None = Query(default=None, ge=0.0, le=1.0),
    overlay_w: float | None = Query(default=None, ge=0.05, le=1.0),
    overlay_h: float | None = Query(default=None, ge=0.03, le=1.0),
    overlay_blur: int | None = Query(default=None, ge=2, le=40),
    output_dir: str | None = Query(default=None),
    resume_dir: str | None = Query(default=None),
) -> dict:
    local_file = await _save_uploaded_video(request, filename)
    payload = TranslateRequest(
        local_file=local_file,
        resume_dir=resume_dir,
        target_language=target_language,
        source_lang=source_lang,
        asr_provider=asr_provider,
        bgm_mode=bgm_mode,
        bg_duck_db=bg_duck_db,
        target_voice=target_voice,
        voice_id=voice_id,
        skip_video=skip_video,
        sub_style=sub_style,
        overlay_type=overlay_type,
        overlay_x=overlay_x,
        overlay_y=overlay_y,
        overlay_w=overlay_w,
        overlay_h=overlay_h,
        overlay_blur=overlay_blur,
        output_dir=output_dir,
    )
    return _start_translation_job(payload)


def _start_translation_job(payload: TranslateRequest) -> dict:
    request = payload.model_dump(exclude_none=True)
    translation = translation_service.create_job(payload.target_language, request)
    executor.submit(
        run_pipeline_with_job_logging,
        translation_service,
        translation.job_id,
        lambda: _run_translation_pipeline(payload),
    )
    return _translation_response(translation)


@app.get("/api/translations")
def list_translations() -> dict:
    return {
        "translations": [
            _translation_response(translation)
            for translation in translation_service.list_jobs()
        ]
    }


@app.get("/api/translate/{translation_id}")
def get_translation_status(translation_id: str, include_logs: bool = False) -> dict:
    translation = translation_service.get_job(translation_id)
    if not translation:
        raise HTTPException(status_code=404, detail="Translation task not found")
    return _translation_response(translation, include_logs=include_logs)


@app.get("/api/translate/{translation_id}/logs")
def get_translation_logs(
    translation_id: str,
    tail: int = Query(default=200, ge=1, le=5000),
    raw: bool = Query(default=False),
) -> dict:
    lines = translation_service.tail_logs(translation_id, tail=tail, raw=raw)
    if lines is None:
        raise HTTPException(status_code=404, detail="Translation task not found")
    return {"translation_id": translation_id, "tail": tail, "raw": raw, "logs": lines}


async def _save_uploaded_video(request: Request, filename: str) -> str:
    # Luu file upload vao input/uploads de pipeline co duong dan local on dinh.
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(filename)).strip("._")
    if not safe_name:
        safe_name = "uploaded_video.mp4"
    upload_dir = os.getenv("INPUT_UPLOAD_DIR", os.path.join("input", "uploads"))
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, f"{os.urandom(4).hex()}_{safe_name}")

    total_bytes = 0
    with open(path, "wb") as f:
        async for chunk in request.stream():
            if not chunk:
                continue
            total_bytes += len(chunk)
            f.write(chunk)

    if total_bytes == 0:
        try:
            os.remove(path)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="File upload bị rỗng. Hãy chọn lại video.")
    return path


def _run_translation_pipeline(payload: TranslateRequest) -> dict:
    if payload.target_language == "jp":
        return _run_jp_pipeline(payload)
    return _run_vi_pipeline(payload)


def _run_vi_pipeline(payload: TranslateRequest) -> dict:
    import config
    from pipeline_vi import _get_default_vi_output_dir, run_pipeline_vi

    target_voice = payload.target_voice.lower()
    voice_id = payload.voice_id
    if not voice_id:
        voice_id = (
            config.VIETNAMESE_VOICEID_FEMALE
            if target_voice == "female"
            else config.VIETNAMESE_VOICEID_MALE
        )
    if not voice_id:
        raise ValueError(
            "Missing LucyLab voice id. Set VIETNAMESE_VOICEID_MALE/FEMALE in .env "
            "or pass voice_id in the request."
        )

    return run_pipeline_vi(
        url=payload.video_url,
        file_path=payload.local_file,
        source_lang=payload.source_lang,
        asr_provider=payload.asr_provider,
        voice_id=voice_id,
        skip_video=payload.skip_video,
        output_dir=payload.output_dir or _get_default_vi_output_dir(),
        resume_dir=payload.resume_dir,
        bg_mode=payload.bgm_mode,
        bg_duck_db=payload.bg_duck_db,
        sub_style=payload.sub_style,
        overlay_type=payload.overlay_type,
        overlay_x=payload.overlay_x,
        overlay_y=payload.overlay_y,
        overlay_w=payload.overlay_w,
        overlay_h=payload.overlay_h,
        overlay_blur=payload.overlay_blur,
    )


def _run_jp_pipeline(payload: TranslateRequest) -> dict:
    import config
    from pipeline import run_pipeline

    voice = payload.target_voice or config.TTS_VOICE
    if voice.lower() in {"male", "female"}:
        voice = config.TTS_VOICE

    return run_pipeline(
        url=payload.video_url,
        file_path=payload.local_file,
        source_lang=payload.source_lang,
        asr_provider=payload.asr_provider,
        voice=voice,
        skip_video=payload.skip_video,
        output_dir=payload.output_dir or config.OUTPUT_DIR,
        resume_dir=payload.resume_dir,
        bg_mode=payload.bgm_mode,
        bg_duck_db=payload.bg_duck_db,
        sub_style=payload.sub_style,
        overlay_type=payload.overlay_type,
        overlay_x=payload.overlay_x,
        overlay_y=payload.overlay_y,
        overlay_w=payload.overlay_w,
        overlay_h=payload.overlay_h,
        overlay_blur=payload.overlay_blur,
    )


def _translation_response(translation: PipelineJob, include_logs: bool = False) -> dict:
    data = translation.to_dict(include_logs=include_logs)
    return {
        "translation_id": translation.job_id,
        "target_language": translation.pipeline,
        "status": translation.status,
        "current_step": translation.current_step,
        "failed_step": translation.failed_step,
        "progress_percent": _progress_percent(translation),
        "work_dir": translation.work_dir,
        "result": translation.result,
        "error": translation.error,
        "traceback": translation.traceback,
        "log_file": translation.log_file,
        "request": translation.request,
        "status_url": f"/api/translate/{translation.job_id}",
        "logs_url": f"/api/translate/{translation.job_id}/logs",
        **({"logs": data["logs"]} if include_logs and "logs" in data else {}),
    }


def _progress_percent(translation: PipelineJob) -> int:
    if translation.status == "queued":
        return 2
    if translation.status == "translate_pending":
        return 45
    if translation.status == "succeeded":
        return 100
    if translation.status == "failed":
        return 100

    step = translation.current_step or ""
    if "STEP 1" in step:
        return 10
    if "Bước 1" in step:
        return 10
    if "STEP 2.5" in step:
        return 22
    if "Bước 2.5" in step:
        return 22
    if "STEP 2" in step:
        return 18
    if "Bước 2" in step:
        return 18
    if "STEP 3" in step:
        return 34
    if "Bước 3" in step:
        return 34
    if "STEP 4" in step:
        return 45
    if "Bước 4" in step:
        return 45
    if "STEP 5" in step:
        return 62
    if "Bước 5" in step:
        return 62
    if "STEP 6" in step:
        return 78
    if "Bước 6" in step:
        return 78
    if "STEP 7" in step:
        return 90
    if "Bước 7" in step:
        return 90
    if "STEP 8" in step:
        return 96
    if "Bước 8" in step:
        return 96
    return 6 if translation.status == "running" else 0

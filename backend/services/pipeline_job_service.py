from __future__ import annotations

import logging
import os
import re
import traceback as traceback_module
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable


_current_job_id: ContextVar[str | None] = ContextVar("current_job_id", default=None)
_STEP_RE = re.compile(r"\bSTEP\s+([0-9]+(?:\.[0-9]+)?[a-z]?)\s*:?\s*(.*)", re.IGNORECASE)

_STEP_LABELS = {
    "1": "Bước 1/8: Lấy video",
    "2": "Bước 2/8: Tách âm thanh",
    "2.5": "Bước 2.5/8: Tách vocal/nhạc nền",
    "3": "Bước 3/8: Bóc băng giọng nói",
    "4": "Bước 4/8: Dịch transcript bằng Gemini",
    "5": "Bước 5/8: Tạo giọng đọc",
    "6": "Bước 6/8: Khớp timeline và mix audio",
    "6a": "Bước 6/8: Làm chậm audio",
    "6b": "Bước 6/8: Khớp timeline",
    "6c": "Bước 6/8: Mix audio",
    "7": "Bước 7/8: Ghép audio vào video",
    "8": "Bước 8/8: Sinh metadata YouTube",
}


def _step_label(step_number: str, fallback: str = "") -> str:
    normalized = step_number.lower()
    if normalized in _STEP_LABELS:
        return _STEP_LABELS[normalized]
    base = normalized.rstrip("abc")
    if base in _STEP_LABELS:
        return _STEP_LABELS[base]
    return f"Bước {step_number}: {fallback}".rstrip(": ")


def friendly_error_message(message: str) -> str:
    """Doi loi ky thuat sang cau tieng Viet de nguoi dung doc nhanh hon."""
    lower = message.lower()
    if (
        "winerror 2" in lower
        or "the system cannot find the file specified" in lower
        or "không tìm thấy ffmpeg" in lower
    ):
        return (
            "Không tìm thấy chương trình cần chạy, thường là FFmpeg. "
            "Hãy cài FFmpeg, thêm vào PATH, rồi chạy lại tác vụ."
        )
    if "ffmpeg is not installed" in lower or "requested merging of multiple formats" in lower:
        return (
            "Không tìm thấy FFmpeg trên máy. Hãy cài FFmpeg, thêm vào PATH, "
            "rồi chạy lại tác vụ."
        )
    if "ffprobe" in lower and ("not found" in lower or "not installed" in lower):
        return "Không tìm thấy FFprobe. Hãy cài FFmpeg đầy đủ rồi chạy lại."
    if "missing lucylab voice id" in lower:
        return (
            "Thiếu mã giọng đọc LucyLab. Hãy điền VIETNAMESE_VOICEID_MALE "
            "hoặc VIETNAMESE_VOICEID_FEMALE trong file .env."
        )
    if "google_api_key" in lower or "google api key" in lower:
        return "Thiếu GOOGLE_API_KEY để Gemini dịch tự động. Hãy thêm key hoặc dùng Gemini web theo file pending."
    if "video file not found" in lower:
        return "Không tìm thấy file video local. Hãy chọn lại file hoặc kiểm tra đường dẫn."
    return message


def _friendly_log_message(level: str, message: str) -> str | None:
    """Chi giu log hien thi quan trong de UI gon va de quan sat."""
    step_match = _STEP_RE.search(message)
    if step_match:
        return _step_label(step_match.group(1), step_match.group(2).strip())

    lower = message.lower()
    if "job queued" in lower:
        return "Đã nhận tác vụ và đưa vào hàng chờ."
    if "bắt đầu xử lý" in lower:
        return "Bắt đầu xử lý tác vụ."
    if "translation pending" in lower or "translate_pending" in lower:
        return "Bước 4/8: Đang chờ file dịch hoặc cấu hình Gemini."
    if level.upper() == "ERROR" and ("job failed" in lower or "failed" in lower):
        raw_error = message.split(":", 1)[-1].strip() if ":" in message else message
        return f"Tác vụ bị lỗi: {friendly_error_message(raw_error)}"
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PipelineJob:
    job_id: str
    pipeline: str
    request: dict[str, Any]
    log_file: str
    status: str = "queued"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    current_step: str | None = None
    failed_step: str | None = None
    work_dir: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    traceback: str | None = None
    logs: list[str] = field(default_factory=list)

    def to_dict(self, include_logs: bool = False) -> dict[str, Any]:
        data = {
            "job_id": self.job_id,
            "pipeline": self.pipeline,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_step": self.current_step,
            "failed_step": self.failed_step,
            "work_dir": self.work_dir,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback,
            "log_file": self.log_file,
            "request": self.request,
        }
        if include_logs:
            data["logs"] = list(self.logs)
        return data


class PipelineJobService:
    def __init__(self, log_dir: str = "logs", max_memory_lines: int = 1000):
        self.log_dir = log_dir
        self.max_memory_lines = max_memory_lines
        self._jobs: dict[str, PipelineJob] = {}
        self._lock = Lock()
        os.makedirs(self.log_dir, exist_ok=True)

    def create_job(self, pipeline: str, request: dict[str, Any]) -> PipelineJob:
        job_id = uuid.uuid4().hex
        log_file = os.path.join(self.log_dir, f"{job_id}.log")
        job = PipelineJob(
            job_id=job_id,
            pipeline=pipeline,
            request=request,
            log_file=log_file,
        )
        with self._lock:
            self._jobs[job_id] = job
        self.append_log(job_id, "INFO", "backend", f"Job queued for pipeline={pipeline}")
        return job

    def get_job(self, job_id: str) -> PipelineJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[PipelineJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def mark_running(self, job_id: str) -> None:
        self._update(job_id, status="running")
        self.append_log(job_id, "INFO", "backend", "Bắt đầu xử lý tác vụ.")

    def mark_translate_pending(self, job_id: str, result: dict[str, Any]) -> None:
        self._update(
            job_id,
            status="translate_pending",
            result=result,
            work_dir=result.get("work_dir"),
            current_step="Bước 4/8: Đang chờ file dịch",
        )

    def mark_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self._update(
            job_id,
            status="succeeded",
            result=result,
            work_dir=result.get("output_dir") or result.get("work_dir"),
            current_step="Hoàn tất",
        )

    def mark_failed(self, job_id: str, exc: BaseException) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.failed_step = job.current_step
            job.error = friendly_error_message(str(exc))
            job.traceback = traceback_module.format_exc()
            job.updated_at = utc_now_iso()
        self.append_log(job_id, "ERROR", "backend", f"Job failed: {exc}")

    def append_log(self, job_id: str, level: str, logger_name: str, message: str) -> None:
        line = f"{utc_now_iso()} [{level}] {logger_name} - {message}"
        step_match = _STEP_RE.search(message)
        friendly_line = _friendly_log_message(level, message)
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if step_match:
                job.current_step = _step_label(step_match.group(1), step_match.group(2).strip())
            if "translation pending" in message.lower() or "translate_pending" in message.lower():
                job.current_step = "Bước 4/8: Đang chờ file dịch"
            if friendly_line and (not job.logs or job.logs[-1] != friendly_line):
                job.logs.append(friendly_line)
                if len(job.logs) > self.max_memory_lines:
                    job.logs = job.logs[-self.max_memory_lines:]
            job.updated_at = utc_now_iso()

        with open(self._jobs[job_id].log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def tail_logs(self, job_id: str, tail: int = 200, raw: bool = False) -> list[str] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        if not raw:
            return job.logs[-tail:]
        if not os.path.exists(job.log_file):
            return []
        with open(job.log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        return lines[-tail:]

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = utc_now_iso()


class PipelineJobLogHandler(logging.Handler):
    def __init__(self, service: PipelineJobService):
        super().__init__(level=logging.INFO)
        self.service = service

    def emit(self, record: logging.LogRecord) -> None:
        job_id = _current_job_id.get()
        if not job_id:
            return
        try:
            message = record.getMessage()
            self.service.append_log(job_id, record.levelname, record.name, message)
        except Exception:
            self.handleError(record)


@contextmanager
def pipeline_job_logging_context(job_id: str):
    token = _current_job_id.set(job_id)
    try:
        yield
    finally:
        _current_job_id.reset(token)


def install_pipeline_job_log_handler(service: PipelineJobService) -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, PipelineJobLogHandler):
            return
    root.addHandler(PipelineJobLogHandler(service))
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)


def run_pipeline_with_job_logging(
    service: PipelineJobService,
    job_id: str,
    fn: Callable[[], dict[str, Any]],
) -> None:
    service.mark_running(job_id)
    with pipeline_job_logging_context(job_id):
        try:
            result = fn()
            if result.get("status") == "translate_pending":
                service.mark_translate_pending(job_id, result)
            else:
                service.mark_succeeded(job_id, result)
        except BaseException as exc:
            service.mark_failed(job_id, exc)

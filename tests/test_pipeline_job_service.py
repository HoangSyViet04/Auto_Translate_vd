from backend.services.pipeline_job_service import (
    PipelineJobService,
    friendly_error_message,
    run_pipeline_with_job_logging,
)


def test_pipeline_job_service_tracks_step_from_log(tmp_path):
    service = PipelineJobService(log_dir=str(tmp_path / "logs"))
    pipeline_job = service.create_job("vi", {"url": "https://example.com/video"})

    service.append_log(
        pipeline_job.job_id,
        "INFO",
        "pipeline_vi",
        "STEP 3: Transcribing audio (ASR)",
    )

    stored = service.get_job(pipeline_job.job_id)
    assert stored is not None
    assert stored.current_step == "Bước 3/8: Bóc băng giọng nói"
    assert stored.logs
    assert service.tail_logs(pipeline_job.job_id)[-1] == "Bước 3/8: Bóc băng giọng nói"


def test_pipeline_job_service_marks_translate_pending(tmp_path):
    service = PipelineJobService(log_dir=str(tmp_path / "logs"))
    pipeline_job = service.create_job("vi", {"url": "https://example.com/video"})

    def pending():
        return {"status": "translate_pending", "work_dir": "output/VN/demo"}

    run_pipeline_with_job_logging(service, pipeline_job.job_id, pending)

    stored = service.get_job(pipeline_job.job_id)
    assert stored.status == "translate_pending"
    assert stored.work_dir == "output/VN/demo"
    assert stored.current_step == "Bước 4/8: Đang chờ file dịch"


def test_pipeline_job_service_marks_failed_step(tmp_path):
    service = PipelineJobService(log_dir=str(tmp_path / "logs"))
    pipeline_job = service.create_job("jp", {"url": "https://example.com/video"})
    service.append_log(
        pipeline_job.job_id,
        "INFO",
        "pipeline",
        "STEP 5: Synthesizing Japanese audio (TTS)",
    )

    def boom():
        raise RuntimeError("tts failed")

    run_pipeline_with_job_logging(service, pipeline_job.job_id, boom)

    stored = service.get_job(pipeline_job.job_id)
    assert stored.status == "failed"
    assert stored.failed_step == "Bước 5/8: Tạo giọng đọc"
    assert stored.error == "tts failed"
    assert "RuntimeError" in stored.traceback


def test_pipeline_job_service_friendly_winerror2_is_actionable():
    friendly = friendly_error_message("[WinError 2] The system cannot find the file specified")

    assert "FFmpeg" in friendly


def test_pipeline_job_service_friendly_ffmpeg_error():
    message = (
        "ERROR: You have requested merging of multiple formats but ffmpeg is not installed. "
        "Aborting due to --abort-on-error"
    )

    friendly = friendly_error_message(message)

    assert "Không tìm thấy FFmpeg" in friendly

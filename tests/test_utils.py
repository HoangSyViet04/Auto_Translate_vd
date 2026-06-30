import os
import logging
from datetime import datetime
from src.utils import setup_logging, ensure_dir, format_timestamp


def test_setup_logging_returns_logger():
    logger = setup_logging("test_logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"


def test_setup_logging_writes_split_log_files(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    logger = setup_logging("split_logger_test")

    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")

    today = datetime.now().strftime("%Y%m%d")
    info_log = tmp_path / "logs" / "info" / f"{today}.log"
    error_log = tmp_path / "logs" / "error" / f"{today}.log"
    debug_log = tmp_path / "logs" / "debug" / f"{today}.log"

    assert info_log.exists()
    assert error_log.exists()
    assert debug_log.exists()

    info_text = info_log.read_text(encoding="utf-8")
    error_text = error_log.read_text(encoding="utf-8")
    debug_text = debug_log.read_text(encoding="utf-8")

    assert "[INFO] split_logger_test" in info_text
    assert "[WARNING] split_logger_test" in info_text
    assert "debug message" not in info_text
    assert "error message" not in info_text

    assert "[ERROR] split_logger_test" in error_text
    assert "[CRITICAL] split_logger_test" in error_text
    assert "info message" not in error_text

    assert "debug message" in debug_text
    assert "info message" in debug_text
    assert "warning message" in debug_text
    assert "error message" in debug_text
    assert "critical message" in debug_text


def test_ensure_dir_creates_directory(tmp_path):
    new_dir = tmp_path / "subdir" / "nested"
    result = ensure_dir(str(new_dir))
    assert os.path.isdir(result)
    assert result == str(new_dir)


def test_ensure_dir_existing_directory(tmp_path):
    result = ensure_dir(str(tmp_path))
    assert os.path.isdir(result)


def test_format_timestamp_zero():
    assert format_timestamp(0.0) == "00:00:00,000"


def test_format_timestamp_seconds():
    assert format_timestamp(3.2) == "00:00:03,200"


def test_format_timestamp_minutes():
    assert format_timestamp(65.5) == "00:01:05,500"


def test_format_timestamp_hours():
    assert format_timestamp(3661.123) == "01:01:01,123"

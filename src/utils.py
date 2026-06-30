import os
import logging
from datetime import datetime


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Cau hinh logger theo 3 nhanh file: info, error va debug."""
    log_root = os.getenv("LOG_DIR", "logs")
    log_date = datetime.now().strftime("%Y%m%d")
    log_format = "[%(asctime)s] [%(levelname)s] %(name)s (%(funcName)s) - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    class _ExactLevelRangeFilter(logging.Filter):
        """Loc log nam trong khoang level mong muon."""

        def __init__(self, min_level: int, max_level: int):
            super().__init__()
            self.min_level = min_level
            self.max_level = max_level

        def filter(self, record: logging.LogRecord) -> bool:
            return self.min_level <= record.levelno <= self.max_level

    def _build_handler(handler: logging.Handler, handler_level: int) -> logging.Handler:
        # Moi handler dung chung formatter de log de quet bang mat.
        handler.setLevel(handler_level)
        handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
        handler._auto_translate_handler = True  # type: ignore[attr-defined]
        return handler

    def _file_handler(folder_name: str, handler_level: int) -> logging.FileHandler:
        # Tu tao folder theo nhom log va ghi vao file cua ngay hien tai.
        folder = os.path.join(log_root, folder_name)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{log_date}.log")
        return _build_handler(
            logging.FileHandler(path, encoding="utf-8"),
            handler_level,
        )

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Neu logger da duoc cau hinh boi ham nay, go bo handler cu de tranh ghi trung.
    for handler in list(logger.handlers):
        if getattr(handler, "_auto_translate_handler", False):
            logger.removeHandler(handler)
            handler.close()

    info_handler = _file_handler("info", logging.INFO)
    info_handler.addFilter(_ExactLevelRangeFilter(logging.INFO, logging.WARNING))

    error_handler = _file_handler("error", logging.ERROR)
    error_handler.addFilter(_ExactLevelRangeFilter(logging.ERROR, logging.CRITICAL))

    debug_handler = _file_handler("debug", logging.DEBUG)

    console_handler = _build_handler(logging.StreamHandler(), logging.INFO)

    for handler in (info_handler, error_handler, debug_handler, console_handler):
        logger.addHandler(handler)

    logger.propagate = True
    return logger


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

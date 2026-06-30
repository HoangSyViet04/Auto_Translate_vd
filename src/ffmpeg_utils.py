from __future__ import annotations

import shutil
import subprocess


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    if name == "ffmpeg":
        raise RuntimeError(
            "Không tìm thấy FFmpeg. Hãy cài FFmpeg, thêm vào PATH, rồi chạy lại tác vụ."
        )
    if name == "ffprobe":
        raise RuntimeError(
            "Không tìm thấy FFprobe. Hãy cài bản FFmpeg đầy đủ, thêm vào PATH, rồi chạy lại tác vụ."
        )
    raise RuntimeError(f"Không tìm thấy chương trình cần chạy: {name}")


def run_ffmpeg(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    if cmd and cmd[0] in {"ffmpeg", "ffprobe"}:
        cmd = [require_tool(cmd[0]), *cmd[1:]]
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError as exc:
        binary = cmd[0] if cmd else "chương trình"
        raise RuntimeError(
            f"Không tìm thấy {binary}. Hãy cài FFmpeg/FFprobe và thêm vào PATH."
        ) from exc

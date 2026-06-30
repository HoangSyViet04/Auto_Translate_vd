import os
import shutil
import subprocess

from src.utils import setup_logging

logger = setup_logging("video_merger")

SUBTITLE_STYLES = {
    "white": {"primary": "&H00FFFFFF", "outline": "&H00000000", "outline_width": 2},
    "yellow": {"primary": "&H0000FFFF", "outline": "&H00000000", "outline_width": 2},
    "red": {"primary": "&H004444FF", "outline": "&H00000000", "outline_width": 2},
    "cyan": {"primary": "&H00EED322", "outline": "&H00000000", "outline_width": 2},
}

OVERLAY_BOX = "x=iw*0.06:y=ih*0.77:w=iw*0.88:h=ih*0.11"


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "Không tìm thấy FFmpeg. Hãy cài FFmpeg, thêm vào PATH, rồi chạy lại tác vụ."
        )


def _escape_subtitle_path(path: str) -> str:
    normalized = os.path.abspath(path).replace("\\", "/")
    return normalized.replace(":", "\\:").replace("'", "\\'")


def _subtitle_force_style(sub_style: str) -> str:
    style = SUBTITLE_STYLES.get(sub_style, SUBTITLE_STYLES["white"])
    return (
        "FontName=Arial,"
        "FontSize=18,"
        f"PrimaryColour={style['primary']},"
        f"OutlineColour={style['outline']},"
        "BorderStyle=1,"
        f"Outline={style['outline_width']},"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=96"
    )


def _overlay_filter(overlay_type: str, *, allow_delogo: bool = True) -> str | None:
    if overlay_type == "none":
        return None
    if overlay_type == "solid":
        return f"drawbox={OVERLAY_BOX}:color=black@0.92:t=fill"
    if overlay_type == "soft":
        return f"drawbox={OVERLAY_BOX}:color=black@0.50:t=fill"
    if allow_delogo:
        return f"delogo={OVERLAY_BOX}:show=0"
    return f"drawbox={OVERLAY_BOX}:color=black@0.76:t=fill"


def _build_filter_complex(
    subtitle_path: str | None,
    sub_style: str,
    overlay_type: str,
    *,
    allow_delogo: bool = True,
) -> str | None:
    filters = []
    overlay = _overlay_filter(overlay_type, allow_delogo=allow_delogo)
    if overlay:
        filters.append(overlay)
    if subtitle_path:
        escaped_path = _escape_subtitle_path(subtitle_path)
        force_style = _subtitle_force_style(sub_style)
        filters.append(f"subtitles='{escaped_path}':force_style='{force_style}'")
    if not filters:
        return None
    return f"[0:v]{','.join(filters)}[vout]"


def merge_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    subtitle_path: str | None = None,
    sub_style: str = "white",
    overlay_type: str = "default",
) -> str:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")
    if subtitle_path and not os.path.exists(subtitle_path):
        logger.warning(f"Subtitle file not found, rendering without subtitles: {subtitle_path}")
        subtitle_path = None

    _require_ffmpeg()

    filter_complex = _build_filter_complex(subtitle_path, sub_style, overlay_type)
    if filter_complex:
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-shortest",
            "-y",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-map", "0:v",
            "-map", "1:a",
            "-shortest",
            "-y",
            output_path,
        ]

    logger.info(
        f"Merging video + audio -> {output_path} "
        f"(sub_style={sub_style}, overlay_type={overlay_type})"
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and filter_complex and "delogo=" in filter_complex:
        logger.warning("FFmpeg delogo filter failed; retrying with drawbox overlay fallback")
        fallback_filter = _build_filter_complex(
            subtitle_path,
            sub_style,
            overlay_type,
            allow_delogo=False,
        )
        fallback_cmd = cmd.copy()
        fallback_cmd[fallback_cmd.index("-filter_complex") + 1] = fallback_filter
        result = subprocess.run(fallback_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")

    logger.info(f"Video merged: {output_path}")
    return output_path

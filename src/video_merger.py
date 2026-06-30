import os

from src.ffmpeg_utils import require_tool, run_ffmpeg
from src.utils import setup_logging

logger = setup_logging("video_merger")

SUBTITLE_STYLES = {
    "white": {"primary": "&H00FFFFFF", "outline": "&H00000000", "outline_width": 2, "font": "Arial", "shadow": 0},
    "yellow": {"primary": "&H0000FFFF", "outline": "&H00000000", "outline_width": 2, "font": "Arial", "shadow": 0},
    "red": {"primary": "&H004444FF", "outline": "&H00000000", "outline_width": 2, "font": "Arial", "shadow": 0},
    "cyan": {"primary": "&H00EED322", "outline": "&H00000000", "outline_width": 2, "font": "Arial", "shadow": 0},
    "black": {"primary": "&H00111111", "outline": "&H00FFFFFF", "outline_width": 3, "font": "Arial", "shadow": 0},
    "bold": {"primary": "&H00FFFFFF", "outline": "&H00000000", "outline_width": 4, "font": "Arial Black", "shadow": 1},
    "neon": {"primary": "&H0000F5FF", "outline": "&H00AE00FF", "outline_width": 3, "font": "Arial Black", "shadow": 1},
    "soft": {"primary": "&H00F8FAFC", "outline": "&H006B7280", "outline_width": 2, "font": "Segoe UI", "shadow": 1},
}


def _clamp_pct(value: float | None, default: float, min_value: float, max_value: float) -> float:
    try:
        number = float(value if value is not None else default)
    except (TypeError, ValueError):
        number = default
    return max(min_value, min(max_value, number))


def _overlay_geometry(
    overlay_x: float | None,
    overlay_y: float | None,
    overlay_w: float | None,
    overlay_h: float | None,
) -> tuple[float, float, float, float]:
    width = _clamp_pct(overlay_w, 0.82, 0.18, 0.96)
    height = _clamp_pct(overlay_h, 0.10, 0.04, 0.38)
    x = _clamp_pct(overlay_x, 0.09, 0.0, 1.0 - width)
    y = _clamp_pct(overlay_y, 0.78, 0.0, 1.0 - height)
    return x, y, width, height


def _box_expr(
    overlay_x: float | None,
    overlay_y: float | None,
    overlay_w: float | None,
    overlay_h: float | None,
) -> tuple[str, str, str, str]:
    x, y, width, height = _overlay_geometry(overlay_x, overlay_y, overlay_w, overlay_h)
    return f"iw*{x:.4f}", f"ih*{y:.4f}", f"iw*{width:.4f}", f"ih*{height:.4f}"


def _require_ffmpeg() -> str:
    return require_tool("ffmpeg")


def _escape_subtitle_path(path: str) -> str:
    normalized = os.path.abspath(path).replace("\\", "/")
    return normalized.replace(":", "\\:").replace("'", "\\'")


def _subtitle_force_style(sub_style: str) -> str:
    style = SUBTITLE_STYLES.get(sub_style, SUBTITLE_STYLES["white"])
    return (
        f"FontName={style['font']},"
        "FontSize=18,"
        f"PrimaryColour={style['primary']},"
        f"OutlineColour={style['outline']},"
        "BorderStyle=1,"
        f"Outline={style['outline_width']},"
        f"Shadow={style['shadow']},"
        "Alignment=2,"
        "MarginV=96"
    )


def _linear_overlay_filter(
    overlay_type: str,
    overlay_x: float | None,
    overlay_y: float | None,
    overlay_w: float | None,
    overlay_h: float | None,
    *,
    allow_delogo: bool = True,
) -> str | None:
    x, y, width, height = _box_expr(overlay_x, overlay_y, overlay_w, overlay_h)
    box = f"x={x}:y={y}:w={width}:h={height}"
    if overlay_type == "none" or overlay_type == "blur":
        return None
    if overlay_type == "solid":
        return f"drawbox={box}:color=black@0.92:t=fill"
    if overlay_type == "soft":
        return f"drawbox={box}:color=black@0.50:t=fill"
    if allow_delogo:
        return f"delogo={box}:show=0"
    return f"drawbox={box}:color=black@0.76:t=fill"


def _blur_filter(
    overlay_x: float | None,
    overlay_y: float | None,
    overlay_w: float | None,
    overlay_h: float | None,
    overlay_blur: int | None,
    output_label: str = "ov",
) -> str:
    x, y, width, height = _box_expr(overlay_x, overlay_y, overlay_w, overlay_h)
    blur = int(_clamp_pct(overlay_blur, 14, 2, 40))
    return (
        f"[0:v]split=2[base][blur];"
        f"[blur]crop=w={width}:h={height}:x={x}:y={y},boxblur={blur}:1[blurred];"
        f"[base][blurred]overlay=x={x}:y={y}[{output_label}]"
    )


def _build_filter_complex(
    subtitle_path: str | None,
    sub_style: str,
    overlay_type: str,
    *,
    overlay_x: float | None = None,
    overlay_y: float | None = None,
    overlay_w: float | None = None,
    overlay_h: float | None = None,
    overlay_blur: int | None = None,
    allow_delogo: bool = True,
) -> str | None:
    subtitles = None
    if subtitle_path:
        escaped_path = _escape_subtitle_path(subtitle_path)
        force_style = _subtitle_force_style(sub_style)
        subtitles = f"subtitles='{escaped_path}':force_style='{force_style}'"

    if overlay_type == "blur":
        if subtitles:
            blur_filter = _blur_filter(overlay_x, overlay_y, overlay_w, overlay_h, overlay_blur)
            return f"{blur_filter};[ov]{subtitles}[vout]"
        return _blur_filter(overlay_x, overlay_y, overlay_w, overlay_h, overlay_blur, "vout")

    linear_filters = []
    overlay = _linear_overlay_filter(
        overlay_type,
        overlay_x,
        overlay_y,
        overlay_w,
        overlay_h,
        allow_delogo=allow_delogo,
    )
    if overlay:
        linear_filters.append(overlay)
    if subtitles:
        linear_filters.append(subtitles)
    if not linear_filters:
        return None
    return f"[0:v]{','.join(linear_filters)}[vout]"


def merge_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    subtitle_path: str | None = None,
    sub_style: str = "white",
    overlay_type: str = "blur",
    overlay_x: float | None = None,
    overlay_y: float | None = None,
    overlay_w: float | None = None,
    overlay_h: float | None = None,
    overlay_blur: int | None = None,
) -> str:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")
    if subtitle_path and not os.path.exists(subtitle_path):
        logger.warning(f"Subtitle file not found, rendering without subtitles: {subtitle_path}")
        subtitle_path = None

    ffmpeg = _require_ffmpeg()

    filter_complex = _build_filter_complex(
        subtitle_path,
        sub_style,
        overlay_type,
        overlay_x=overlay_x,
        overlay_y=overlay_y,
        overlay_w=overlay_w,
        overlay_h=overlay_h,
        overlay_blur=overlay_blur,
    )
    if filter_complex:
        cmd = [
            ffmpeg,
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
            ffmpeg,
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

    result = run_ffmpeg(cmd, capture_output=True, text=True)
    if result.returncode != 0 and filter_complex and "delogo=" in filter_complex:
        logger.warning("FFmpeg delogo filter failed; retrying with drawbox overlay fallback")
        fallback_filter = _build_filter_complex(
            subtitle_path,
            sub_style,
            overlay_type,
            overlay_x=overlay_x,
            overlay_y=overlay_y,
            overlay_w=overlay_w,
            overlay_h=overlay_h,
            overlay_blur=overlay_blur,
            allow_delogo=False,
        )
        fallback_cmd = cmd.copy()
        fallback_cmd[fallback_cmd.index("-filter_complex") + 1] = fallback_filter
        result = run_ffmpeg(fallback_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")

    logger.info(f"Video merged: {output_path}")
    return output_path

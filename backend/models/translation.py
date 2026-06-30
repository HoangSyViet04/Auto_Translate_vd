from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TranslateRequest(BaseModel):
    video_url: str | None = Field(default=None, description="Video URL from YouTube/TikTok/Douyin")
    local_file: str | None = Field(default=None, description="Local video path on the server")
    resume_dir: str | None = Field(default=None, description="Existing work directory to resume")
    target_language: Literal["vi", "jp"] = Field(default="vi", description="Dub target language")
    source_lang: str = Field(default="zh", description="Source language, e.g. zh, en, vi")
    asr_provider: Literal["auto", "azure", "whisper"] = Field(default="auto")
    bgm_mode: Literal["demucs", "duck", "none"] = Field(default="demucs")
    bg_duck_db: float = Field(default=-12.0)
    target_voice: str = Field(default="male", description="VI: male/female. JP: Azure voice name.")
    voice_id: str | None = Field(default=None, description="Optional LucyLab voice id override for Vietnamese")
    skip_video: bool = False
    sub_style: Literal["white", "yellow", "red", "cyan", "black", "bold", "neon", "soft"] = Field(default="white")
    overlay_type: Literal["blur", "default", "solid", "soft", "none"] = Field(default="blur")
    overlay_x: float | None = Field(default=None, ge=0.0, le=1.0)
    overlay_y: float | None = Field(default=None, ge=0.0, le=1.0)
    overlay_w: float | None = Field(default=None, ge=0.05, le=1.0)
    overlay_h: float | None = Field(default=None, ge=0.03, le=1.0)
    overlay_blur: int | None = Field(default=None, ge=2, le=40)
    output_dir: str | None = None

    @model_validator(mode="after")
    def require_video_or_resume(self):
        if not self.video_url and not self.local_file and not self.resume_dir:
            raise ValueError("Provide video_url, local_file, or resume_dir")
        return self

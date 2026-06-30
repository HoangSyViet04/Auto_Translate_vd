"""Dich transcript bang Gemini.

Module nay co y do rat don gian:
- Nhan danh sach segment ASR tu transcript_original.json.
- Goi Gemini de them field dich text_vi/text_jp.
- Kiem tra ket qua va merge lai voi field goc de pipeline tiep tuc chay.
"""
from __future__ import annotations

import json
from typing import Any


def _target_info(target_lang: str) -> tuple[str, str, str]:
    """Lay ten ngon ngu, field output va toc do noi de dua vao prompt."""
    if target_lang == "vi-VN" or target_lang == "vi":
        return (
            "Vietnamese",
            "text_vi",
            "Vietnamese: ~12 chars/sec normal, ~15 chars/sec max at 1.3x",
        )
    return (
        "Japanese",
        "text_jp",
        "Japanese: ~7-8 chars/sec normal, ~10 chars/sec max at 1.3x",
    )


def _style_rules(target_lang: str) -> str:
    """Quy tac phong cach ngan gon cho tung ngon ngu dich."""
    if target_lang == "vi-VN" or target_lang == "vi":
        # CHỖ ĐIỀN PROMPT: Sửa nội dung các dòng dưới đây theo đúng ý muốn
        return """- Dùng giọng văn TikTok/Douyin cuốn hút, gần gũi.
- Xưng hô phù hợp với chủ đề video (Ví dụ: mình / các bạn). 
- Bỏ hoàn toàn các từ đệm, từ hát sớn vô nghĩa của tiếng Trung (như 啊, 呢, 嘛).
- Dịch thoát ý, câu ngắn gọn, rõ ràng để đảm bảo vừa khớp thời lượng chạy của video.
- Các tên riêng tiếng Trung nếu có thì dịch sang âm Hán Việt hoặc giữ nguyên tên thương hiệu gốc."""
    
    return """- Dung van noi tieng Nhat tu nhien, ngan gon, khong qua lich su.
- Uu tien cau ngan de vua thoi luong TTS.
- Ten rieng/thuong hieu giu on dinh trong toan bo transcript.
- Doan bi beep hoac chi co ky tu dac biet: dung cam than ngan nhu "あー" hoac "うっ"."""


def build_translation_prompt(
    segments: list[dict[str, Any]],
    target_lang: str,
    source_lang: str,
) -> str:
    """Tao prompt yeu cau Gemini tra ver JSON hop le, cung so segment."""
    target_name, out_field, pace = _target_info(target_lang)
    segments_json = json.dumps(segments, ensure_ascii=False, indent=2)

    return f"""You are translating an ASR transcript for a video dubbing pipeline.

Source language: {source_lang}
Target language: {target_lang} ({target_name})

OUTPUT FORMAT (STRICT):
- Return a JSON array ONLY.
- Return valid JSON only. No markdown fences. No commentary.
- Keep the exact same length, same order, and same 'id's as the input array.
- Keep all original fields (id, text, start, end, duration) untouched.
- For each segment, add exactly one new string field: "{out_field}".

STYLE AND CONSTRAINTS:
{_style_rules(target_lang)}

DURATION-AWARE LENGTH:
- Each segment has a duration in seconds. The translation must fit within this timing.
- Spoken pace reference: {pace}.
- Short segments (< 4s): use the shortest, most natural phrase possible.
- Medium segments (4-8s): compact and meaningful.
- Long segments (> 8s): clear but avoid unnecessary bloat.

Input JSON to translate:
{segments_json}
"""


def parse_translation_json(raw_text: str) -> list[dict[str, Any]]:
    """Parse JSON Gemini tra ve, ke ca khi bi boc trong markdown fence."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(text[start:end + 1])

    if not isinstance(data, list):
        raise ValueError("Gemini translation response must be a JSON array")
    return data


def _merge_and_validate(
    original_segments: list[dict[str, Any]],
    translated_segments: list[dict[str, Any]],
    out_field: str,
) -> list[dict[str, Any]]:
    """Kiem tra so luong/id va copy ban dich vao segment goc."""
    if len(original_segments) != len(translated_segments):
        raise ValueError(
            f"Gemini returned {len(translated_segments)} segments, expected {len(original_segments)}"
        )

    merged: list[dict[str, Any]] = []
    for original, translated in zip(original_segments, translated_segments):
        if translated.get("id") != original.get("id"):
            raise ValueError(
                f"Segment id mismatch: expected {original.get('id')}, got {translated.get('id')}"
            )

        translated_text = str(translated.get(out_field, "")).strip()
        if not translated_text:
            raise ValueError(f"Missing {out_field} for segment {original.get('id')}")

        merged.append({**original, out_field: translated_text})

    return merged


def translate_segments_with_gemini(
    segments: list[dict[str, Any]],
    target_lang: str,
    source_lang: str,
    api_key: str,
    model_id: str = "gemini-1.5-flash", # Mặc định dùng bản Flash tối ưu chi phí
) -> list[dict[str, Any]]:
    """Goi Gemini API va tra ve transcript da dich."""
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is required for Gemini translation")

    from google import genai
    from google.genai import types

    _, out_field, _ = _target_info(target_lang)
    prompt = build_translation_prompt(segments, target_lang, source_lang)
    client = genai.Client(api_key=api_key)

    # Tối ưu: Bắt buộc Gemini ép đầu ra trả về cấu trúc mảng JSON sạch sẽ
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16000,
            response_mime_type="application/json", 
        ),
    )
    translated = parse_translation_json(response.text or "[]")
        
    return _merge_and_validate(segments, translated, out_field)

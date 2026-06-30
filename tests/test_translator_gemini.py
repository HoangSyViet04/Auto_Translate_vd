import pytest

from src.translator_gemini import (
    _merge_and_validate,
    build_translation_prompt,
    parse_translation_json,
)


def test_build_translation_prompt_mentions_expected_output_field():
    segments = [{"id": 1, "text": "Hello", "start": 0.0, "end": 1.0, "duration": 1.0}]

    prompt = build_translation_prompt(segments, "vi-VN", "en-US")

    assert '"text_vi"' in prompt
    assert "Return valid JSON only" in prompt
    assert "Hello" in prompt


def test_parse_translation_json_accepts_markdown_fence():
    raw = """```json
[
  {"id": 1, "text": "Hello", "text_vi": "Xin chao"}
]
```"""

    data = parse_translation_json(raw)

    assert data[0]["text_vi"] == "Xin chao"


def test_merge_and_validate_preserves_original_fields():
    original = [{"id": 1, "text": "Hello", "start": 0, "end": 1, "duration": 1}]
    translated = [{"id": 1, "text_vi": "Xin chao"}]

    merged = _merge_and_validate(original, translated, "text_vi")

    assert merged == [
        {"id": 1, "text": "Hello", "start": 0, "end": 1, "duration": 1, "text_vi": "Xin chao"}
    ]


def test_merge_and_validate_rejects_id_mismatch():
    original = [{"id": 1, "text": "Hello"}]
    translated = [{"id": 2, "text_vi": "Xin chao"}]

    with pytest.raises(ValueError, match="Segment id mismatch"):
        _merge_and_validate(original, translated, "text_vi")

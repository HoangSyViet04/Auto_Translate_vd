# Auto Translate Video

Ứng dụng web + pipeline Python để tự động lồng tiếng video từ YouTube, TikTok, Douyin hoặc file local sang tiếng Việt hoặc tiếng Nhật.

Luồng chính: tải video, tách audio, nhận diện giọng nói bằng Azure Speech, dịch transcript bằng Gemini, tạo TTS, mix lại audio với nhạc nền/SFX, rồi xuất video đã lồng tiếng.

## Cấu trúc thư mục

```text
backend/        FastAPI entrypoint, service chạy task và quản lý log
frontend/       Giao diện web tĩnh: index.html, style.css, script.js
src/            Lõi pipeline: download, ASR, Gemini translate, TTS, merge audio/video, SRT
scripts/        Script tiện ích: chạy batch, tải video, sinh content
tests/          Unit test
docs/specs/     Đặc tả dự án
docs/plans/     Kế hoạch triển khai
docs/api/       Tài liệu API backend
data/examples/  File JSON mẫu
output/         Kết quả chạy pipeline
downloads/      Video tải riêng
input/          Video input local
logs/           Log backend/task
```

Entrypoint chính ở root:

```text
pipeline_vi.py  CLI lồng tiếng Việt
pipeline.py     CLI lồng tiếng Nhật
config.py       Load cấu hình từ .env
```

## Yêu cầu

- Python 3.10+
- FFmpeg/FFprobe trong `PATH`
- Azure Speech key/region cho ASR và TTS tiếng Nhật
- LucyLab API key + voice id nếu lồng tiếng Việt
- Google Gemini API key để dịch transcript tự động và sinh metadata
- Playwright Chromium nếu cần tải Douyin

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

Điền `.env`:

```ini
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=japaneast

VIETNAMESE_API_KEY=...
VIETNAMESE_VOICEID_MALE=...
VIETNAMESE_VOICEID_FEMALE=...

TTS_VOICE=ja-JP-KeitaNeural
DEFAULT_SOURCE_LANG=en-US
OUTPUT_DIR=./output

GOOGLE_API_KEY=...
```

Bạn cũng có thể dùng tên cũ `google_api_key=...`; code hiện hỗ trợ cả hai.

## Chạy web app

Khởi động backend:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Mở giao diện:

```text
http://localhost:8000
```

Mở Swagger UI:

```text
http://localhost:8000/docs
```

Kiểm tra health:

```bash
curl http://localhost:8000/health
```

## API chính

API không dùng `/job` hoặc `/jobs`. Endpoint chính là:

```text
POST /api/translate
POST /api/translate/upload
GET  /api/translations
GET  /api/translate/{translation_id}
GET  /api/translate/{translation_id}/logs
```

Tạo task lồng tiếng Việt:

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"video_url\":\"https://v.douyin.com/...\",\"target_language\":\"vi\",\"source_lang\":\"zh\",\"target_voice\":\"male\",\"bgm_mode\":\"demucs\"}"
```

Body mẫu:

```json
{
  "video_url": "https://...",
  "local_file": null,
  "resume_dir": null,
  "target_language": "vi",
  "source_lang": "zh",
  "target_voice": "male",
  "skip_video": false,
  "bgm_mode": "demucs",
  "bg_duck_db": -12.0
}
```

Upload file video từ web UI sẽ gọi endpoint raw upload:

```bash
curl -X POST "http://localhost:8000/api/translate/upload?filename=video.mp4&target_language=vi&source_lang=zh&target_voice=male&bgm_mode=demucs" ^
  -H "Content-Type: application/octet-stream" ^
  --data-binary "@input/video.mp4"
```

File upload được lưu vào `input/uploads/`, sau đó backend chạy pipeline bằng `local_file`.

Tạo task lồng tiếng Nhật:

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"video_url\":\"https://www.youtube.com/watch?v=...\",\"target_language\":\"jp\",\"source_lang\":\"en\",\"target_voice\":\"ja-JP-KeitaNeural\"}"
```

Xem trạng thái và log:

```bash
curl http://localhost:8000/api/translate/<translation_id>
curl "http://localhost:8000/api/translate/<translation_id>/logs?tail=200"
```

Mặc định endpoint logs trả tiến trình ngắn gọn bằng tiếng Việt, ví dụ `Bước 1/8: Lấy video`. Nếu cần xem log kỹ thuật đầy đủ để debug sâu:

```bash
curl "http://localhost:8000/api/translate/<translation_id>/logs?tail=200&raw=true"
```

Mỗi task có log raw riêng:

```text
logs/debug/jobs/<translation_id>.log
```

Nếu lỗi, API trả về `status=failed`, `failed_step`, `error`, `traceback` để biết lỗi ở bước nào.

## Chạy CLI trực tiếp

Lồng tiếng Việt:

```bash
python pipeline_vi.py --url "https://v.douyin.com/..." --source-lang zh --voice male
python pipeline_vi.py --file input/video.mp4 --source-lang zh --voice female
```

Lồng tiếng Nhật:

```bash
python pipeline.py --url "https://www.youtube.com/watch?v=..." --source-lang en --voice ja-JP-KeitaNeural
python pipeline.py --file input/video.mp4 --source-lang en
```

Chế độ nhạc nền/audio gốc:

```bash
python pipeline_vi.py --url "..." --source-lang zh --voice male --bg-mode demucs
python pipeline_vi.py --url "..." --source-lang zh --voice male --bg-mode duck --bg-duck-db -15
python pipeline_vi.py --url "..." --source-lang zh --voice male --bg-mode none
```

`demucs` cho chất lượng tốt hơn nhưng nặng. `duck` nhanh hơn vì chỉ hạ âm lượng audio gốc. `none` bỏ audio gốc và chỉ giữ TTS.

## Bước dịch bằng Gemini

Pipeline hiện dùng Gemini ở Step 4:

- Nếu có `GOOGLE_API_KEY`, pipeline tự gọi Gemini để tạo `transcript_vi.json` hoặc `transcript_jp.json`.
- Nếu không có key hoặc Gemini lỗi, pipeline tạo `<work_dir>/TRANSLATE_PENDING.txt`.
- File pending có prompt sẵn để bạn dùng Gemini web thủ công, lưu lại JSON dịch, rồi resume.

File dịch cần có:

```text
transcript_vi.json  field text_vi cho tiếng Việt
transcript_jp.json  field text_jp cho tiếng Nhật
```

Resume CLI:

```bash
python pipeline_vi.py --resume "output/VN/20260630120000_vi" --file input/video.mp4 --voice male
python pipeline.py --resume "output/20260630120000" --file input/video.mp4
```

Resume qua backend:

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"resume_dir\":\"output/VN/20260630120000_vi\",\"target_language\":\"vi\",\"target_voice\":\"male\"}"
```

## Script tiện ích

Chạy batch từ Excel:

```bash
python scripts/batch_run_vi.py --excel output/video_link.xlsx --source-lang zh --voice male
python scripts/batch_run.py --excel output/video_link.xlsx --source-lang en
```

Chạy batch tiếng Việt từ JSON:

```bash
python scripts/batch_run_json.py --json list_video.json --source-lang zh
```

File mẫu:

```text
data/examples/list_video.example.json
data/examples/get_content_url.example.json
```

Tải video riêng:

```bash
python scripts/download_video.py "https://www.youtube.com/watch?v=..." --output-dir downloads
python scripts/download_video.py --file video_links.txt --output-dir downloads
```

Lấy caption/script YouTube:

```bash
python scripts/get_youtube_script.py "https://www.youtube.com/watch?v=..." --lang en,vi,ja
```

Chạy lại content generation cho video đã xong:

```bash
python scripts/run_content_gen.py
```

## Output quan trọng

Nhánh Việt thường tạo:

```text
output/VN/<timestamp>_vi/
  original_audio.wav
  vocals.wav
  no_vocals.wav
  transcript_original.json
  transcript_original.srt
  transcript_vi.json
  transcript_vi.srt
  segments/
  segments_fit/
  fit_adjustments.json
  audio_vi_full.wav
  dubbed_video.mp4
  report.json
  timing_guide.json
```

Nhánh Nhật thường tạo:

```text
output/<timestamp>/
  original_audio.wav
  transcript_original.json
  transcript_original.srt
  transcript_jp.json
  transcript_jp.srt
  segments/
  audio_jp_full.wav
  dubbed_video.mp4
  report.json
  timing_guide.json
```

## Test và kiểm tra

Chạy toàn bộ test:

```bash
python -m pytest tests -v
```


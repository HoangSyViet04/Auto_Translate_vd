# Báo cáo chi tiết project Auto Translate Video

## 1. Project này dùng để làm gì?

Project này là một pipeline CLI bằng Python để tự động lồng tiếng video. Input có thể là URL YouTube, TikTok, Douyin hoặc file video local. Pipeline sẽ tải video, tách audio, nhận diện giọng nói bằng Azure Speech, tạo transcript theo timeline, chờ người dùng dịch transcript sang tiếng Việt hoặc tiếng Nhật, tạo giọng đọc TTS, ghép lại audio theo timestamp, giữ lại nhạc nền hoặc hiệu ứng nếu cấu hình phù hợp, rồi xuất video đã lồng tiếng.

Hiện project có 2 nhánh chính:

- `pipeline_vi.py`: lồng tiếng sang tiếng Việt, dùng LucyLab để TTS.
- `pipeline.py`: lồng tiếng sang tiếng Nhật, dùng Azure Neural Voice để TTS.

Luồng dịch ở Step 4 hiện ưu tiên Gemini tự động. Nếu `.env` có `GOOGLE_API_KEY` hoặc `google_api_key`, pipeline sẽ gọi Gemini để tạo `transcript_vi.json` hoặc `transcript_jp.json`, sinh luôn SRT bản dịch rồi tiếp tục TTS. Nếu không có key hoặc Gemini lỗi, pipeline mới tạo `TRANSLATE_PENDING.txt` để bạn dùng Gemini web thủ công và chạy `--resume`.

## 1.1. Cấu trúc thư mục hiện tại

Repo đã được sắp xếp lại theo khung chuẩn trong `docs/claude-code-workflow.md`:

```text
Auto_Translate_vd/
  CLAUDE.md
  README.md
  requirements.txt
  config.py
  pipeline.py
  pipeline_vi.py
  backend/
    main.py
    app.py
    services/
      translation_api_service.py
      pipeline_job_service.py
  src/
    audio_extractor.py
    audio_merger.py
    content_generator.py
    downloader.py
    downloader_douyin.py
    srt_generator.py
    synthesizer.py
    synthesizer_vi.py
    transcriber.py
    translate_pending.py
    utils.py
    video_merger.py
    vocal_separator.py
  scripts/
    batch_run.py
    batch_run_json.py
    batch_run_vi.py
    download_video.py
    get_youtube_script.py
    run_content_gen.py
  tests/
  docs/
    api/
    plans/
    specs/
  data/
    examples/
```

Quy ước chính:

- `backend/services/`: logic điều phối API/backend.
- `src/`: lõi pipeline từng module, không để output/log/data trong đây.
- `scripts/`: script tiện ích, batch, download phụ trợ.
- `docs/specs/`: đặc tả dự án.
- `docs/plans/`: kế hoạch triển khai.
- `docs/api/`: tài liệu endpoint.
- `data/examples/`: file JSON mẫu.
- `output/`, `downloads/`, `input/`, `logs/`: dữ liệu runtime, không commit.

## 2. Công nghệ và dịch vụ đang dùng

Các dependency chính nằm trong `requirements.txt`:

- `azure-cognitiveservices-speech`: Azure Speech dùng cho ASR và TTS tiếng Nhật.
- `pydub`: xử lý, overlay và xuất audio.
- `yt-dlp`: tải video từ YouTube/TikTok và nhiều site khác.
- `playwright`: tải Douyin bằng Chromium headless do đường yt-dlp Douyin không ổn định.
- `requests`: gọi LucyLab, tải stream, tải thumbnail.
- `openpyxl`: batch video từ Excel.
- `google-genai`: dịch transcript bằng Gemini, sinh metadata YouTube và prompt thumbnail.
- `demucs`, `soundfile`: tách vocal khỏi nhạc nền.
- `pytest`: unit test.

Phụ thuộc hệ thống:

- Python 3.10+.
- FFmpeg và FFprobe trong PATH.
- Chromium cho Playwright nếu dùng Douyin: `playwright install chromium`.
- Internet và API key thật khi chạy các bước tải video, ASR, TTS, Gemini.

## 3. Cài đặt ban đầu

Tạo môi trường và cài thư viện:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Tạo file `.env` từ mẫu:

```bash
copy .env.example .env
```

Điền các biến quan trọng:

```ini
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=japaneast

VIETNAMESE_API_KEY=...
VIETNAMESE_VOICEID_MALE=...
VIETNAMESE_VOICEID_FEMALE=...

TTS_VOICE=ja-JP-KeitaNeural
TTS_MAX_SPEED_RATIO=1.3
DEFAULT_SOURCE_LANG=en-US
AUDIO_SAMPLE_RATE=16000
OUTPUT_DIR=./output

google_api_key=...
image_model_id=gemini-2.0-flash-exp
content_model_id=gemini-2.0-flash
```

Lưu ý: `config.py` bắt buộc có `AZURE_SPEECH_KEY` và `AZURE_SPEECH_REGION`. Nếu thiếu 2 biến này thì nhiều script sẽ thoát ngay khi import `config.py`, kể cả khi script đó chủ yếu chạy nhánh tiếng Việt.

## 4. Cách chạy nhanh

### 4.1. Lồng tiếng Việt từ URL

```bash
python pipeline_vi.py --url "https://www.youtube.com/watch?v=..." --source-lang zh --voice male
```

Với Douyin:

```bash
python pipeline_vi.py --url "https://v.douyin.com/..." --source-lang zh --voice female
```

Với file local:

```bash
python pipeline_vi.py --file input.mp4 --source-lang zh --voice male
```

### 4.2. Lồng tiếng Nhật

```bash
python pipeline.py --url "https://www.youtube.com/watch?v=..." --source-lang en --voice ja-JP-KeitaNeural
```

Với file local:

```bash
python pipeline.py --file input.mp4 --source-lang en --voice ja-JP-KeitaNeural
```

### 4.3. Dịch bằng Gemini rồi resume nếu cần

Nếu có `GOOGLE_API_KEY`, lần chạy đầu sẽ tự dịch bằng Gemini. Pipeline chỉ dừng ở bước dịch nếu chưa có key hoặc Gemini trả lỗi.

- Nhánh Việt cần file: `transcript_vi.json`.
- Nhánh Nhật cần file: `transcript_jp.json`.

Khi bị dừng, mở file `<work_dir>/TRANSLATE_PENDING.txt`, copy prompt trong đó, gửi kèm nội dung `transcript_original.json` cho Gemini web. Sau đó lưu output JSON vào đúng tên file trong cùng thư mục.

Resume tiếng Việt:

```bash
python pipeline_vi.py --resume "output/VN/20260630120000_vi" --file input.mp4 --voice male
```

Resume tiếng Nhật:

```bash
python pipeline.py --resume "output/20260630120000" --file input.mp4
```

Nếu video gốc đã nằm trong work dir và không phải file `dubbed_video*.mp4`, bạn có thể bỏ `--file`; pipeline sẽ tự tìm video source đã cache.

## 5. Các chế độ nhạc nền

Cả `pipeline_vi.py` và `pipeline.py` đều có `--bg-mode`:

- `demucs`: mặc định. Tách `original_audio.wav` thành `vocals.wav` và `no_vocals.wav`, sau đó dùng `no_vocals.wav` làm nền để giữ nhạc, SFX và ambience.
- `duck`: không tách vocal, dùng nguyên `original_audio.wav` làm nền nhưng giảm âm lượng theo `--bg-duck-db`. Mặc định `-12 dB`.
- `none`: không giữ âm thanh gốc, chỉ ghép TTS lên nền im lặng.

Ví dụ:

```bash
python pipeline_vi.py --url "..." --source-lang zh --voice male --bg-mode demucs
python pipeline_vi.py --url "..." --source-lang zh --voice male --bg-mode duck --bg-duck-db -15
python pipeline_vi.py --url "..." --source-lang zh --voice male --bg-mode none
```

`--no-bg-music` vẫn còn nhưng chỉ là alias cũ cho `--bg-mode none`.

## 6. Luồng xử lý chi tiết

### Bước 1: Lấy video

File liên quan:

- `pipeline_vi.py`
- `pipeline.py`
- `src/downloader.py`
- `src/downloader_douyin.py`
- `scripts/download_video.py`

Nếu dùng URL thường, pipeline gọi `yt-dlp` qua `src/downloader.py`. Với Douyin, code chuyển sang `src/downloader_douyin.py` vì yt-dlp Douyin dễ lỗi chữ ký. Module Douyin mở Chromium bằng Playwright, bắt các request CDN video/audio, tải stream về bằng `requests`, rồi mux bằng FFmpeg nếu video và audio tách rời.

Nếu dùng `--file`, pipeline bỏ qua bước download và dùng file local.

### Bước 2: Tách audio

File liên quan:

- `src/audio_extractor.py`

FFmpeg convert audio từ video sang WAV mono 16 kHz:

```bash
ffmpeg -i video.mp4 -vn -ar 16000 -ac 1 -acodec pcm_s16le original_audio.wav
```

Sample rate lấy từ `AUDIO_SAMPLE_RATE` trong `.env`.

### Bước 2.5: Tách vocal hoặc giảm nền

File liên quan:

- `src/vocal_separator.py`
- `src/audio_merger.py`

Khi `--bg-mode demucs`, code chạy Demucs model `htdemucs` bằng Python API, tạo:

- `vocals.wav`: giọng nói gốc.
- `no_vocals.wav`: nhạc nền, hiệu ứng, ambience.

Nếu Demucs lỗi, thiếu model, thiếu dependency hoặc input không tồn tại, hàm trả `None` và pipeline fallback sang nền im lặng thay vì dừng hẳn.

Khi `--bg-mode duck`, không chạy Demucs. Pipeline dùng `original_audio.wav` làm nền và giảm volume theo `--bg-duck-db`.

### Bước 3: ASR

File liên quan:

- `src/transcriber.py`
- `src/srt_generator.py`

Azure Speech nhận diện audio bằng continuous recognition. Mỗi recognized event tạo một segment:

```json
{
  "id": 1,
  "text": "Original speech text",
  "start": 0.5,
  "end": 3.2,
  "duration": 2.7
}
```

Sau ASR, code lưu:

- `transcript_original.json`
- `transcript_original.srt`

Các segment dài hơn 10 giây sẽ được `split_long_segments()` cố gắng chia nhỏ theo dấu câu, phân bổ timestamp theo tỷ lệ số ký tự.

### Bước 4: Dịch bằng Gemini hoặc chờ dịch thủ công

File liên quan:

- `src/translator_gemini.py`
- `src/translate_pending.py`

Pipeline kiểm tra file dịch:

- Tiếng Việt: `transcript_vi.json`, field mới là `text_vi`.
- Tiếng Nhật: `transcript_jp.json`, field mới là `text_jp`.

Nếu file chưa có và `.env` có `GOOGLE_API_KEY`, pipeline gọi Gemini bằng `src/translator_gemini.py`. Module này tạo prompt giữ đúng số segment, parse JSON Gemini trả về, validate số lượng/id/field dịch, rồi merge bản dịch vào segment gốc.

Nếu không có key hoặc Gemini lỗi, pipeline tạo `TRANSLATE_PENDING.txt` và trả về status `translate_pending`. File này hướng dẫn 2 cách:

- Thêm `GOOGLE_API_KEY` rồi chạy `--resume` để Gemini API dịch tự động.
- Dùng Gemini web thủ công, lưu JSON dịch rồi chạy `--resume`.

Format file dịch phải là JSON array cùng số lượng, cùng thứ tự, giữ nguyên các field cũ và thêm field dịch.

Ví dụ cho tiếng Việt:

```json
[
  {
    "id": 1,
    "text": "Original speech text",
    "start": 0.5,
    "end": 3.2,
    "duration": 2.7,
    "text_vi": "Bản dịch tiếng Việt"
  }
]
```

### Bước 5: TTS

File liên quan:

- `src/synthesizer_vi.py`
- `src/synthesizer.py`

Nhánh Việt dùng LucyLab:

- Gọi JSON-RPC method `ttsLongText`.
- Nhận `projectExportId`.
- Poll `getExportStatus` đến khi `completed`.
- Tải audio về, convert sang WAV.
- Tốc độ ban đầu được ước lượng theo độ dài text và duration target.
- Nếu vẫn dài quá, có thể gọi lại một lần với speed cao hơn, tối đa theo `VIETNAMESE_TTS_MAX_SPEED`.

Nhánh Nhật dùng Azure TTS:

- Tạo SSML với voice Azure.
- Ước lượng tốc độ theo số ký tự tiếng Nhật.
- Dùng `<prosody rate="...">`.
- Giảm pause bằng `mstts:silence`.
- Nếu audio dài hơn target, thử synthesize lại với rate phù hợp, tối đa theo `TTS_MAX_SPEED_RATIO`.

Các file segment được lưu ở:

```text
segments/seg_001.wav
segments/seg_002.wav
...
```

### Bước 6: Fit timeline và merge audio

File liên quan:

- `src/audio_merger.py`

Nhánh Việt có thêm bước:

- Chậm audio theo `AUDIO_SLOW_FACTOR` nếu nhỏ hơn 1.0, mặc định 0.82.
- Ghi vào thư mục như `segments_slow18`.
- Chạy `fit_segments_to_timeline()` để nén đoạn nào tràn sang segment tiếp theo.
- Ghi log `fit_adjustments.json`.
- Merge audio TTS lên nền.

Kết quả nhánh Việt:

- `audio_vi_full.wav`

Nhánh Nhật hiện merge trực tiếp từ `segments/`:

- `audio_jp_full.wav`

### Bước 7: Ghép video

File liên quan:

- `src/video_merger.py`

Nếu không dùng `--skip-video`, FFmpeg giữ nguyên video stream và thay audio bằng audio đã dub:

```bash
ffmpeg -i source.mp4 -i audio_vi_full.wav -c:v copy -map 0:v -map 1:a dubbed_video.mp4
```

Kết quả:

- `dubbed_video.mp4`

### Bước 8: Sinh metadata YouTube

File liên quan:

- `src/content_generator.py`
- `scripts/run_content_gen.py`

Nếu có `GOOGLE_API_KEY` hoặc `google_api_key`, pipeline tạo:

- `script_original.txt`
- `script_vi.txt` hoặc `script_jp.txt`
- `thumbnail_prompts.txt`
- `youtube_metadata.json`
- `youtube_post.txt`

Lưu ý: phần gọi Gemini image để tạo ảnh thumbnail hiện đang bị disable trong code. Hiện module chỉ sinh prompt thumbnail, không tạo `thumbnail_1.png` và `thumbnail_2.png` trừ khi bạn tự bật lại block `generate_thumbnails()`.

## 7. Cấu trúc output

Nhánh Việt mặc định tạo thư mục trong `output/VN/`:

```text
output/VN/20260630120000_vi/
  Douyin_123.mp4 hoặc <video_id>.mp4
  original_audio.wav
  vocals.wav
  no_vocals.wav
  transcript_original.json
  transcript_original.srt
  TRANSLATE_PENDING.txt
  transcript_vi.json
  segments/
  segments_slow18/
  segments_fit/
  fit_adjustments.json
  audio_vi_full.wav
  dubbed_video.mp4
  report.json
  timing_guide.json
  script_original.txt
  script_vi.txt
  thumbnail_prompts.txt
  youtube_metadata.json
  youtube_post.txt
```

Nhánh Nhật mặc định tạo thư mục trong `output/`:

```text
output/20260630120000/
  <video_id>.mp4
  original_audio.wav
  vocals.wav
  no_vocals.wav
  transcript_original.json
  transcript_original.srt
  TRANSLATE_PENDING.txt
  transcript_jp.json
  segments/
  audio_jp_full.wav
  dubbed_video.mp4
  report.json
  timing_guide.json
```

`report.json` chứa thống kê tổng quan: session id, ngôn ngữ nguồn, số segment, tổng duration gốc, tổng duration TTS, số segment bị chỉnh tốc độ, thời gian xử lý và đường dẫn file output.

`timing_guide.json` giúp rà segment nào quá dài hoặc quá ngắn so với timeline gốc để chỉnh tiếp trong CapCut.

## 8. Các script ở root

### `pipeline_vi.py`

Entry point chính cho lồng tiếng Việt. Có nhiều logic hơn nhánh Nhật: chọn voice nam/nữ, output mặc định vào `OUTPUT_DIR/VN`, chậm audio theo `AUDIO_SLOW_FACTOR`, fit timeline trước khi merge.

### `pipeline.py`

Entry point cho lồng tiếng Nhật. Dùng Azure TTS voice từ `--voice` hoặc `TTS_VOICE`.

### `scripts/batch_run_vi.py`

Đọc Excel `output/video_link.xlsx` mặc định. Cột 1 là URL, cột 2 là status, cột 3 là folder output. Chỉ xử lý dòng có URL và status trống.

Ví dụ:

```bash
python scripts/batch_run_vi.py --excel output/video_link.xlsx --source-lang zh --voice male
```

### `scripts/batch_run.py`

Tương tự `scripts/batch_run_vi.py` nhưng dùng pipeline Nhật.

### `scripts/batch_run_json.py`

Đọc danh sách video từ JSON rồi chạy nhánh Việt. Code hiện lọc các item có:

```json
"status": "waiting"
```

Mỗi item nên có:

```json
{
  "id": 1,
  "video_url": "https://...",
  "voice_type": "male",
  "status": "waiting"
}
```

Lưu ý quan trọng: file `data/examples/list_video.example.json` hiện ghi `"status": "pending"`, nhưng code lại lọc `"waiting"`. Nếu dùng theo example thì batch sẽ báo không có video pending. Nên đổi status trong file thật thành `"waiting"` hoặc sửa code cho thống nhất.

### `scripts/download_video.py`

Script chỉ tải video, không chạy dubbing. Hỗ trợ nhiều URL, file text chứa URL, output manifest JSON, cookies browser/cookies file cho video cần login.

Ví dụ:

```bash
python scripts/download_video.py "https://www.youtube.com/watch?v=..." --output-dir downloads
python scripts/download_video.py --file urls.txt --output-dir downloads
```

### `scripts/get_youtube_script.py`

Lấy transcript/caption YouTube nhanh nhất, ưu tiên `youtube-transcript-api`, fallback sang `yt-dlp` tải subtitle `.vtt`, rồi parse thành plain text.

Lưu ý: `requirements.txt` hiện không có `youtube-transcript-api`, nên nếu muốn dùng script này cần cài thêm:

```bash
pip install youtube-transcript-api
```

### `scripts/run_content_gen.py`

Chạy lại bước sinh metadata/post cho những video đã success trong `list_video.json`. Script này kỳ vọng output folder nằm trong `OUTPUT_DIR/VN`.

## 9. Các module trong `src/`

### `src/utils.py`

Helper nhỏ:

- `setup_logging()`: tạo logger console.
- `ensure_dir()`: tạo folder nếu chưa có.
- `format_timestamp()`: đổi seconds sang format SRT `HH:MM:SS,mmm`.

### `src/downloader.py`

Wrapper `yt-dlp`, đồng thời normalize một số URL Douyin dạng `modal_id` thành `/video/<id>`. Nếu URL là Douyin thì route sang `downloader_douyin`.

### `src/downloader_douyin.py`

Downloader riêng cho Douyin bằng Playwright. Bắt request media từ CDN, chọn stream bitrate cao nhất theo query `br`, tải bằng `requests`, mux bằng FFmpeg nếu cần.

### `src/audio_extractor.py`

Tách audio bằng FFmpeg, validate file output tồn tại và không rỗng.

### `src/vocal_separator.py`

Chạy Demucs model `htdemucs` bằng Python API. Sau khi tách, normalize stem về WAV mono sample rate của pipeline. Có cache: nếu `vocals.wav` và `no_vocals.wav` đã tồn tại thì không chạy lại.

### `src/transcriber.py`

ASR bằng Azure Speech, tạo segment theo offset/duration, xử lý lỗi cancellation, split segment dài, lưu transcript JSON.

### `src/translate_pending.py`

Tạo file hướng dẫn fallback khi Gemini API chưa chạy được. File này nhắc cách thêm `GOOGLE_API_KEY` để resume tự động, hoặc dùng Gemini web thủ công.

### `src/translator_gemini.py`

Dịch transcript bằng Gemini API. Module này build prompt theo target `vi-VN`/`ja-JP`, parse JSON trả về, kiểm tra số segment/id và đảm bảo mỗi segment có `text_vi` hoặc `text_jp` trước khi pipeline chạy TTS.

### `src/synthesizer_vi.py`

TTS tiếng Việt qua LucyLab. Có polling, timeout `LUCYLAB_POLL_TIMEOUT` mặc định 300 giây, download audio về file tạm rồi export WAV.

### `src/synthesizer.py`

TTS tiếng Nhật qua Azure Neural Voice. Dùng SSML, escape XML text, giảm pause, tự điều chỉnh prosody rate.

### `src/audio_merger.py`

Gồm 2 chức năng:

- `fit_segments_to_timeline()`: nén những đoạn audio tràn sang segment kế tiếp bằng FFmpeg `atempo`, tối đa 1.4x.
- `merge_segments()`: overlay từng segment vào timeline gốc, có thể dùng nền im lặng, `no_vocals.wav` hoặc `original_audio.wav` đã giảm gain.

### `src/video_merger.py`

Ghép video và audio bằng FFmpeg, copy video stream để nhanh hơn re-encode.

### `src/srt_generator.py`

Sinh SRT từ JSON segment.

### `src/content_generator.py`

Sinh script text, prompt thumbnail và metadata YouTube bằng Gemini. Có retry/backoff cho lỗi transient 503, có fallback parse JSON nếu Gemini trả output không chuẩn.

## 10. Test hiện có

Thư mục `tests/` đang cover:

- `test_config.py`: đọc env và default config.
- `test_utils.py`: logger, tạo folder, format timestamp.
- `test_srt_generator.py`: sinh SRT từ field `text` hoặc `text_jp`.
- `test_translator_gemini.py`: build prompt Gemini, parse JSON trong markdown fence, validate/merge bản dịch.
- `test_audio_merger.py`: merge audio, background, padding background, missing background fallback, duck gain.
- `test_vocal_separator.py`: cache hit, input missing, Demucs error fallback, normalize/cleanup khi mock thành công.

Chạy test:

```bash
pytest
```

Hoặc:

```bash
python -m pytest tests -v
```

`.py` set sẵn dummy `AZURE_SPEECH_KEY` và `AZURE_SPEECH_REGION` để import `config.py` trong test không cần key thật.

## 11. Những điểm cần lưu ý hoặc dễ vấp

1. README và một số tài liệu cũ đang bị mojibake khi đọc bằng terminal hiện tại. Nội dung code vẫn dùng UTF-8 khi đọc/ghi JSON, SRT, report.

2. `data/examples/list_video.example.json` dùng `"pending"` nhưng `scripts/batch_run_json.py` lọc `"waiting"`. Khi chạy batch JSON, hãy dùng `"waiting"`.

3. `requirements.txt` thiếu `youtube-transcript-api` dù `scripts/get_youtube_script.py` import package này.

4. Pipeline hiện đã sinh `transcript_vi.srt` và `transcript_jp.srt` sau khi có file dịch. Nếu file SRT đã tồn tại trong work dir khi resume, pipeline sẽ giữ lại.

5. `scripts/run_content_gen.py` kiểm tra thumbnail image tồn tại, nhưng `src/content_generator.py` hiện disable Gemini image generation. Vì vậy output bình thường là `thumbnail_prompts.txt`, không phải ảnh thumbnail.

6. Demucs có thể tải model lần đầu và khá nặng. Nếu máy yếu hoặc cần chạy nhanh, dùng `--bg-mode duck` hoặc `--bg-mode none`.

7. `pipeline_vi.py` mặc định `AUDIO_SLOW_FACTOR=0.82`, tức làm chậm audio Việt thêm khoảng 18% trước khi fit timeline. Nếu nghe quá chậm, chỉnh trong `.env` thành `AUDIO_SLOW_FACTOR=1.0`.

8. LucyLab không nhận text rỗng hoặc chỉ toàn dấu câu. Prompt trong `TRANSLATE_PENDING.txt` đã dặn dùng câu cảm thán ngắn cho đoạn censored, nhưng khi dịch thủ công vẫn cần kiểm tra.

9. Resume sẽ tái dùng các artifact đã tồn tại: video source, `original_audio.wav`, transcript, stems Demucs và segment WAV. Nếu muốn chạy lại một bước, xóa đúng artifact của bước đó trong work dir.

10. Các thao tác tải video, ASR, TTS, Gemini đều phụ thuộc network/API. Unit test không kiểm tra end-to-end các dịch vụ này.

## 12. Quy trình dùng khuyến nghị

Với video tiếng Trung sang tiếng Việt:

```bash
python pipeline_vi.py --url "https://..." --source-lang zh --voice male --bg-mode demucs
```

Nếu pipeline dừng vì thiếu key hoặc Gemini lỗi:

1. Mở folder output vừa tạo.
2. Mở `TRANSLATE_PENDING.txt`.
3. Mở `transcript_original.json`.
4. Dùng prompt trong file pending để dịch bằng Gemini web.
5. Lưu kết quả thành `transcript_vi.json`.
6. Resume:

```bash
python pipeline_vi.py --resume "output/VN/<folder>_vi" --voice male
```

Sau khi xong, kiểm tra:

- `dubbed_video.mp4`: video hoàn chỉnh.
- `audio_vi_full.wav`: audio dub đã mix.
- `timing_guide.json`: đoạn nào cần chỉnh timing.
- `fit_adjustments.json`: đoạn nào bị nén để tránh overlap.
- `youtube_post.txt`: title/description/hashtags nếu bật Gemini metadata.

Nếu cần chỉnh thủ công trong CapCut:

1. Import video gốc.
2. Import `audio_vi_full.wav` hoặc từng file trong `segments_fit/`.
3. Mute audio gốc nếu dùng `--bg-mode none`; nếu dùng Demucs thì audio output đã có nền.
4. Dùng `timing_guide.json` để tìm đoạn quá dài/quá ngắn.

## 13. Gợi ý cải thiện tiếp theo

- Sửa mismatch `"pending"` và `"waiting"` trong batch JSON.
- Thêm `youtube-transcript-api` vào `requirements.txt` nếu muốn giữ `scripts/get_youtube_script.py`.
- Thêm validation tương tự Gemini cho file dịch thủ công khi người dùng tự lưu `transcript_vi.json`/`transcript_jp.json`.
- Thêm CLI option cho `AUDIO_SLOW_FACTOR` thay vì chỉ cấu hình qua `.env`.
- Thêm integration smoke test bằng một audio/video mẫu nhỏ không cần API thật.
- Cập nhật README bằng UTF-8 chuẩn để tránh mojibake.

## 14. Backend FastAPI mới thêm

Project đã có lớp backend đầu tiên trong thư mục `backend/`. Mục tiêu là dùng FastAPI làm lớp điều phối bên ngoài, còn lõi xử lý vẫn tái dùng `run_pipeline_vi()` và `run_pipeline()` hiện có. Như vậy CLI cũ vẫn chạy được, đồng thời có thể gọi pipeline qua API.

File chính:

- `backend/main.py`: entrypoint mỏng để chạy Uvicorn.
- `backend/app.py`: wrapper tương thích cũ, import lại `app` từ service.
- `backend/services/translation_api_service.py`: FastAPI app, định nghĩa endpoint tạo tác vụ dịch/lồng tiếng và xem trạng thái.
- `backend/services/pipeline_job_service.py`: quản lý tác vụ pipeline nền, trạng thái, current step, failed step và log file.
- `logs/<translation_id>.log`: log riêng cho từng tác vụ.

### 14.1. Cài dependency backend

`requirements.txt` đã thêm:

```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
```

Sau khi pull code hoặc đổi môi trường, chạy:

```bash
pip install -r requirements.txt
```

### 14.2. Chạy server

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Kiểm tra:

```bash
curl http://localhost:8000/health
```

Swagger UI:

```text
http://localhost:8000/docs
```

### 14.3. Tạo tác vụ lồng tiếng Việt

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"video_url\":\"https://www.youtube.com/watch?v=...\",\"target_language\":\"vi\",\"source_lang\":\"zh\",\"target_voice\":\"male\",\"bgm_mode\":\"demucs\"}"
```

Body đầy đủ có thể gồm:

```json
{
  "video_url": "https://...",
  "local_file": null,
  "resume_dir": null,
  "target_language": "vi",
  "source_lang": "zh",
  "target_voice": "male",
  "voice_id": null,
  "skip_video": false,
  "output_dir": null,
  "bgm_mode": "demucs",
  "bg_duck_db": -12.0
}
```

Nếu không truyền `voice_id`, backend lấy voice id từ `.env`:

- `target_voice=male` dùng `VIETNAMESE_VOICEID_MALE`.
- `target_voice=female` dùng `VIETNAMESE_VOICEID_FEMALE`.

### 14.4. Tạo tác vụ lồng tiếng Nhật

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"video_url\":\"https://www.youtube.com/watch?v=...\",\"target_language\":\"jp\",\"source_lang\":\"en\",\"target_voice\":\"ja-JP-KeitaNeural\"}"
```

Nếu không truyền voice Nhật cụ thể, backend dùng `TTS_VOICE` trong `.env`.

### 14.5. Resume qua API

Khi tác vụ dừng ở bước dịch, status sẽ là `translate_pending`, response có `work_dir`.

Sau khi bạn lưu `transcript_vi.json` hoặc `transcript_jp.json` vào work dir, gọi lại endpoint với `resume_dir`:

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"resume_dir\":\"output/VN/20260630120000_vi\",\"target_language\":\"vi\",\"target_voice\":\"male\"}"
```

Nếu video source không nằm trong work dir, truyền thêm `local_file`.

### 14.6. Xem trạng thái tác vụ

Khi tạo tác vụ, API trả về `translation_id`. Xem trạng thái:

```bash
curl http://localhost:8000/api/translate/<translation_id>
```

Response quan trọng:

```json
{
  "translation_id": "...",
  "target_language": "vi",
  "status": "running",
  "current_step": "STEP 3: Transcribing audio (ASR)",
  "failed_step": null,
  "progress_percent": 34,
  "work_dir": null,
  "error": null,
  "log_file": "logs/<translation_id>.log"
}
```

Các status hiện có:

- `queued`: đã nhận tác vụ, chờ worker.
- `running`: đang chạy.
- `translate_pending`: pipeline đã tạo `TRANSLATE_PENDING.txt` và chờ file dịch.
- `succeeded`: hoàn tất.
- `failed`: lỗi.

### 14.7. Xem log tác vụ

```bash
curl "http://localhost:8000/api/translate/<translation_id>/logs?tail=200"
```

Log cũng được ghi vào:

```text
logs/<translation_id>.log
```

Nếu tác vụ lỗi, endpoint status sẽ có:

- `status = failed`
- `failed_step`: step cuối cùng backend đọc được từ log, ví dụ `STEP 5: Synthesizing Vietnamese audio (LucyLab TTS)`
- `error`: message lỗi ngắn
- `traceback`: full traceback Python

Nhờ vậy khi lỗi TTS, ASR, download, Demucs hoặc merge video, bạn biết lỗi rơi ở step nào thay vì chỉ thấy pipeline chết chung chung.

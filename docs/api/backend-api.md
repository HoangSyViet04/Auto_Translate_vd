# Backend API

FastAPI entrypoint:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend SPA:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

## Endpoints

```text
GET  /health
POST /api/translate
GET  /api/translations
GET  /api/translate/{translation_id}
GET  /api/translate/{translation_id}/logs
```

## Start Vietnamese Translation

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"video_url\":\"https://...\",\"target_language\":\"vi\",\"source_lang\":\"zh\",\"target_voice\":\"male\",\"bgm_mode\":\"demucs\"}"
```

## Start Japanese Translation

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"video_url\":\"https://...\",\"target_language\":\"jp\",\"source_lang\":\"en\",\"target_voice\":\"ja-JP-KeitaNeural\"}"
```

## Resume Translation

```bash
curl -X POST http://localhost:8000/api/translate ^
  -H "Content-Type: application/json" ^
  -d "{\"resume_dir\":\"output/VN/20260630120000_vi\",\"target_language\":\"vi\",\"target_voice\":\"male\"}"
```

## Status And Logs

```bash
curl http://localhost:8000/api/translate/<translation_id>
curl "http://localhost:8000/api/translate/<translation_id>/logs?tail=200"
```

Each translation task writes:

```text
logs/<translation_id>.log
```


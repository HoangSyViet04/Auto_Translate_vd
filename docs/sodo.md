'
[ BẮT ĐẦU: Nhập Link Video hoặc File ]
       │
       ▼
 ┌────────────────────────────────────────┐
 │ BƯỚC 1: XỬ LÝ ĐẦU VÀO                  │
 │ - Tải video từ Douyin/Youtube (yt-dlp) │
 │ - Bóc tách âm thanh gốc (FFmpeg)       │
 └────────────────────────────────────────┘
       │
       ▼
 ┌────────────────────────────────────────┐
 │ BƯỚC 2: NHẬN DIỆN GIỌNG NÓI (ASR)      │
 │ - Dùng Azure Speech nghe tiếng Trung.  │
 │ - Xuất ra file: transcript_original.json│
 └────────────────────────────────────────┘
       │
       ▼
 ┌────────────────────────────────────────┐
 │ BƯỚC 3: DỊCH THUẬT (RẼ NHÁNH TÙY CHỌN) │
 └────────────────────────────────────────┘
       ├──> NẾU CÓ NẠP TIỀN CLAUDE (Cách A)
       │      │
       │      └─> Gửi thẳng file JSON cho Claude Opus dịch.
       │      └─> Hệ thống chạy tuốt luốt không cần chờ m.
       │
       └──> NẾU KHÔNG DÙNG CLAUDE (Cách B - CÁCH M ĐANG LÀM)
              │
              ├─> Hệ thống báo "TRANSLATE_PENDING" và TẠM DỪNG.
              ├─> M mở file JSON lấy kịch bản tiếng Trung.
              ├─> [HÀNH ĐỘNG CỦA M]: Quăng vào ChatGPT + Prompt cố định.
              ├─> M copy kết quả, lưu thành file transcript_vi.json
              └─> M gõ lệnh "--resume" báo hệ thống chạy tiếp.
       │
       ▼
 ┌────────────────────────────────────────┐
 │ BƯỚC 4: LỒNG TIẾNG BẰNG AI (TTS)       │
 │ - Đọc file transcript_vi.json          │
 │ - Gọi API LucyLab để đọc tiếng Việt.   │
 └────────────────────────────────────────┘
       │
       ▼
 ┌────────────────────────────────────────┐
 │ BƯỚC 5: HẬU KỲ & MIX ÂM THANH          │
 │ - Ép tốc độ giọng nói khớp với video.  │
 │ - Tách nhạc nền gốc (bằng Demucs).     │
 │ - Ghép giọng Việt + Nhạc nền gốc.      │
 └────────────────────────────────────────┘
       │
       ▼
[ KẾT THÚC: Ra file mp4 hoàn chỉnh để đem đăng FB, TikTok ]
'

1. lỗi : 
Bước 2/8: Tách âm thanh
Tác vụ bị lỗi: [WinError 2] The system cannot find the file specified
Tác vụ lỗi ở Bước 2/8: Tách âm thanh: [WinError 2] The system cannot find the file specified

2. là khi t upload video lên thì cái cột ở giữa preview video nó k có hoạt động 
( t cần nó có thể xem như ảnh t gửi á )

3. cái phần style và overlay đấy là t có thể chỉnh sửa trên giao diện đó luôn nha :Hãy nâng cấp Backend FastAPI và hàm render FFmpeg hiện tại để khi bấm "Xuất Video Thành Phẩm", hệ thống sẽ truyền thêm 2 tham số `sub_style` và `overlay_type` từ Frontend về API; sau đó lập tức điều chỉnh lệnh FFmpeg (sử dụng đúng filter delogo/drawbox tương ứng với kiểu overlay) và cấu hình lại style chữ (fontcolor, border của sub tương ứng với style đã chọn) để xuất ra video thành phẩm chuẩn đét như cấu hình trên UI 
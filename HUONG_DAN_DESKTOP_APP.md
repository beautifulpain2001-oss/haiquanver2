# Phần Mềm Desktop Quét PO Offline & Lưu Trữ Hồ Sơ Hải Quan Tập Trung (Hồng Thiên)

## 1. Kiến trúc Ứng dụng Desktop & Tập Lưu Trữ Dữ Liệu Riêng
- **Không sử dụng trình duyệt hay file `.html`:** Ứng dụng chạy bằng cửa sổ Windows Desktop gốc (`hongthien_desktop_app.py` / `.exe`), hoạt động **100% Offline**, không gọi hay truyền bất kỳ file nào ra ngoài Internet.
- **Tập lưu trữ dữ liệu riêng (`DATA_LUU_TRU_HONG_THIEN/`):**
  - `hongthien_haiquan.db`: Cơ sở dữ liệu SQLite riêng chứa toàn bộ danh mục 206 mã cân nặng, 1.833 mã thương mại ERP đầu `TM`, định mức đóng gói Kodi/Tesa và toàn bộ lịch sử hồ sơ hải quan.
  - `master_catalog.json` & `hongthien_records.json`: Tập dữ liệu đồng bộ nhanh qua ổ mạng LAN (chống lỗi khóa file SMB khi nhiều máy cùng mở trên LAN).
  - `01_WORKING_LAM_CHUNG_TU/`: Tự động lưu các file Excel xuất ra ở Bước 1.
  - `02_ARCHIVE_SAU_PHAT_HANH/`: Tự động lưu trữ theo cây thư mục chuẩn các chứng từ gốc đã nạp ở Bước 2.

## 2. Cách Chạy & Chia Sẻ Tập Lưu Trữ Qua Mạng LAN Về Máy Chủ Host
1. Đặt thư mục phần mềm này trên **Máy chủ Host** (hoặc ổ mạng LAN dùng chung `Z:\`).
2. Bấm đúp vào **`1_CHAY_APP_DESKTOP.bat`** để mở phần mềm ngay (hoặc chạy **`2_DONG_GOI_RA_FILE_EXE.bat`** một lần để tạo file `HongThien_HaiQuan_Desktop.exe`).
3. Trên các máy trạm trong mạng LAN, bấm nút **"📂 Chọn Thư Mục Lưu Trữ Tập Trung (Host / Ổ Mạng LAN Z:\)"** trên góc phải phần mềm và trỏ về thư mục `DATA_LUU_TRU_HONG_THIEN` trên Máy chủ Host.

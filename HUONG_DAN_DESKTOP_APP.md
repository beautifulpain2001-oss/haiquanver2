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

## 3. Thêm Khách Hàng Mới Bằng Chứng Từ Mẫu (Học Offline)
1. Bấm **"🧠 Thêm Khách Mới Từ Chứng Từ Mẫu"** trên thanh trên cùng, chọn một lúc nhiều file mẫu của khách:
   - **XML hóa đơn VAT** (TT78): app lấy tên công ty, MST, địa chỉ, email, mã hàng, tên hàng, ĐVT, đơn giá.
   - **XML PXK kiêm VCNB**: app lấy địa chỉ kho nhận, lái xe, biển xe, ký hiệu.
   - **Invoice / Bảng kê PKL Excel**: app suy ra định mức **SL/kiện** (Số lượng ÷ Số kiện) và **kg/chiếc** (N.W ÷ Số lượng), mã HS.
   - **PO mẫu** (PDF có chữ, Excel, PDF scan / ảnh qua OCR, hoặc .txt): app đoán số PO; bạn sửa lại nếu sai, app tự tạo mẫu nhận dạng số PO.
2. Kiểm tra, sửa các ô và xóa dòng hàng sai, bấm **"🔍 Thử đọc PO mẫu"** để xem app đọc đúng chưa, rồi bấm **"💾 Lưu Khách Hàng Mới"**. Chưa bấm Lưu thì không có gì được ghi.
3. Khách mới xuất hiện ở hàng chọn khách của Bước 1. Quét PO như bình thường: app nhận dòng hàng theo mã/tên đã học, tính kiện và cân nặng theo định mức, xuất đủ VAT, PXK, Invoice/PKL, DNTT.
4. Dữ liệu học được lưu trong `master_catalog.json` (`custom_profiles`, `custom_items`), dùng chung qua ổ mạng LAN như danh mục hiện có.

## 4. Bản `.exe` Không Cần Cài Python
- **Tải bản dựng sẵn:** vào tab **Actions → build-exe** trên GitHub, mở lần chạy mới nhất và tải `HongThien_HaiQuan_Desktop_Windows` ở mục *Artifacts* (hoặc tải ở trang **Releases** nếu đã đăng). Giải nén rồi bấm đúp `HongThien_HaiQuan_Desktop.exe`.
- **Tự đóng gói trên máy có Python:** chạy `2_DONG_GOI_RA_FILE_EXE.bat` (dùng `build_exe.py`: build bằng PyInstaller, tự chạy `--self-test` trên bản `.exe`, rồi nén zip vào `dist/`).
- Dữ liệu `DATA_LUU_TRU_HONG_THIEN/` và `config_desktop.json` nằm **cạnh file `.exe`**, không nằm trong thư mục tạm.
- Bản .exe mang sẵn bộ OCR Tesseract (tiếng Việt + Anh, thư mục `Tesseract-OCR` cạnh file .exe) nên đọc được PDF scan / ảnh ngay, 100% offline. Chạy bằng Python thì cần cài Tesseract riêng. Chi tiết ở `HUONG_DAN_BAN_EXE.md`.

PHẦN MỀM HỒ SƠ HẢI QUAN HỒNG THIÊN - BẢN .EXE (KHÔNG CẦN CÀI PYTHON)
=====================================================================

1. CÁCH DÙNG
   - Giải nén file zip vào một thư mục cố định, ví dụ D:\HongThien\
     (KHÔNG chạy thẳng bên trong file zip, vì dữ liệu sẽ không lưu lại được).
   - Bấm đúp HongThien_HaiQuan_Desktop.exe để mở phần mềm.
   - Lần đầu mở có thể mất 5-15 giây vì file tự giải nén các thư viện.
   - Phần mềm chạy 100% offline, không cần Internet, không cần cài Python.

2. DỮ LIỆU NẰM Ở ĐÂU
   - Thư mục DATA_LUU_TRU_HONG_THIEN và file config_desktop.json được tạo
     ngay cạnh file .exe. Sao lưu thì chép cả thư mục đó.
   - Nếu đã có dữ liệu cũ từ bản chạy bằng Python: chép thư mục
     DATA_LUU_TRU_HONG_THIEN (và config_desktop.json nếu có) vào cạnh file .exe.
   - Dùng chung qua mạng LAN: vẫn bấm nút "Chọn Thư Mục Lưu Trữ Tập Trung"
     trong phần mềm và trỏ về thư mục trên máy chủ như trước.

3. WINDOWS BÁO "Windows protected your PC" / phần mềm diệt virus chặn
   - Đây là cảnh báo thường gặp với file .exe tự đóng gói chưa ký số.
     Bấm "More info" -> "Run anyway". Nếu phần mềm diệt virus xóa file,
     hãy thêm thư mục phần mềm vào danh sách ngoại lệ.

4. ĐỌC PDF SCAN / ẢNH (OCR) - KHÔNG BẮT BUỘC
   - PDF có chữ (xuất từ phần mềm) đọc được ngay, không cần cài gì thêm.
   - PDF scan và file ảnh cần OCR Tesseract, chương trình này KHÔNG có sẵn
     trong file .exe (quá lớn). Nếu cần, cài Tesseract cho Windows
     (bản UB Mannheim, chọn thêm ngôn ngữ Vietnamese) vào vị trí mặc định
     C:\Program Files\Tesseract-OCR\ - phần mềm sẽ tự nhận ra.
   - Không cài Tesseract thì mọi chức năng khác vẫn hoạt động bình thường.

5. KIỂM TRA NHANH (không bắt buộc)
   - Mở Command Prompt tại thư mục phần mềm, gõ:
       HongThien_HaiQuan_Desktop.exe --self-test
     Nếu chạy đúng, 3 file Test_Full_*.xlsx sẽ xuất hiện trong
     DATA_LUU_TRU_HONG_THIEN\01_WORKING_LAM_CHUNG_TU\

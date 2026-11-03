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

4. ĐỌC PDF SCAN / ẢNH (OCR) - CÓ SẴN, KHÔNG CẦN CÀI GÌ
   - PDF có chữ (xuất từ phần mềm) đọc trực tiếp lớp chữ như trước.
   - PDF scan (PO dạng ảnh) và file ảnh .png/.jpg được đọc bằng bộ OCR
     Tesseract (tiếng Việt + tiếng Anh) nằm trong thư mục Tesseract-OCR
     đi kèm file zip. Chạy 100% offline trên máy, không gửi file đi đâu.
   - Giữ thư mục Tesseract-OCR NẰM CẠNH file HongThien_HaiQuan_Desktop.exe.
     Nếu chỉ chép riêng file .exe sang máy khác thì nhớ chép cả thư mục này,
     nếu không phần mềm vẫn chạy nhưng không đọc được PDF scan.
   - Mỗi trang scan mất khoảng 1-3 giây. Bản scan càng thẳng, rõ (từ 200 dpi)
     thì càng ít lỗi; luôn soát lại số PO, số lượng trước khi xuất chứng từ.
   - Tesseract là phần mềm mã nguồn mở (giấy phép Apache 2.0).

5. KIỂM TRA NHANH (không bắt buộc)
   - Mở Command Prompt tại thư mục phần mềm, gõ:
       HongThien_HaiQuan_Desktop.exe --self-test
     Nếu chạy đúng, 3 file Test_Full_*.xlsx sẽ xuất hiện trong
     DATA_LUU_TRU_HONG_THIEN\HAI_QUAN\<Khách>\<Năm>_Thang_<mm>\<Ngày>\
   - Kiểm tra bộ OCR: HongThien_HaiQuan_Desktop.exe --ocr-self-test
     (không báo lỗi và không sinh file SELF_TEST_LOI.txt là OCR hoạt động).

## Giao diện

- Bấm đúp `HongThien_HaiQuan_Desktop.exe` mở **giao diện mới** (mặc định).
- Giao diện cũ (Tkinter) đã được gỡ hẳn. Học khách mới từ chứng từ mẫu nằm ở **Khách hàng → Học khách mới từ chứng từ mẫu**; sổ theo dõi hồ sơ ở **Hồ sơ đã lưu → Xuất sổ theo dõi ra Excel**.
- Giao diện mới làm chứng từ theo 5 bước: ① chọn khách hàng → ② nạp file PO (kéo thả được) → ③ kiểm tra và sửa dòng hàng (dòng thiếu thông tin tô vàng) → ④ nhập số PXK, hóa đơn, xe, tài xế → ⑤ kiểm tra (hiện đủ từng cảnh báo), xuất trọn bộ (mỗi chứng từ một file Excel riêng, kèm file KiemTraCheo) hoặc chỉ xuất từng file, rồi lưu hồ sơ.
- **Danh mục** có hai cách xem hồ sơ: *theo tháng* (mặc định là tháng hiện tại, có mũi tên chuyển tháng) và *theo khách hàng* (bấm tên khách để xem các tờ khai đã khai, kèm nút mở thư mục hồ sơ trên máy). Hai bảng cân nặng và mã ERP vẫn ở cùng mục.
- **Cài đặt**: sửa thông tin công ty (tên, mã số thuế, địa chỉ, tài khoản ngân hàng…) — được in lên hóa đơn, phiếu xuất kho, invoice, đề nghị thanh toán, tờ khai. Đổi thư mục lưu dữ liệu.
- **Khách hàng**: sửa tên, mã số thuế, địa chỉ, email, lái xe, biển số xe của từng khách; thêm khách mới (chỉ thông tin hành chính).
- Chưa có ở giao diện mới (vẫn dùng giao diện cũ): thêm khách mới từ chứng từ mẫu, nạp danh mục ERP từ Excel, nạp file chứng từ vào 6 ô lưu trữ (Bước 2 cũ), nạp lô mẫu Tesa 3010/2010.
- Lỗi của giao diện mới được ghi vào `LOI_PHAN_MEM.txt` cạnh file .exe.

## Thư mục hồ sơ và Data tổng

- Mỗi hồ sơ nằm ở `HAI_QUAN/<Khách>/<Năm>_Thang_<mm>/<ngày>/`. Mọi file nằm **thẳng trong thư mục ngày**, không còn thư mục con: file do phần mềm tạo
  (Invoice, Hóa đơn Bkav, PXK Bkav, PLX bản Excel…), bản sao PO gốc (`PO_goc_...`) cùng PO scan, PDF Bkav, DSH và tờ khai của bên hải quan.
  Hồ sơ cũ còn thư mục `DO_PHAN_MEM_TAO` vẫn đọc được bình thường.
- Trang **Tờ khai đang có** đọc tên file để biết đã đủ bộ chưa và còn thiếu gì (theo bộ chứng từ của từng khách).
- Mục **Data tổng**: tên sản phẩm, kg/chiếc (từ file ERP hoặc invoice cũ), SL/kiện (từ invoice cũ). File `DATA_TONG.json` nằm trong thư mục `HAI_QUAN`, ngang hàng thư mục tên khách (Arizon, Best, Tesa...), dùng chung cho mọi máy;
  nạp file ERP hoặc invoice cũ ở chính mục này; mỗi lần xuất chứng từ phần mềm nhớ thêm số liệu đã xác nhận.

## Cập nhật gọn (không tải lại cả bộ)

Mỗi lần build có thêm file **HongThien_HaiQuan_Desktop_CapNhat.zip** (chỉ có `.exe`, không kèm Tesseract-OCR). Tắt phần mềm, giải nén và chép
`HongThien_HaiQuan_Desktop.exe` đè lên file cũ cùng tên. Thư mục `DATA_LUU_TRU_HONG_THIEN` và `Tesseract-OCR` giữ nguyên.
Lần cài đầu tiên hoặc khi cần OCR trên máy mới thì dùng bản đầy đủ.

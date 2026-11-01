# KẾ HOẠCH THIẾT KẾ LẠI PHẦN MỀM HỒ SƠ HẢI QUAN HỒNG THIÊN

> Trạng thái: **bản kế hoạch, chưa triển khai**. Soạn ngày 01/11/2026.
> Đã chốt: dùng **PySide6 (Qt)** cho giao diện mới. Phần 2 (tính năng mới) làm sau Phần 1.

Dự án chia hai phần:
- **Phần 1:** phát triển lại từ hệ thống đang có: tách backend, thiết kế lại giao diện cho thân thiện.
- **Phần 2:** phát triển tính năng mới (lập kế hoạch sau, xem mục 5).

---

## 1. Vấn đề của giao diện hiện tại

1. **Quá tải trên một màn hình.** Tab Bước 1 có 3 hàng ô nhập, 10 ô chung một hàng, 8 nút xuất màu khác nhau và 1 nút sang Bước 2. Người dùng không biết nên làm gì trước.
2. **Nhãn dài, nhiều thuật ngữ.** Tiêu đề và tên nút viết theo kiểu kỹ thuật ("Bảo toàn 100% tính năng & công thức gốc", "SQLite + Hồ sơ Host").
3. **Ô nhập của từng khách bị trộn lẫn** (lô Tesa, đợt giao Shirai, tùy chọn Kodi, hạn thanh toán Best nằm chung một chỗ).
4. **Nút xuất rời rạc**, đánh số 1–8 không theo thứ tự công việc; nút hay dùng nhất ("Trọn bộ") nằm ở số 6.
5. **Không có chỉ dẫn tiến trình**, không cảnh báo trước khi xuất (thiếu số PXK, thiếu kg/ống… chỉ biết sau khi xuất).
6. **Bố cục cứng** (cửa sổ 1450×880, nhiều `pack` rời rạc), màn hình nhỏ bị tràn.
7. **Backend dính vào giao diện.** Lớp `HongThienCustomsDesktopApp` dài ~1.400 dòng, trộn logic nghiệp vụ với widget → khó thiết kế lại, khó test.

## 2. Nguyên tắc

- Giữ nguyên các ràng buộc: **100% offline**, **không cần Python trên máy người dùng**, **người dùng xác nhận trước khi lưu/xuất**, dữ liệu khách thật không đưa vào repo.
- **Không đổi kết quả xuất Excel và parser** trong Phần 1. Snapshot Excel hiện có (`tests/snapshots/`) là hàng rào an toàn.
- Mỗi bước là một PR nhỏ; chờ cả hai workflow `tests` và `build-exe` xanh rồi mới merge.
- Giao diện cũ (Tkinter) giữ chạy song song cho tới khi giao diện mới được người dùng chấp nhận.

## 3. Phần 1A: Tách backend khỏi giao diện

Làm trước, **không đổi hành vi**.

```
hongthien/
├── core/        # parser PO, xuất Excel (build_*_sheet), store (DedicatedDataStore), OCR
├── services/    # LotService (một lô: nạp PO, sửa dòng, tính, kiểm tra, xuất)
│                # ArchiveService (Bước 2: gắn file, lưu, tra cứu, sổ tổng hợp)
│                # SettingsService (thư mục dữ liệu, nạp danh mục ERP)
├── ui_tk/       # giao diện Tkinter cũ (tạm giữ)
└── ui_qt/       # giao diện PySide6 mới
hongthien_desktop_app.py   # file mỏng re-export mọi tên cũ để test/PyInstaller không vỡ
```

- Chuyển logic đang nằm trong các hàm giao diện (`build_current_step1_record`, `export_step1_excel`, `transfer_step1_to_step2`, `save_workbench_record`, `refresh_archive_table`…) sang `services/`, giao diện chỉ gọi.
- Thêm `LotService.validate()` trả về danh sách **lỗi** (chặn xuất) và **cảnh báo** (cho phép xuất) bằng tiếng Việt dễ hiểu, tái dùng `check_lot`. Ví dụ: thiếu số PXK, quy cách chưa có kg/ống, tổng SL các chứng từ lệch.
- Tiêu chí xong: toàn bộ test và snapshot hiện tại vẫn xanh, giao diện Tkinter cũ vẫn chạy bằng service mới.

## 4. Phần 1B: Giao diện mới bằng PySide6

### 4.1 Cấu trúc màn hình
Thanh bên trái (điều hướng), vùng làm việc ở giữa:

| Mục | Nội dung |
|---|---|
| **Làm chứng từ** | Luồng 4 bước (4.2) |
| **Hồ sơ đã lưu** | Tra cứu, mở lại, nạp về làm tiếp, xuất sổ tổng hợp (thay Bước 2 và bảng lưu trữ) |
| **Danh mục** | Thư viện cân nặng, danh mục ERP, danh mục theo khách |
| **Khách hàng** | Danh sách khách, nút "Thêm khách mới từ chứng từ mẫu" |
| **Cài đặt** | Thư mục dữ liệu / ổ mạng LAN, nạp danh mục ERP, kiểm tra OCR |

### 4.2 Luồng "Làm chứng từ" (thanh tiến trình ở trên)
```
① Chọn khách & nạp PO → ② Kiểm tra dòng hàng → ③ Thông tin chuyến hàng → ④ Xuất & lưu hồ sơ
```
- **①** Chọn khách bằng thẻ lớn. Nút lớn "Chọn file PO" hoặc kéo-thả file; "Dán văn bản PO" là lựa chọn phụ. Ô riêng của khách (lô Tesa, đợt giao Shirai, tùy chọn Kodi, "Thêm PO vào lô" cho Best) **chỉ hiện đúng khách đó**.
- **②** Bảng dòng hàng. Dòng thiếu kg/ống, OCR đáng ngờ hoặc SL×giá lệch thành tiền được tô màu kèm lời nhắc ngay trên dòng. Bấm đúp để sửa; hộp sửa có gợi ý "app sẽ nhớ cho lần sau".
- **③** Biểu mẫu nhóm theo ý nghĩa: "Chứng từ" (số PO, ngày, PXK, HĐ, tờ khai), "Vận chuyển" (xe, tài xế, LĐĐ), "Thanh toán/giao hàng" (Best). Mỗi ô có chú thích ngắn.
- **④** Bảng kiểm tra trước khi xuất (lỗi/cảnh báo từ `validate()`), một nút chính **"Xuất trọn bộ chứng từ"**, danh sách tích chọn nếu chỉ muốn vài file. Xong hiện màn hình kết quả với nút "Mở thư mục". Phần lưu hồ sơ nằm ngay tại đây.
- Tự lưu nháp, đóng app giữa chừng không mất lô đang làm.

### 4.3 Nguyên tắc trình bày
- Nhãn tiếng Việt ngắn, bỏ thuật ngữ kỹ thuật; cỡ chữ 10–11pt; một bảng màu thống nhất (lấy xanh đậm `#1B365D` hiện có làm màu chính).
- Bố cục co giãn theo cửa sổ (layout Qt), dùng được trên màn hình 1366×768.
- Thông báo lỗi nói rõ "chuyện gì xảy ra – làm gì tiếp", có nút "Mở file lỗi" (`LOI_PHAN_MEM.txt`).
- Việc chạy lâu (OCR, xuất Excel) chạy ở luồng nền, có thanh tiến trình, không làm treo cửa sổ.
- Bàn phím: Enter/Tab đi qua ô nhập đúng thứ tự; phím tắt cho "Chọn PO", "Xuất".

### 4.4 Rủi ro riêng của PySide6 và cách xử lý
| Rủi ro | Xử lý |
|---|---|
| .exe tăng từ ~65 MB lên khoảng 150–250 MB | Loại module Qt không dùng (`QtWebEngine`, `QtQml`…) trong PyInstaller; chấp nhận kích thước, nhắc người dùng |
| Phải viết lại toàn bộ UI | Làm sau khi tách `services/` (mục 3), chia nhỏ theo trang; Tkinter cũ chạy song song |
| PyInstaller + Qt trên Windows dễ thiếu plugin (`platforms/qwindows`) | Thêm kiểm tra `--gui-smoke` cho bản Qt vào `build_exe.py` và CI `build-exe` ngay từ PR đầu |
| Test giao diện | Dùng `pytest-qt` + `QT_QPA_PLATFORM=offscreen` trên CI Ubuntu, không cần xvfb |
| Cảnh báo antivirus/SmartScreen có thể nhiều hơn với .exe lớn | Ghi trong hướng dẫn; xem xét ký số (việc ưu tiên thấp trong tài liệu bàn giao) |
| Giấy phép | PySide6 theo LGPL: dùng được cho phần mềm nội bộ, vẫn cần kiểm tra lại trước khi phát hành ra ngoài công ty |

## 5. Trình tự thực hiện Phần 1 (mỗi dòng một PR)

| # | Việc | Tiêu chí xong |
|---|---|---|
| 1 | Chốt hành vi hiện tại: bổ sung test cho các luồng giao diện chưa phủ, rà snapshot | Test xanh, có danh sách luồng chuẩn |
| 2 | Tách package `core/`, giữ `hongthien_desktop_app.py` re-export | Test và snapshot cũ xanh không sửa |
| 3 | Tách `services/` (`LotService`, `ArchiveService`, `SettingsService`) + `validate()`; giao diện Tkinter cũ gọi qua service | Test xanh; thêm test cho `validate()` bằng dữ liệu giả |
| 4 | Khung PySide6: cửa sổ, điều hướng, thanh tiến trình; thêm PySide6 vào `requirements-*.txt`; `--gui-smoke` cho bản Qt; CI build thử | `build-exe` ra .exe mở được cửa sổ Qt trên Windows |
| 5 | Trang ① chọn khách + nạp PO (luồng nền cho OCR) | Nạp được PO của Shirai/Kodi/Tesa/khách đã học |
| 6 | Trang ② bảng dòng hàng + sửa dòng + tô cảnh báo | Sửa dòng, nhớ định mức hoạt động như cũ |
| 7 | Trang ③ biểu mẫu + trang ④ kiểm tra/xuất/lưu | Xuất ra Excel **giống hệt snapshot** |
| 8 | Hồ sơ đã lưu, Danh mục, Khách hàng (kể cả trình thêm khách mới), Cài đặt | Đủ tính năng của giao diện cũ |
| 9 | Cho người dùng (anh huy) dùng thử song song, ghi phản hồi, chỉnh | Người dùng xác nhận chạy ổn |
| 10 | Gỡ giao diện Tkinter, cập nhật hướng dẫn và tài liệu bàn giao | Chỉ còn một giao diện |

Mỗi PR gửi người dùng bản `.exe` từ Actions để dùng thử sớm từ PR #4 trở đi.

## 6. Phần 2: Tính năng mới (làm sau Phần 1)

Chưa có yêu cầu cụ thể. Cần thu thập từ người dùng, rồi xếp ưu tiên. Ứng viên đã có sẵn trong `docs/BAN_GIAO_DU_AN.md` mục 12.1:
- Mẫu Invoice riêng theo từng khách đã học.
- Hỗ trợ số kiện lẻ.
- Khóa ghi khi nhiều máy cùng lưu qua LAN.
- Sửa lỗi `xfail` (PLX dòng tổng cộng, số thành chữ ≥ 1.000 tỷ).
- Ký số file .exe.

Làm Phần 2 trên nền `services/` + giao diện mới để không phải sửa hai lần.

## 7. Việc cần quyết định / xác nhận

1. Chấp nhận .exe lớn hơn (khoảng 150–250 MB) khi dùng PySide6?
2. Người dùng thật (anh huy) có thể dùng thử từng bước từ PR #4 trở đi không?
3. Có vẫn cần giữ giao diện Tkinter cũ để dự phòng sau khi giao diện mới ra mắt, và giữ trong bao lâu?
4. Việc còn dở độ ưu tiên cao trong tài liệu bàn giao (hạn thanh toán Best 30/60 ngày, kg/ống Best mới, build lại .exe sau PR #10) làm trước hay song song với Phần 1?

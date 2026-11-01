# KẾ HOẠCH HOÀN CHỈNH: THIẾT KẾ LẠI PHẦN MỀM HỒ SƠ HẢI QUAN HỒNG THIÊN

> Phiên bản 2, ngày 01/11/2026. Trạng thái: **đã duyệt hướng đi, chưa viết code**.
> Thay thế bản 1 (10 PR). Bản này đã gộp các quyết định của chủ dự án và áp dụng nguyên tắc "làm ít code nhất mà đủ việc".

---

## 1. Mục tiêu và phạm vi

Dự án gồm hai phần:

| Phần | Nội dung | Trạng thái |
|---|---|---|
| **Phần 1** | Phát triển lại từ hệ thống đang có: tách backend, thiết kế lại giao diện cho thân thiện | Kế hoạch đầy đủ ở dưới |
| **Phần 2** | Phát triển tính năng mới | Làm sau Phần 1, danh sách yêu cầu chưa có (mục 9) |

**Tiêu chí thành công của Phần 1:**
1. Người dùng mới làm xong một lô hàng mà không cần hướng dẫn trực tiếp.
2. File Excel xuất ra **giống hệt** bản cũ (snapshot không đổi).
3. Anh huy dùng thử một lô thật trên bản mới, số liệu khớp bản cũ.
4. Vẫn 100% offline, một file .exe, người dùng xác nhận trước khi lưu hoặc xuất.

**Ngoài phạm vi Phần 1:** thêm khách mới, thêm mẫu chứng từ mới, đổi parser hoặc cách đọc OCR, đổi cấu trúc dữ liệu.

## 2. Các quyết định đã chốt

| # | Quyết định | Ghi chú |
|---|---|---|
| 1 | Giao diện mới dùng **PySide6 (Qt)** | .exe tăng từ ~65 MB lên ~150–250 MB, đã chấp nhận |
| 2 | Anh huy dùng thử từng bản | Mỗi PR gửi kèm .exe để thử, từ khi có khung PySide6 |
| 3 | Giữ giao diện Tkinter cũ chạy song song | Chỉ gỡ sau khi anh huy xác nhận bản mới ổn một lô thật |
| 4 | Hạn thanh toán Best do người làm hồ sơ tự nhập | App giữ ô "Hạn thanh toán", mặc định 60 ngày, sửa được từng lô; không cần quyết định thêm |
| 5 | Kg/ống của quy cách Best mới nhập sau qua giao diện | Không phải việc về code |
| 6 | Bản .exe sau PR #10 đã build xong | Build-exe lần chạy 24 (commit `35c6871`) xanh, có sẵn trong Actions |
| 7 | Làm ít code nhất mà đủ việc | Gộp bước tách backend, tái dùng hàm có sẵn (mục 4) |

## 3. Hiện trạng và vấn đề

Tóm từ khảo sát `hongthien_desktop_app.py` (~4.800 dòng, giao diện dòng 3245–4680):

1. Tab Bước 1 quá tải: 3 hàng ô nhập, 10 ô chung một hàng, 8 nút xuất màu khác nhau, 1 nút sang Bước 2.
2. Nhãn dài, nhiều thuật ngữ kỹ thuật.
3. Ô riêng của từng khách (lô Tesa, đợt giao Shirai, tùy chọn Kodi, hạn thanh toán Best) trộn chung một chỗ.
4. Nút "Trọn bộ" (hay dùng nhất) nằm ở vị trí số 6 trong 8 nút.
5. Không có chỉ dẫn tiến trình, không cảnh báo trước khi xuất.
6. Cửa sổ cố định 1450×880, nhiều `pack` rời rạc, màn hình nhỏ bị tràn.
7. Logic nghiệp vụ nằm lẫn trong các hàm giao diện (`build_current_step1_record`, `export_step1_excel`, `transfer_step1_to_step2`, `save_workbench_record`…).

## 4. Nguyên tắc thực hiện

- **Không đổi hành vi** của parser, OCR, hàm xuất Excel, cấu trúc dữ liệu. Snapshot Excel và 124 test hiện có là hàng rào.
- **Tái dùng** những gì đã có: `check_lot` làm bước kiểm tra trước khi xuất, `build_full_bundle` làm nút xuất trọn bộ, `DedicatedDataStore` làm kho dữ liệu.
- **Chỉ tách lớp mỏng** phần logic mà giao diện mới gọi; không dựng thêm tầng trừu tượng, không dời parser và hàm xuất.
- Mỗi PR: một nhánh riêng, mô tả tiếng Việt dễ hiểu, test chỉ dùng dữ liệu giả, chờ **cả `tests` và `build-exe` xanh** rồi mới merge.
- Không commit số liệu thật của khách. Giữ offline, giữ `Tesseract-OCR` cạnh .exe, giữ tessdata_fast 4.1.0.
- Không gỡ giao diện Tkinter trước khi anh huy xác nhận.

## 5. Kiến trúc đích

```
hongthien_desktop_app.py      # giữ nguyên tên và API cũ (test, PyInstaller dùng)
lot_service.py                # MỚI, lớp mỏng: các thao tác giao diện cần gọi
ui_qt/                        # MỚI: giao diện PySide6
    main_window.py            #   khung, thanh điều hướng, thanh tiến trình
    page_po.py                #   ① chọn khách + nạp PO
    page_items.py             #   ② bảng dòng hàng + sửa dòng
    page_info.py              #   ③ thông tin chuyến hàng
    page_export.py            #   ④ kiểm tra + xuất + lưu
    page_records.py           #   hồ sơ đã lưu
    page_catalog.py           #   danh mục (cân nặng, ERP, theo khách)
    page_customers.py         #   khách hàng + trình thêm khách mới
    page_settings.py          #   cài đặt (thư mục dữ liệu, ERP, kiểm tra OCR)
    theme.py                  #   màu, cỡ chữ, QSS dùng chung
```

`lot_service.py` chỉ chứa các hàm giao diện mới thật sự cần, lấy từ logic đang nằm trong lớp giao diện cũ:

| Hàm | Lấy từ | Việc |
|---|---|---|
| `load_po(path, customer, append)` | `scan_po_file_offline` | Đọc PO, trả danh sách dòng |
| `recalc(lot)` | `recalc_all_items` | Tính kiện, tịnh, cả bì |
| `validate(lot)` | `check_lot` | Trả lỗi (chặn xuất) và cảnh báo (cho xuất) bằng tiếng Việt |
| `export(lot, mode)` | `export_step1_excel` | Xuất Excel, trả danh sách file |
| `save_record(lot, zone)` | `save_workbench_record` | Lưu hồ sơ vào WORKING/ARCHIVE |
| `load_record(id)` | `load_selected_archive_to_step1` | Nạp lại hồ sơ cũ |

Giao diện Tkinter cũ chuyển sang gọi qua các hàm này luôn, nên bản cũ và bản mới dùng chung một đường xử lý và không lệch nhau.

## 6. Thiết kế giao diện mới

### 6.1 Điều hướng
Thanh bên trái:

| Mục | Nội dung |
|---|---|
| **Làm chứng từ** | Luồng 4 bước (6.2) |
| **Hồ sơ đã lưu** | Tra cứu, mở lại, nạp về làm tiếp, xuất sổ tổng hợp |
| **Danh mục** | Thư viện cân nặng, danh mục ERP, danh mục theo khách |
| **Khách hàng** | Danh sách khách, "Thêm khách mới từ chứng từ mẫu" |
| **Cài đặt** | Thư mục dữ liệu / ổ mạng LAN, nạp danh mục ERP, kiểm tra OCR |

### 6.2 Luồng "Làm chứng từ"
Thanh tiến trình: `① Chọn khách & nạp PO → ② Kiểm tra dòng hàng → ③ Thông tin chuyến hàng → ④ Xuất & lưu`

- **①** Chọn khách bằng thẻ lớn; nút lớn "Chọn file PO" hoặc kéo-thả; "Dán văn bản PO" là lựa chọn phụ. Ô riêng chỉ hiện đúng khách (lô Tesa, đợt giao Shirai, tùy chọn Kodi, "Thêm PO vào lô" cho khách gom nhiều PO). OCR chạy ở luồng nền, có thanh tiến trình.
- **②** Bảng dòng hàng. Dòng thiếu kg/ống, OCR đáng ngờ hoặc SL×giá lệch thành tiền được tô màu kèm lời nhắc ngay trên dòng. Bấm đúp để sửa; có gợi ý "app sẽ nhớ cho lần sau". Thêm, xóa, tính lại bì nằm cùng thanh công cụ.
- **③** Biểu mẫu chia nhóm: "Chứng từ" (số PO, ngày, PXK, HĐ, tờ khai), "Vận chuyển" (xe, tài xế, LĐĐ), "Thanh toán và giao hàng" (hạn thanh toán, ngày giao PGH, chỉ hiện với khách cần). Mỗi ô có chú thích ngắn.
- **④** Bảng kiểm tra từ `validate()`; một nút chính **"Xuất trọn bộ chứng từ"**; danh sách tích chọn nếu chỉ cần vài file; xong hiện kết quả với nút "Mở thư mục"; nút "Lưu hồ sơ" ngay tại đây.
- Tự lưu nháp lô đang làm, đóng app giữa chừng không mất.

### 6.3 Trình bày
- Nhãn tiếng Việt ngắn, không thuật ngữ kỹ thuật. Cỡ chữ 10–11pt. Màu chính giữ xanh đậm `#1B365D`. Bố cục co giãn, dùng được trên 1366×768.
- Lỗi nói rõ "chuyện gì xảy ra – làm gì tiếp", có nút mở `LOI_PHAN_MEM.txt`.
- Phím: Tab/Enter đi đúng thứ tự ô; phím tắt cho "Chọn PO" và "Xuất".
- Lấy nguyên tắc (bảng màu, chữ, khoảng cách, khả năng truy cập) từ các skill `ui-ux-pro-max` và `ui-design-system` đã có trong `.claude/skills/`; không sao chép phần dành cho web.

## 7. Trình tự thực hiện (7 PR)

| PR | Việc | Tiêu chí xong | Gửi anh huy |
|---|---|---|---|
| **A** | Tạo `lot_service.py`, chuyển giao diện Tkinter cũ gọi qua đó; thêm `validate()` bọc `check_lot`; thêm test cho `lot_service` bằng dữ liệu giả, gồm luồng lưu hồ sơ và nạp lại hồ sơ cũ (chỗ chưa có test) | 124 test + snapshot xanh không sửa; test mới xanh | Không cần |
| **B** | Khung PySide6: `main_window`, `theme`, điều hướng, thanh tiến trình; thêm `PySide6`, `pytest-qt` vào `requirements-dev.txt` và `requirements-build.txt`; `build_exe.py` + CI `build-exe`: loại module Qt không dùng, kiểm tra mở cửa sổ Qt trên Windows; cờ `--giao-dien-moi` để chạy thử | CI Windows xanh, .exe mở được cửa sổ Qt; bản cũ vẫn mặc định | **Có** (thử mở được trên máy thật) |
| **C** | Trang ① + ② + ④ (nạp PO, sửa dòng, kiểm tra, xuất, lưu) cho 5 khách; test `pytest-qt` ở chế độ `offscreen` | Xuất Excel từ giao diện mới **giống hệt snapshot** của Shirai, Kodi, Tesa và Best | **Có** (làm thử một lô thật) |
| **D** | Trang ③ biểu mẫu thông tin chuyến hàng; ô hiện/ẩn theo khách | Mỗi khách chỉ thấy ô cần; hạn thanh toán Best nhập được | Có |
| **E** | Hồ sơ đã lưu, Danh mục, Khách hàng (kể cả trình thêm khách mới), Cài đặt | Đủ tính năng của giao diện cũ | Có |
| **F** | Chạy song song, ghi phản hồi, chỉnh theo phản hồi, sửa lỗi; làm bản `.exe` ổn định, đăng Releases | Anh huy xác nhận một lô thật khớp bản cũ | **Có** |
| **G** | Đổi giao diện mới thành mặc định; gỡ Tkinter **chỉ khi anh huy đồng ý**; cập nhật `HUONG_DAN_*.md`, `BAN_GIAO_DU_AN.md`, `tests/README.md` | Chỉ còn một giao diện, tài liệu cập nhật | Có |

Thứ tự ưu tiên khi dồn việc: A → B → C là xương sống; D, E có thể đổi thứ tự.

## 8. Rủi ro và cách xử lý

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Bản Qt trên Windows lỗi riêng (thiếu plugin `platforms/qwindows`, không mở được cửa sổ) dù Linux xanh | Cao | PR B đưa kiểm tra mở cửa sổ trên Windows vào CI ngay đầu; gửi anh huy thử sớm |
| Tách lớp mỏng làm lệch hành vi ở chỗ ít test (lưu hồ sơ, nạp lại hồ sơ cũ) | Trung bình | PR A viết test cho đúng các luồng này trước khi chuyển |
| Người dùng đang dùng Tkinter hằng ngày, bản Qt lỗi gây gián đoạn | Trung bình | Giữ Tkinter chạy song song; chỉ đổi mặc định ở PR G |
| .exe 150–250 MB; SmartScreen/antivirus cảnh báo nhiều hơn | Thấp–Trung bình | Loại module Qt không dùng; ghi hướng dẫn "More info → Run anyway"; ký số (việc ưu tiên thấp) |
| Đổi giao diện làm đổi cách ghi dữ liệu | Thấp | Không đổi `DedicatedDataStore`; test so snapshot |
| OCR chạy ở luồng nền gây lỗi đồng bộ | Thấp | Chỉ đẩy việc OCR/xuất sang luồng nền, kết quả trả về luồng giao diện qua tín hiệu |
| Giấy phép PySide6 (LGPL) | Thấp | Dùng nội bộ công ty; kiểm tra lại trước khi phát hành ra ngoài |
| Skill ngoài (33 mục trong `.claude/skills/`) chạy script lạ | Thấp | Đã rà soát, loại hook/MCP/settings; chỉ dùng khi cần |

## 9. Phần 2: Tính năng mới (làm sau Phần 1)

**Chưa có yêu cầu cụ thể.** Việc cần làm khi Phần 1 xong:
1. Gom danh sách yêu cầu thật từ anh huy và nhân viên làm hồ sơ.
2. Với mỗi yêu cầu, ghi: ai cần, hiện đang làm thủ công thế nào, mất bao lâu, cách đo thành công.
3. Xếp ưu tiên, rồi lập kế hoạch riêng cho từng nhóm.

Ứng viên đã có sẵn trong `docs/BAN_GIAO_DU_AN.md` mục 12.1:

| Ứng viên | Ghi chú |
|---|---|
| Mẫu Invoice riêng theo từng khách đã học | Hiện dùng mẫu chuẩn |
| Hỗ trợ số kiện lẻ | Một số khách ghi kiện lẻ trên Invoice |
| Khóa ghi khi nhiều máy cùng lưu qua LAN | Hiện "lưu sau thắng" |
| Sửa lỗi `xfail` | PLX dòng "Tổng cộng" ghi đè dòng hàng cuối; `num_to_vn_words` sai từ 1.000 tỷ |
| Ký số file .exe | Giảm cảnh báo SmartScreen |
| Tách `hongthien_desktop_app.py` thành module | Sau khi bỏ Tkinter, file sẽ nhỏ đi nhiều |

Phần 2 chạy trên nền `lot_service.py` và giao diện mới, nên tính năng mới chỉ thêm một lần.

## 10. Việc vận hành song song (không thuộc Phần 1)

| Việc | Ai | Ghi chú |
|---|---|---|
| Tải bản .exe sau PR #10 và đưa anh huy dùng | Chủ dự án | Actions → build-exe → lần chạy 24 → artifact `HongThien_HaiQuan_Desktop_Windows` |
| Nhập kg/ống cho quy cách Best mới (1450–1800mm) | Người làm hồ sơ | Qua giao diện, mục danh mục khách Best |
| Chọn hạn thanh toán Best cho từng lô | Người làm hồ sơ | Ô "Hạn thanh toán" ở Bước 1 |

## 11. Quy tắc làm việc

- Mỗi thay đổi một nhánh + PR; mô tả tiếng Việt dễ hiểu; trả lời người dùng bằng tiếng Việt ngắn gọn, có link trực tiếp.
- Mỗi thay đổi parser hoặc mẫu Excel đi kèm test với **dữ liệu giả cùng cấu trúc**.
- Chờ cả `tests` và `build-exe` xanh rồi mới merge; nhắc người dùng điều này.
- Sau khi merge: báo link tải .exe mới (Actions → build-exe → artifact, hoặc Releases).
- Chỉ chạy `python run_tests.py --update-snapshots` khi **cố ý** đổi định dạng Excel, và xem lại diff.
- Cập nhật `docs/BAN_GIAO_DU_AN.md` khi kết thúc mỗi PR có thay đổi cấu trúc.

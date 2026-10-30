# Bộ kiểm thử Hồng Thiên

```bash
pip install -r requirements-dev.txt
python run_tests.py              # self-test của app + pytest (bỏ qua GUI)
python run_tests.py --gui        # thêm kiểm thử giao diện (cần Tkinter; Linux dùng xvfb-run)
python run_tests.py -k pkl       # tham số còn lại đưa thẳng cho pytest
python run_tests.py --update-snapshots   # ghi lại snapshot khi cố ý đổi định dạng Excel
```

Mọi test chạy trên thư mục dữ liệu tạm, không đụng `DATA_LUU_TRU_HONG_THIEN/` thật.

| File | Kiểm tra |
| :-- | :-- |
| `test_text_utils.py` | `clean_str`, `strip_accents_upper`, `num_to_vn_words` |
| `test_data_store.py` | Tự phục hồi catalog, JSON/SQLite, `remember_item_norm`, cây thư mục, đổi thư mục Host |
| `test_po_parsers.py` | Parser PO Kodi (suy ngược số lượng), Tesa (nhiều trang, bầu chọn), Shirai Excel (tách đợt giao, khớp ERP, xếp PNN) |
| `test_excel_exports.py` | 8 loại sheet; snapshot trọn bộ cho 3 khách (`tests/snapshots/`) |
| `test_customer_rules.py` | Hồ sơ từng khách, toàn vẹn catalog (206 / 1.833), quy tắc Kodi/Tesa/Shirai |
| `test_self_test.py` | `run_self_test()` và import được khi không có Tkinter |
| `test_gui_smoke.py` | Mở app, xuất trọn bộ, chuyển sang Bước 2 (đánh dấu `gui`) |

## xfail có chủ đích

Các test `xfail(strict=True)` ghi lại chỗ mã nguồn lệch tài liệu bàn giao hoặc lỗi đã biết.
Khi sửa xong, test báo XPASS: gỡ dấu xfail.

- PLX: dòng "Tổng cộng" ghi đè dòng hàng cuối và SUM bỏ sót nó.
- `num_to_vn_words` từ 1.000 tỷ trở lên.
- Tài liệu nói Kodi VAT 8%, mã đang xuất 0.
- Tài liệu nhắc `sort_shirai_pnn_order`, `fmt_vat_name`, `save_step2_archive`, 19 mặt hàng Kodi / 21 mã Tesa; mã hiện có khác.

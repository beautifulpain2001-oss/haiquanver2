# TÀI LIỆU BÀN GIAO DỰ ÁN – PHẦN MỀM HỒ SƠ HẢI QUAN HỒNG THIÊN

> Cập nhật: 01/11/2026, sau khi merge PR #10.
> Mục đích: người mới đọc xong tài liệu này có thể tự chạy, sửa, test, đóng gói và hỗ trợ người dùng mà không cần hỏi lại.
> Tài liệu này **không chứa số liệu thật của khách** (xem mục 11 về bảo mật).

---

## Mục lục
1. [Mục tiêu và bối cảnh nghiệp vụ](#1-mục-tiêu-và-bối-cảnh-nghiệp-vụ)
2. [Kiến trúc và cấu trúc thư mục](#2-kiến-trúc-và-cấu-trúc-thư-mục)
3. [Cài đặt, chạy, test, build .exe](#3-cài-đặt-chạy-test-build-exe)
4. [Luồng sử dụng trong app (Bước 1 → Bước 2)](#4-luồng-sử-dụng-trong-app-bước-1--bước-2)
5. [Luồng đọc chứng từ: PO, Invoice, OCR offline](#5-luồng-đọc-chứng-từ-po-invoice-ocr-offline)
6. [Học khách hàng mới và danh mục `master_catalog.json`](#6-học-khách-hàng-mới-và-danh-mục-master_catalogjson)
7. [Quy trình bộ hồ sơ khách Best (docSet `best`)](#7-quy-trình-bộ-hồ-sơ-khách-best-docset-best)
8. [Các quyết định thiết kế](#8-các-quyết-định-thiết-kế)
9. [Lịch sử thay đổi (PR #1 – #10)](#9-lịch-sử-thay-đổi-pr-1--10)
10. [Lỗi đã gặp và cách sửa](#10-lỗi-đã-gặp-và-cách-sửa)
11. [Bảo mật dữ liệu khách](#11-bảo-mật-dữ-liệu-khách)
12. [Việc còn dở và rủi ro](#12-việc-còn-dở-và-rủi-ro)
13. [Xử lý sự cố khi người dùng báo lỗi](#13-xử-lý-sự-cố-khi-người-dùng-báo-lỗi)
14. [Checklist cho người tiếp quản](#14-checklist-cho-người-tiếp-quản)

---

## 1. Mục tiêu và bối cảnh nghiệp vụ

**Công ty:** CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN (MST 2300723980, KCN Thuận Thành II, Bắc Ninh). Sản phẩm chính là **ống/lõi giấy** (và pallet gỗ cho Tesa) bán cho doanh nghiệp chế xuất (DNCX) trong các khu công nghiệp. Vì bán cho DNCX nên mỗi lô hàng phải làm **thủ tục hải quan xuất khẩu tại chỗ** (loại hình **B11**), thuế suất VAT **0%**.

**Vấn đề:** mỗi lô hàng nhân viên phải gõ tay cùng một bộ số liệu (PO, số lượng, đơn giá, số kiện, trọng lượng tịnh/cả bì) vào 6–10 chứng từ khác nhau. Gõ sai một con số là lệch giữa hóa đơn và tờ khai, rất tốn kém để sửa.

**Phần mềm làm gì:**
1. **Bước 1 – Làm chứng từ:** đọc PO của khách (PDF có chữ, PDF scan, ảnh, Excel), tự tính số kiện và trọng lượng theo định mức, rồi xuất ra Excel trọn bộ: Hóa đơn VAT (mẫu nhập Bkav), Phiếu xuất kho kiêm vận chuyển nội bộ (PXKKVCNB, Bkav), Invoice/Packing List, Đề nghị thanh toán (ĐNTT), Phụ lục X (PLX), Tờ khai B11 tham khảo, SO (Shirai), và với khách kiểu Best thêm Đóng gói, Phiếu giao hàng, Đối chiếu công nợ, file `dsh` để import vào ECUS.
2. **Bước 2 – Lưu trữ:** gắn các chứng từ đã phát hành (PDF/XML VAT, PXK, tờ khai, bản scan có dấu) vào hồ sơ, lưu theo cây thư mục chuẩn trên ổ máy chủ / ổ mạng LAN để nhiều máy cùng dùng.

**Ràng buộc bất biến (người dùng yêu cầu):**
- **100% offline**, không gửi file chứng từ ra Internet (kể cả OCR).
- **Không cần cài Python** trên máy người dùng: phát hành dạng file `.exe` Windows.
- **Người kiểm tra trước khi lưu/xuất**: app chỉ đề xuất, người dùng xác nhận. Không dùng machine learning, chỉ quy tắc và mẫu.

**Khách hàng hiện có:**

| Khách | Kiểu | Đầu vào PO | Ghi chú |
|---|---|---|---|
| Shirai | Có sẵn trong code (`PROFILES["shirai"]`) | Excel, nhiều đợt giao | Khớp mã ERP đầu `TM`, xếp PNN, xuất SO |
| Kodi | Có sẵn | PDF (có chữ hoặc scan) | Suy ngược số lượng từ thành tiền/đơn giá |
| Tesa | Có sẵn | PDF nhiều trang, PO ở trang chẵn | Nhiều PO một lô, có tờ khai B11, PLX, dòng pallet |
| Khách đã học (ABLE, ARIZON, Best…) | Học từ chứng từ mẫu, lưu trong `master_catalog.json` | PDF/ảnh/Excel/txt | Dùng parser chung `parse_generic_po_text` |
| Best (Best Pacific VN) | Khách đã học + **bộ mẫu `best`** | PDF scan hoặc PDF xuất từ ERP | Gom nhiều PO một lô, mẫu song ngữ Trung–Việt |

Người dùng chính (anh **huy**) viết tiếng Việt, không chuyên kỹ thuật. Trả lời bằng tiếng Việt, đưa link tải trực tiếp, tránh thuật ngữ.

---

## 2. Kiến trúc và cấu trúc thư mục

### 2.1 Tổng quan
- **Một file mã nguồn duy nhất:** `hongthien_desktop_app.py` (~4.800 dòng), Python 3.12 + **Tkinter** (giao diện Windows gốc, không dùng trình duyệt).
- Thư viện: `openpyxl` (đọc/ghi Excel), `pypdf` (đọc lớp chữ PDF), `pypdfium2` + `pillow` + `pytesseract` (OCR PDF scan/ảnh, tùy chọn).
- Dữ liệu: JSON + SQLite trong thư mục `DATA_LUU_TRU_HONG_THIEN/` **nằm cạnh file .exe/.py** (hoặc thư mục người dùng chọn trên ổ mạng LAN).
- Danh mục gốc (206 mã cân nặng, 1.833 mã ERP `TM…`) được **nhúng sẵn** trong code dưới dạng base64 + zlib (`EMBEDDED_MASTER_CATALOG_B64`, dòng ~45). Lần đầu chạy app tự giải ra `master_catalog.json`.

### 2.2 Cây thư mục repo

```
haiquanver2/
├── hongthien_desktop_app.py     # TOÀN BỘ app: hằng số, parser, xuất Excel, giao diện, self-test
├── build_exe.py                 # Đóng gói .exe bằng PyInstaller + chép Tesseract + tự kiểm tra
├── run_tests.py                 # Chạy self-test + pytest (một lệnh)
├── 1_CHAY_APP_DESKTOP.bat       # Chạy bằng Python trên Windows
├── 2_DONG_GOI_RA_FILE_EXE.bat   # Tự đóng gói .exe trên máy Windows có Python
├── HUONG_DAN_DESKTOP_APP.md     # Hướng dẫn người dùng (đọc trước)
├── HUONG_DAN_BAN_EXE.md         # Hướng dẫn bản .exe, đi kèm trong file zip (HUONG_DAN.txt)
├── requirements.txt             # openpyxl, pypdf
├── requirements-dev.txt         # + pytest, pillow, pytesseract, pypdfium2
├── requirements-build.txt       # + pyinstaller, pillow, pytesseract, pypdfium2
├── pyproject.toml               # cấu hình pytest (marker "gui")
├── .github/workflows/
│   ├── tests.yml                # Ubuntu: self-test + pytest + GUI smoke (xvfb) + OCR
│   └── build-exe.yml            # Windows: build .exe + self-test + OCR self-test + mở thử giao diện
├── tests/                       # pytest, xem tests/README.md
│   ├── conftest.py              # fixture thư mục dữ liệu tạm, không đụng dữ liệu thật
│   ├── snapshots/               # snapshot Excel trọn bộ cho shirai/kodi/tesa
│   └── test_*.py
└── docs/BAN_GIAO_DU_AN.md       # tài liệu này
```

### 2.3 Bản đồ `hongthien_desktop_app.py` (theo thứ tự trong file)

| Dòng (xấp xỉ) | Khối | Nội dung chính |
|---|---|---|
| 1–110 | Khởi tạo | import tùy chọn (pypdf, pdfium, pytesseract), `get_app_dir()`, tìm Tesseract (`BUNDLED_TESSERACT`), `ocr_available()` |
| 110–260 | Hằng số | Địa chỉ/MST Hồng Thiên, `DNTT_BANK`, **`PROFILES`** (shirai/kodi/tesa), dữ liệu mẫu Tesa, `DOC_SLOTS` (6 ô chứng từ Bước 2), danh mục mặc định Kodi/Tesa |
| 260–335 | Tiện ích chữ | `clean_str`, `strip_accents_upper`, `num_to_vn_words` (số thành chữ) |
| 336–700 | **`DedicatedDataStore`** | Thư mục dữ liệu, nạp/lưu catalog + records (JSON) + SQLite, `remember_item_norm`, `remember_item_refs`, `save_learned_customer`, `register_custom_profiles`, đổi thư mục Host |
| 699–770 | **Đọc file** | `auto_rotate_scan`, `extract_text_from_pdf_or_image_offline` (lớp chữ → OCR) |
| 771–1040 | Parser PO có sẵn | `parse_kodi_po_text`, `parse_tesa_po_page/_text`, `parse_shirai_po_excel` |
| 1040–1875 | Xuất Excel chuẩn | `build_vat_bkav_sheet`, `build_pxk_bkav_sheet`, `build_pkl_*`, `build_dntt_sheet`, `build_plx_sheet`, `build_customs_b11_sheet`, `build_so_shirai_sheet` |
| 1874–2490 | **Bộ mẫu Best** | `BEST_DOCSET_DEFAULTS`, `is_best_docset`, `lot_totals`, `check_lot`, `build_check_sheet`, `build_pkl_best_sheet`, `build_packing_best_sheet`, `build_pgh_best_sheet`, `build_dccn_best_sheet`, `build_dntt_best_sheet`, `build_ecus_dsh_sheet`, **`build_full_bundle`** |
| 2487–2970 | **Học khách mới** | `BUILTIN_CUSTOMERS`, `CUSTOM_PROFILE_DEFAULTS`, `learn_from_einvoice_xml`, `learn_from_invoice_excel`, `read_document_text`, `guess_po_number`, `infer_po_pattern`, `learn_customer_from_documents`, `build_custom_profile` |
| 2970–3235 | **Parser PO chung** | `_name_dims`, `_normalize_ocr_numbers`, `_qty_price_from_numbers`, `_loose_po_line` (OCR lỏng), **`parse_generic_po_text`** |
| 3237–4680 | **Giao diện** `HongThienCustomsDesktopApp` | Tab Bước 1, Bước 2, Danh mục cân nặng, Danh mục ERP; trình thêm khách mới; sửa dòng; xuất Excel; lưu trữ |
| 4679–4790 | Tự kiểm tra | `run_self_test`, `make_scanned_pdf`, `run_ocr_self_test`, `__main__` (cờ `--self-test`, `--ocr-self-test`, `--gui-smoke`) |

### 2.4 Dữ liệu khi chạy (`DATA_LUU_TRU_HONG_THIEN/`, không đưa lên git)

```
DATA_LUU_TRU_HONG_THIEN/
├── master_catalog.json          # danh mục: weights_db, erp_catalog, kodi_items, tesa_items,
│                                #   item_mem, custom_profiles, custom_items
├── hongthien_records.json       # danh sách hồ sơ (record) đã làm
├── hongthien_haiquan.db         # SQLite (bản sao để tra cứu)
└── HAI_QUAN/                    # MỘT thư mục gốc cho mọi hồ sơ hải quan
    └── <Tên gọi khách>/         #   vd Tesa, Kodi (lấy từ mục Khách hàng)
        └── <Năm>_Thang_<mm>/    #   vd 2026_Thang_11 (có rồi thì không tạo lại)
            └── <yyyy-mm-dd>/    #   ngày làm tờ khai; chứng từ xuất ra nằm trong đây
                                 #   cùng khách + cùng ngày + khác PO: thêm _2, _3…
```
`config_desktop.json` (cạnh .exe) lưu đường dẫn thư mục dữ liệu nếu người dùng đã chọn thư mục Host/LAN.

### 2.5 Cấu trúc một hồ sơ (record)
Tạo bởi `build_current_step1_record()`: `id` (`HS-yyyymmdd-KHACH-nn`), `zone` (`WORKING`/`ARCHIVE`), `customer`, `docDate`, `poNumber`, `poDate`, `poDates` (nhiều PO), `pxkNo`, `hdNo`, `tkNo`, `luong`, `xeNo`, `driver`, `lddSeq`, `payDays`, `deliveryDate`, các tổng (`totalQty/Amount/Net/Gross/Kien`), `items` (mỗi dòng: `po, code, name, ten_hq, unit, qty, price, amount, div, kg, kien, net, gross, hs, tare`, và với Best thêm `inquiry`, `customsNo`), `files` (6 ô chứng từ).

---

## 3. Cài đặt, chạy, test, build .exe

### 3.1 Chạy từ mã nguồn
```bash
pip install -r requirements.txt          # tối thiểu: openpyxl, pypdf
python hongthien_desktop_app.py          # mở giao diện
python hongthien_desktop_app.py --self-test      # xuất 3 file Test_Full_*.xlsx, không mở giao diện
python hongthien_desktop_app.py --ocr-self-test  # dựng PDF scan Kodi/Tesa rồi OCR lại
```
Trên Windows có thể bấm đúp `1_CHAY_APP_DESKTOP.bat`.

OCR khi chạy từ mã nguồn cần cài thêm `pip install pillow pytesseract pypdfium2` và chương trình Tesseract có tiếng Việt:
- Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-vie`
- Windows: cài Tesseract (UB Mannheim hoặc `choco install tesseract`), rồi chép `vie.traineddata` + `eng.traineddata` bản **tessdata_fast 4.1.0** vào `tessdata` (xem mục 10.3).

### 3.2 Test
```bash
pip install -r requirements-dev.txt
python run_tests.py              # self-test + pytest (bỏ qua GUI)
python run_tests.py --gui        # thêm test giao diện (Linux: xvfb-run -a python run_tests.py --gui)
python run_tests.py -k best      # lọc theo tên
python run_tests.py --update-snapshots   # CHỈ khi cố ý đổi định dạng Excel
```
- Mọi test chạy trên thư mục tạm, không đụng dữ liệu thật.
- `test_ocr.py` tự bỏ qua nếu máy không có Tesseract.
- Có vài test `xfail(strict=True)` ghi lại lỗi đã biết (xem `tests/README.md`). Khi sửa xong lỗi đó test sẽ báo XPASS và làm đỏ CI: gỡ dấu xfail.
- Danh sách file test và phạm vi: xem bảng trong `tests/README.md`.

### 3.3 CI (GitHub Actions)
| Workflow | Máy | Chạy khi | Làm gì |
|---|---|---|---|
| `tests` | ubuntu-latest | mọi push / PR | Cài python3-tk, xvfb, tesseract-ocr-vie → `xvfb-run -a python run_tests.py --gui` |
| `build-exe` | windows-latest | push `main`, tag `v*`, PR, chạy tay | `choco install tesseract` → tải tessdata_fast 4.1.0 (eng, vie) → `python build_exe.py` → upload artifact; tag `v*` hoặc chạy tay có chọn release thì đăng lên Releases |

**Quy tắc:** chờ **cả hai** workflow xanh rồi mới merge. Người dùng có thói quen merge sớm, nên luôn nhắc.

### 3.4 Build file .exe
- **Cách khuyến nghị:** để CI làm. Vào GitHub → tab **Actions** → workflow **build-exe** → mở lần chạy mới nhất trên `main` → tải artifact **`HongThien_HaiQuan_Desktop_Windows`** (zip ~65 MB, giữ 90 ngày). Hoặc trang **Releases** nếu đã đăng.
- **Phát hành bản chính thức:** đẩy tag `v1.x.y`, hoặc Actions → build-exe → **Run workflow** (để tick "Đăng bản build lên trang Releases").
- **Tự build trên Windows có Python:** chạy `2_DONG_GOI_RA_FILE_EXE.bat` (thêm `--no-ocr` nếu máy không có Tesseract).

`build_exe.py` làm các bước:
1. PyInstaller `--onefile --windowed`, loại `pytest`, `numpy`. Kiểm tra Tcl/Tk có mặt (thiếu thì .exe không mở được cửa sổ).
2. Chép bản gọn Tesseract (exe + DLL + `eng`, `vie`, `osd`) ra `dist/Tesseract-OCR/`.
3. Chép .exe sang thư mục tạm trống và chạy `--self-test` (phải sinh đúng 3 file `Test_Full_*.xlsx` cạnh .exe), `--ocr-self-test`, và trên Windows `--gui-smoke` (mở giao diện 3 giây rồi tự đóng).
4. Nén `dist/HongThien_HaiQuan_Desktop_Windows.zip` gồm .exe + `Tesseract-OCR/` + `HUONG_DAN.txt`.

**Cách người dùng cài:** giải nén zip vào thư mục cố định (ví dụ `D:\HongThien\`), **giữ thư mục `Tesseract-OCR` cạnh file .exe**, bấm đúp .exe. Windows SmartScreen cảnh báo vì .exe chưa ký số: "More info" → "Run anyway". Nâng cấp bản mới: chỉ thay file .exe và thư mục `Tesseract-OCR`, giữ nguyên `DATA_LUU_TRU_HONG_THIEN/` và `config_desktop.json`.

---

## 4. Luồng sử dụng trong app (Bước 1 → Bước 2)

### Bước 1 – Làm chứng từ
1. Chọn khách (hàng nút radio). Khách đã học xuất hiện ở đây sau khi lưu.
2. **Quét PO** (`scan_po_file_offline`): chọn file → app đọc chữ (mục 5) → điền số PO, ngày PO, dòng hàng. Với khách đã học có nút **"➕ Quét Thêm PO Vào Lô Này"** để gom nhiều PO.
   Không đọc được thì dùng **"Dán Văn Bản PO"** hoặc thêm dòng tay.
3. Kiểm tra/sửa dòng (**"✏️ Sửa Dòng"**, `open_item_editor_modal`): sửa định mức SL/kiện, kg/chiếc, HS, mã vật liệu… App **nhớ lại** định mức (`remember_item_norm`) và mã/Inquiry/Customs No (`remember_item_refs`) cho lần sau.
4. Điền số PXK, số HĐ, số tờ khai, luồng, xe, tài xế, số lệnh điều động; với Best thêm hạn thanh toán và ngày giao PGH.
5. Bấm nút xuất:

| Nút | `mode` | Kết quả |
|---|---|---|
| 1 | `VAT` | Hóa đơn VAT mẫu nhập Bkav |
| 2 | `PKL` | Invoice / Packing List |
| 3 | `PXK` | PXKKVCNB mẫu Bkav |
| 4 | `DNTT` | Đề nghị thanh toán |
| 5 | `PLX` | Phụ lục X |
| 6 | `ALL` | Trọn bộ (`build_full_bundle`), Best thì gồm cả mẫu riêng + KiemTra + dsh |
| 7 | `BEST` | Chỉ 4 mẫu riêng Best: Đóng gói, PGH, ĐCCN, ĐNTT |
| 8 | `DSH` | File `dsh_<PXK>.xlsx` để import ECUS |

File ra nằm ở `HAI_QUAN/<Khách>/<Năm>_Thang_<mm>/<Ngày>/` (hàm `DedicatedDataStore.get_record_folder_path`; hồ sơ lưu rồi giữ nguyên thư mục qua trường `folder`; hồ sơ từ bản cũ vẫn dùng thư mục kiểu cũ nếu còn trên máy).

### Bước 2 – Lưu trữ
Chuyển hồ sơ sang Bước 2 (`transfer_step1_to_step2`), gắn file vào 6 ô (`DOC_SLOTS`: PO, PXK, VAT, Invoice/PKL, Tờ khai+PLX, Bản scan có dấu), lưu vào `WORKING` hoặc `ARCHIVE`. App chép file vào cây thư mục `02_ARCHIVE_SAU_PHAT_HANH/...`. Có bảng tra cứu hồ sơ, nạp lại hồ sơ cũ về Bước 1, xuất sổ tổng hợp Excel.

### Dùng chung qua mạng LAN
Đặt thư mục dữ liệu trên máy chủ, các máy trạm bấm **"📂 Chọn Thư Mục Lưu Trữ Tập Trung"** và trỏ về đó (`change_base_dir`, lưu vào `config_desktop.json`). Dữ liệu chính là JSON để tránh lỗi khóa file SQLite qua SMB. **Không có cơ chế khóa ghi đồng thời**: hai máy cùng lưu một lúc thì bản lưu sau thắng (xem rủi ro mục 12).

---

## 5. Luồng đọc chứng từ: PO, Invoice, OCR offline

### 5.1 Đọc chữ từ file – `extract_text_from_pdf_or_image_offline(path, is_tesa, table_mode)`
```
Ảnh (.png/.jpg/.tif…)  ──► Tesseract (vie+eng) [table_mode: tự xoay + --psm 4]
PDF ──► với từng trang (tối đa 10; Tesa: chỉ trang chẵn 2,4,6…):
          ├─ table_mode: pypdf extract_text(extraction_mode="layout")   ← PR #10
          ├─ không được thì pypdf extract_text() thường
          ├─ nếu > 80 ký tự không trắng → dùng lớp chữ
          └─ nếu ít hơn (PDF scan) → pypdfium2 render ảnh (scale 2.5, Tesa/table 3.0)
                 → [table_mode: auto_rotate_scan bằng OSD] → Tesseract
                 → Tesa: OCR thêm dải tiêu đề (cắt 8.5–17.5% chiều cao, phóng 2x, lang=eng), nối sau "@@HDR@@"
Không có trang nào → giải mã thô latin1 làm phương án cuối
```
- `table_mode=True` dùng cho **khách đã học** (PO dạng bảng nhiều cột). Kodi/Tesa giữ cách đọc cũ vì parser của họ được tinh chỉnh theo đúng đầu ra cũ. **Không đổi cách đọc Kodi/Tesa** nếu không chạy lại toàn bộ test OCR.
- `read_document_text(path)` là cổng chung cho khách đã học: Excel → `excel_to_text`, .txt → đọc thẳng, PDF/ảnh → hàm trên với `table_mode=True`.

### 5.2 Parser PO từng khách
| Hàm | Khách | Ý chính |
|---|---|---|
| `parse_shirai_po_excel` | Shirai | Đọc Excel, tách theo đợt giao (schedule), khớp mã ERP `TM…` theo tên, xếp thứ tự PNN |
| `parse_kodi_po_text` | Kodi | Tìm số PO dạng `ddmmyyyy-nnKDHT`, khớp dòng theo tên trong `kodi_items`, suy ngược SL từ thành tiền ÷ đơn giá khi OCR làm hỏng SL |
| `parse_tesa_po_text` | Tesa | Mỗi trang chẵn là một PO `8600…`; bầu chọn giữa nhiều ứng viên số; khớp mã `397xx-9xxxx-00` |
| `parse_generic_po_text` | Khách đã học | Xem 5.3 |

Khi người dùng chọn khách có sẵn mà quét file, `scan_po_file_offline` còn **tự đoán**: Excel → Shirai; chữ có `8600` → Tesa; còn lại thử Kodi.

### 5.3 Parser chung `parse_generic_po_text(text, profile, catalog_items, data_store, tare_val)`
1. Số PO: theo regex học được (`poPattern`, sinh bởi `infer_po_pattern` từ một số PO mẫu), rơi về `guess_po_number`. Ngày PO: `find_po_date`.
2. Với từng dòng văn bản, tìm mặt hàng trong danh mục khách theo thứ tự:
   - **mã hàng** (cho phép sai 1 chữ số do OCR),
   - **tên hàng**,
   - **quy cách + định lượng** (ví dụ `38*5*467` + `250g`, hàm `_name_dims`/`_dims_regex`).
   Nhiều mặt hàng cùng khớp thì chọn mặt hàng có **đơn giá gần nhất**.
3. Lấy SL và đơn giá (`_qty_price_from_numbers`, có chuẩn hóa số OCR bị tách `_normalize_ocr_numbers`).
4. **Chế độ OCR lỏng** (`ocrLoose`, bật cho bộ mẫu Best): `_loose_po_line` nhận hàng theo **chiều dài** (ví dụ `1350MM`) rồi kiểm **SL × đơn giá = thành tiền** để chọn đúng bộ số; lấy Inquiry No (`QS…`), Customs No (`PackingF…`), mã vật liệu.
5. Tính kiện = SL ÷ định mức (`div`), tịnh = SL × kg, cả bì = tịnh + bì (`tare`, Best: 1 kg/dòng).

### 5.4 Đọc Invoice Excel và hóa đơn XML (khi học khách mới)
- `learn_from_einvoice_xml`: XML hóa đơn VAT/PXK theo TT78 → tên công ty, MST, địa chỉ, email, mã/tên hàng, ĐVT, đơn giá; PXK thì lấy kho nhận, lái xe, biển xe, ký hiệu.
- `learn_from_invoice_excel`: đọc **mọi sheet**, sheet có **ngày mới nhất thắng** (`_sheet_date`); tìm dòng tiêu đề (`INVOICE_HEADER_KEYS`); suy ra SL/kiện = SL ÷ số kiện, kg/chiếc = N.W ÷ SL, bì từng dòng = gross − net; đọc bảng "Số lượng ống / 1 túi" (`_learn_norm_table`); lấy số PO từ dòng `Số ĐĐH`; **bỏ qua dòng bị ẩn**; đọc tên/MST người mua (`_learn_party_from_sheet`).

### 5.5 Gói OCR
- Engine: **Tesseract** (Apache 2.0), ngôn ngữ `vie+eng`, `osd` để tự xoay trang.
- Bản .exe ưu tiên `Tesseract-OCR\tesseract.exe` cạnh .exe và **ép `TESSDATA_PREFIX`** về thư mục đó để không bị bản Tesseract khác trên máy chen vào. Chạy mã nguồn thì tìm trong PATH rồi các vị trí cài mặc định trên Windows.
- Thiếu OCR thì app vẫn chạy, chỉ báo không đọc được PDF scan.

---

## 6. Học khách hàng mới và danh mục `master_catalog.json`

### 6.1 Trình "🧠 Thêm Khách Mới Từ Chứng Từ Mẫu" (`open_learn_customer_wizard`)
1. Người dùng chọn nhiều file mẫu: XML hóa đơn VAT, XML PXK, Invoice Excel, PO mẫu (PDF/ảnh/Excel/txt).
2. `learn_customer_from_documents(paths)` gọi từng bộ đọc ở mục 5.4, gộp kết quả (`merge_learned_docs`), đoán số PO mẫu (**ưu tiên số PO trong cột PO của Invoice**, PR #7), và trả về bản nháp `{profile, items, meta, errors}`.
3. Cửa sổ xem lại: sửa mã khách (không dấu, `customer_key_from_name`), tên, MST, địa chỉ, ĐVT, **Bộ mẫu chứng từ** (`chuan` hoặc `best`; tên có "BEST PACIFIC" thì tự chọn `best`), số PO mẫu, xóa/sửa dòng hàng. Nút **"🔍 Thử đọc PO mẫu"** chạy parser ngay trên PO mẫu.
4. **Chỉ khi bấm "💾 Lưu Khách Hàng Mới"** thì `save_learned_customer` mới ghi vào catalog. Trước đó không có gì được lưu.

### 6.2 Lưu ở đâu
`master_catalog.json` trong thư mục dữ liệu:

| Khóa | Nội dung |
|---|---|
| `weights_db` | 206 mã định mức cân nặng (dữ liệu gốc) |
| `erp_catalog` | 1.833 mã thương mại ERP đầu `TM` (`ten_sp`, `ma_sp`), dùng khớp Shirai |
| `kodi_items`, `tesa_items` | Danh mục hàng Kodi/Tesa (đơn giá, `div` SL/kiện, `kg`, mã, HS, `ten_hq`, `tare`) |
| `item_mem` | Định mức người dùng đã sửa, theo tên hàng |
| `custom_profiles` | Hồ sơ khách đã học: tên, MST, địa chỉ, ĐVT, `poPattern`, `docSet`, khối `customs`, … |
| `custom_items` | Danh mục hàng của từng khách đã học (thêm `code`, `inquiry`, `customsNo` đã nhớ) |

Lúc nạp, `register_custom_profiles` đưa khách đã học vào `PROFILES` (qua `build_custom_profile` + `CUSTOM_PROFILE_DEFAULTS`) để mọi mẫu xuất dùng chung. **shirai/kodi/tesa (`BUILTIN_CUSTOMERS`) không bao giờ bị ghi đè** bởi khách đã học.

File `master_catalog.json` trong thư mục chung của project là bản danh mục gốc (206 / 1.833, chưa có khách đã học), giống bản nhúng trong code.

### 6.3 Thêm khách mới: làm thế nào cho đúng
- **Dùng cơ chế học**, không viết cứng khách mới vào `PROFILES` hay viết parser riêng, trừ khi mẫu PO quá đặc thù.
- Nếu khách cần mẫu chứng từ riêng, làm như Best: thêm một giá trị `docSet` mới + bảng mặc định + các hàm `build_*_sheet`, rồi nối vào `build_full_bundle`.
- **Test chỉ dùng dữ liệu giả cùng cấu trúc.**

---

### 6.4 Khách đặt một mã hàng cố định (kiểu Sunlu)
- Hồ sơ khách có `fixedItem` (mã hàng cố định) hoặc `docStyle: "sunlu"` (hoặc tên có SUNLU): bước ② không đọc file PO mà hiện ô **Xác nhận đơn hàng**: số PO 3 phần (tiền tố + ngày + số thứ tự), ngày PO, số lượng, đơn giá.
- Số PO theo `poGen`, ví dụ `YNCGDD{yymmdd}{nnnn}`: số thứ tự = lớn nhất đã dùng cùng ngày + 1 (`next_po_parts`). Sửa tay được từng phần.
- Đơn giá điền sẵn = giá của hồ sơ gần nhất của khách (`last_fixed_order`), chưa có hồ sơ thì giá trong danh mục.
- Bộ chứng từ: Invoice, Hóa đơn VAT, Phiếu xuất kho (Bkav, không ghi PO), Đơn đặt hàng, Biên bản giao nhận, Bảng đối chiếu hàng hóa theo tháng (mã `BDC`, gộp mọi hồ sơ cùng tháng), Phụ lục X dạng văn bản. Không có ĐNTT.
- Dữ liệu khách (tên, MST, mã hàng, giá) nằm trong file dữ liệu học `khach_sunlu_hoc.json` ở thư mục file chung, không nằm trong repo. Test dùng dữ liệu giả (`tests/test_fixed_order.py`).

## 7. Quy trình bộ hồ sơ khách Best (docSet `best`)

Tài liệu nghiệp vụ đầy đủ (có số liệu thật, **không đưa vào repo**): `best/QUY_TRINH_BO_HO_SO_BEST.md` trong thư mục file chung của project. Tóm tắt quy tắc:

### 7.1 Thứ tự chứng từ
```
PO của Best (PDF scan hoặc PDF xuất từ ERP; có Item Code, Spec, SL, giá, Inquiry No, PR No, Customs No)
 ├─ (1) Lệnh điều động LĐĐ<ddmmyyyy>-<stt>
 ├─ (2) PXKKVCNB (Bkav, ký hiệu 6C26NAA)  → số PXK dùng làm "số hóa đơn" trên tờ khai
 ├─ (3) Hóa đơn GTGT (Bkav), PO theo từng dòng
 ├─ (4) Invoice – Bảng kê chi tiết         ┐ cùng SL, kg/ống, N.W, G.W, số kiện
 ├─ (5) Chi tiết đóng gói (không giá, TTR) ┘
 ├─ (6) dsh_<PXK>.xlsx → import ECUS
 ├─ (7) Tờ khai B11 (khai trên ECUS)
 ├─ (8) Phiếu giao hàng song ngữ (XKTLGH-yyMMdd)
 ├─ (9) Đối chiếu công nợ song ngữ
 └─ (10) Đề nghị thanh toán mẫu Best (請款單)
```

### 7.2 Quy tắc tính (đã cài trong `BEST_DOCSET_DEFAULTS`, `lot_totals`)
- **20 ống / kiện** cố định; số kiện = tổng SL ÷ 20.
- Tịnh = SL × kg/ống (định mức theo quy cách). Cả bì = tịnh + **1 kg mỗi dòng**.
- ĐVT `ống` (VAT/PXK/INV), `PIP` (tờ khai, dsh), `Ống` (PGH). HS `48229090`.
- **Nhiều PO một lô**, mỗi dòng giữ PO của nó. Cùng quy cách ở 2 PO là **2 dòng riêng**, không gộp.
- Tờ khai B11: mã nhóm **4822**, đích bảo thuế **03PJCPJ**, "Số hóa đơn" = **`B - <số PXK>`**, ký hiệu và số hiệu = `P/O: <PO1> + <PO2>`.
- PGH: cột "Số đơn đặt hàng" chứa **Inquiry No**, còn số PO nằm ở cột "Số đơn xin mua"; ghi chú = Customs No.
- ĐCCN/ĐNTT: ngày yêu cầu thanh toán = ngày hóa đơn + **N ngày** (mặc định 60, sửa được ở Bước 1, ô "Hạn thanh toán").
- Mã vật liệu (Item Code) **không ghi lên VAT/INV**, chỉ dùng trên PGH và ĐCCN.

### 7.3 Cách làm trong app
1. Thêm khách bằng trình học, với Invoice Excel cũ của Best; chọn bộ mẫu `best`; điền tên tiếng Trung, người liên hệ cho ĐCCN.
2. Bước 1: quét PO thứ nhất, rồi **"➕ Quét Thêm PO Vào Lô Này"** cho các PO còn lại.
3. Lần đầu: sửa mã vật liệu / Inquiry / Customs No bị OCR đọc sai ở "✏️ Sửa Dòng"; app nhớ cho lần sau.
4. Quy cách mới chưa có trong danh mục (ví dụ một chiều dài mới) phải **thêm vào danh mục kèm kg/ống**, nếu không tịnh = 0 và sheet KiemTra sẽ cảnh báo.
5. Nút 6 xuất trọn bộ + sheet **KiemTra** (`check_lot`: đối chiếu tổng SL, kiện, tịnh, cả bì, tiền giữa các chứng từ; báo quy cách thiếu kg/ống) + file dsh.

---

## 8. Các quyết định thiết kế

| Quyết định | Lý do |
|---|---|
| Một file `.py` duy nhất | Có sẵn từ đầu; dễ đóng gói PyInstaller và dễ chép cho người dùng. Tách module là việc nên làm sau, nhưng phải giữ `import hongthien_desktop_app as app` cho test. |
| Tkinter, không web | Yêu cầu offline, không trình duyệt, chạy được trên máy văn phòng cũ. |
| JSON là nguồn dữ liệu chính, SQLite phụ | JSON chép/đồng bộ qua ổ mạng LAN an toàn hơn, tránh lỗi khóa file SQLite qua SMB. |
| Danh mục gốc nhúng base64 trong code | Bản .exe chạy được ngay trên máy mới, không cần chép thêm file. |
| Học khách mới bằng **quy tắc + mẫu**, không ML | Offline, giải thích được, chạy nhanh; chứng từ hải quan sai rất tốn kém nên **người dùng phải xác nhận** trước khi lưu. |
| Khách đã học dùng chung `PROFILES` và các hàm xuất | Không phải viết lại mẫu Excel cho mỗi khách. |
| Tesseract thay vì RapidOCR/EasyOCR | Parser Kodi/Tesa đã tinh chỉnh theo đầu ra Tesseract; gói nhỏ hơn; có tiếng Việt. |
| **tessdata_fast 4.1.0 cho cả eng và vie** | Trộn vie bản thường với eng bản fast làm Tesseract 5.5 trên Windows mất dấu tiếng Việt (mục 10.3). |
| Thư mục `Tesseract-OCR` nằm **cạnh** .exe, không nhúng vào onefile | Tesseract là chương trình ngoài, gọi qua subprocess; giữ .exe nhỏ, dễ thay. |
| Dữ liệu cạnh .exe (`get_app_dir()` dùng `sys.executable` khi frozen) | Bản onefile giải nén vào thư mục tạm; nếu lưu theo `__file__` thì dữ liệu mất sau mỗi lần tắt app. |
| `table_mode` chỉ cho khách đã học | Không làm thay đổi kết quả đã ổn định của Kodi/Tesa. |
| Đọc PDF có chữ theo **layout** cho khách đã học (PR #10) | PDF xuất từ ERP vẽ cột tên/quy cách riêng; đọc thường làm tách quy cách khỏi dòng hàng. |
| OCR lỏng cho Best: nhận theo chiều dài + kiểm SL×giá=thành tiền | Mã hàng/Inquiry trên scan Best rất nhiễu; chiều dài và phép nhân là tín hiệu đáng tin nhất. |
| Lỗi nút bấm ghi ra `LOI_PHAN_MEM.txt` + hộp thoại | Bản `--windowed` không có console; trước đây lỗi chỉ "chớp rồi tắt". |
| VAT 0% cho mọi khách | Hàng bán cho DNCX. Chỗ tài liệu cũ ghi Kodi 8% là sai (đã có test khẳng định 0%). |
| Test chỉ dùng dữ liệu giả | Chứng từ thật của khách là bí mật (mục 11). |

---

## 9. Lịch sử thay đổi (PR #1 – #10)

| PR | Ngày | Nội dung |
|---|---|---|
| (gốc) | 30/10/2026 | Đưa mã nguồn app desktop lên repo |
| #1 | 30/10 | Bộ test pytest, `run_tests.py`, CI `tests`, snapshot Excel 3 khách; khẳng định VAT 0% |
| #2 | 30/10 | Học khách mới từ chứng từ mẫu (XML hóa đơn/PXK, Invoice Excel, PO) |
| #3 | 30/10 | Đóng gói .exe không cần Python (`build_exe.py`, CI `build-exe`) |
| #4 | 30/10 | Đóng gói kèm Tesseract OCR (vie+eng) để đọc PDF scan |
| #5 | 30/10 | Sửa OCR mất dấu trên Windows: dùng tessdata_fast 4.1.0 cho cả eng và vie |
| #6 | 30/10 | Bỏ bước chẩn đoán OCR tạm thời khỏi build |
| #7 | 30/10 | Sửa cửa sổ thêm khách bị che; ghi lỗi nút bấm ra file; đọc PO scan khách mới (tự xoay, `--psm 4`, số PO lấy từ Invoice) |
| #8 | 31/10 | Bộ hồ sơ Best: nhiều PO/lô, Đóng gói, PGH, ĐCCN, ĐNTT mẫu khách, tờ khai B11 theo khách, dsh ECUS, sheet KiemTra |
| #9 | 31/10 | Merge đồng bộ `main` |
| #10 | 01/11 | Đọc PO PDF có lớp chữ (xuất từ ERP) theo bố cục trang; PO Best từ 0 dòng lên 11/11 dòng |

Xem chi tiết từng PR trên GitHub (tab Pull requests, trạng thái Closed).

---

## 10. Lỗi đã gặp và cách sửa

### 10.1 PO Best dạng PDF xuất từ ERP đọc ra 0 dòng (PR #10)
- **Triệu chứng:** PO Best dạng PDF có sẵn chữ (không phải scan) chỉ nhận được những dòng có mã vật liệu đã được nhớ; mã mới ra 0 dòng.
- **Nguyên nhân:** `pypdf.extract_text()` chế độ thường đọc cột Tên hàng và Quy cách (`KT:ø40*4*1800MM`) thành một khối riêng, dồn xuống cuối trang, tách khỏi dòng có SL/giá. Parser chung không còn ghép được quy cách với dòng hàng.
- **Sửa:** trong `extract_text_from_pdf_or_image_offline`, khi `table_mode=True` đọc bằng `extract_text(extraction_mode="layout")` trước, lỗi hoặc rỗng mới quay về cách thường. Test giả lập trong `tests/test_best_docset.py`.
- **Kết quả:** đọc đủ 11/11 dòng, tổng tiền khớp Grand Total, lấy được Inquiry No và Customs No.
- **Còn lưu ý:** quy cách chưa có trong danh mục Best vẫn phải thêm kèm kg/ống.

### 10.2 Cửa sổ "Thêm khách mới" hiện lên rồi biến mất (PR #7)
- Trên Windows, sau hộp chọn file thì cửa sổ chính bị kéo lên trước, che cửa sổ con. Sửa bằng `new_dialog()`: `Toplevel` + `transient(root)` + `lift()` + `focus_force`. Dùng `self.new_dialog()` cho **mọi** cửa sổ con mới.

### 10.3 OCR trên Windows mất hết dấu tiếng Việt (PR #4 → #5)
- Trộn `vie.traineddata` bản thường (~7,7 MB) với `eng` bản fast làm Tesseract 5.5 bỏ dấu. Sửa: CI tải **tessdata_fast 4.1.0** cho **cả** eng và vie (giống gói `tesseract-ocr-vie` trên Ubuntu mà test dùng). Kiểm tra bằng `--ocr-self-test`.

### 10.4 Bản .exe dùng nhầm Tesseract khác trên máy
- Nếu máy có Tesseract cài sẵn (thiếu tiếng Việt) và biến `TESSDATA_PREFIX`, OCR hỏng. Sửa: khi có `Tesseract-OCR` cạnh .exe, app đặt `tesseract_cmd` và ép `TESSDATA_PREFIX` về đó.
- Chocolatey tạo "shim" `tesseract.exe` trong PATH không có DLL bên cạnh, nên `build_exe.py` tìm `C:\Program Files\Tesseract-OCR` **trước** PATH.

### 10.5 PO khách mới scan bị xoay ngang (ARIZON) và PO tiếng Trung (ABLE) (PR #7)
- Thêm `auto_rotate_scan` (OSD, chỉ xoay khi `orientation_conf ≥ 2`), OCR `--psm 4` cho bảng, ưu tiên số PO từ Invoice để học mẫu số PO.

### 10.6 Lỗi "chớp rồi tắt" không để lại dấu vết (PR #7)
- Bản `--windowed` không có console. Thêm `report_error` (gán vào `root.report_callback_exception`) ghi traceback vào `LOI_PHAN_MEM.txt` cạnh .exe và hiện hộp thoại. Self-test lỗi ghi vào `SELF_TEST_LOI.txt`.

### 10.7 .exe không mở được cửa sổ
- PyInstaller lặng lẽ bỏ Tkinter nếu máy build thiếu Tcl/Tk. `build_exe.py` gọi `tkinter.Tcl()` trước khi build và CI chạy `--gui-smoke`.

### 10.8 Lỗi đã biết, chưa sửa (test `xfail`)
- PLX: dòng "Tổng cộng" ghi đè dòng hàng cuối và `SUM` bỏ sót dòng đó.
- `num_to_vn_words` sai từ 1.000 tỷ trở lên.
- Tài liệu cũ nhắc tên hàm/số mặt hàng không còn đúng (`sort_shirai_pnn_order`, `fmt_vat_name`, `save_step2_archive`, 19 mặt hàng Kodi / 21 mã Tesa).

---

## 11. Bảo mật dữ liệu khách

- Người dùng yêu cầu **bảo mật nghiêm ngặt** chứng từ thật của khách (đặc biệt bộ Best). **Không commit** file thật, số PO thật, giá, định mức, tên tiếng Trung, số tài khoản của khách vào repo.
- Test dùng **dữ liệu giả cùng cấu trúc** (`FAKE_NAME`, PO `POS2699900xx`…).
- Mẫu của khách thật (ABLE, ARIZON, Best) chỉ nằm trên máy người dùng và trong thư mục file chung của project; tài liệu nghiệp vụ Best có số thật ở `best/QUY_TRINH_BO_HO_SO_BEST.md` (thư mục chung, không phải repo).
- Thông tin của chính Hồng Thiên và 3 khách có sẵn (Shirai/Kodi/Tesa) đã nằm trong code từ đầu; đừng mở rộng thêm.
- Không dùng dịch vụ OCR/AI trực tuyến cho chứng từ.

---

## 12. Việc còn dở và rủi ro

### 12.1 Việc còn dở
| # | Việc | Ưu tiên | Ghi chú |
|---|---|---|---|
| 1 | **Xác nhận hạn thanh toán Best: 30 hay 60 ngày** | Cao | PO ghi 30 ngày sau nghiệm thu, ĐCCN/ĐNTT mẫu ghi 60 ngày từ ngày hóa đơn. App đang để mặc định 60, sửa được. Chờ anh huy xác nhận. |
| 2 | Bổ sung kg/ống cho các quy cách Best mới (ví dụ các chiều dài 1450–1800mm) vào danh mục khách Best trên máy người dùng | Cao | Thiếu thì tịnh = 0, KiemTra cảnh báo. Làm qua giao diện, không qua code. |
| 3 | Build lại .exe sau PR #10 và gửi người dùng | Cao | Tải từ Actions → build-exe của commit merge PR #10. |
| 4 | Mẫu Invoice riêng theo từng khách đã học (ví dụ "INVOICE - PACKING LIST" của ABLE) | Trung bình | Hiện khách đã học dùng mẫu chuẩn. |
| 5 | Số kiện lẻ (phân số) như trên Invoice của một số khách | Trung bình | Chưa hỗ trợ. |
| 6 | Sửa các lỗi `xfail` (PLX tổng cộng, số thành chữ ≥ 1.000 tỷ) | Trung bình | Sửa xong thì gỡ `xfail`. |
| 7 | Tách `hongthien_desktop_app.py` thành module (parser, export, store, ui) | Thấp | Giữ API cũ cho test và PyInstaller. |
| 8 | Ký số file .exe | Thấp | Để bớt cảnh báo SmartScreen/antivirus; cần chứng thư số. |
| 9 | Khóa ghi khi nhiều máy cùng lưu qua LAN | Thấp–Trung bình | Hiện "lưu sau thắng". |

### 12.2 Rủi ro
- **OCR sai số**: luôn để người dùng soát số PO, SL, giá trước khi xuất; sheet KiemTra chỉ đối chiếu nội bộ, không kiểm được số đọc sai từ PO. Scan dưới 200 dpi hoặc nghiêng nhiều thì lỗi tăng.
- **Mẫu PO của khách thay đổi** (khách đổi ERP, đổi bố cục): parser có thể ra 0 dòng. Cách xử lý: lấy PO mới, chạy `read_document_text` + `parse_generic_po_text`, xem văn bản đọc được, sửa, thêm test bằng **dữ liệu giả cùng bố cục**.
- **Thay đổi cách đọc PDF/OCR ảnh hưởng mọi khách**: chạy đủ `test_ocr.py`, `test_po_parsers.py`, `test_learn_customer.py`, `test_best_docset.py` trên máy có Tesseract (CI Ubuntu có sẵn) và chờ build Windows xanh.
- **Đổi định dạng Excel** làm snapshot đỏ: chỉ chạy `--update-snapshots` khi đã cố ý đổi, và xem lại diff snapshot.
- **Dữ liệu LAN ghi đè nhau** khi hai máy lưu cùng lúc.
- **Merge trước khi CI Windows xong**: đã từng xảy ra; build Windows lâu hơn test Ubuntu nhiều phút.
- **Phiên bản Tesseract trên Chocolatey thay đổi**: nếu CI build đột nhiên hỏng OCR, kiểm tra phiên bản và dữ liệu tessdata trước.
- **Artifact Actions chỉ giữ 90 ngày**: bản cần lưu lâu thì đăng Releases (tag `v*`).
- **Toàn bộ logic trong một file lớn**: sửa chỗ này dễ ảnh hưởng chỗ khác; dựa vào test.

---

## 13. Xử lý sự cố khi người dùng báo lỗi

| Người dùng nói | Làm gì |
|---|---|
| "Bấm nút thì chớp rồi tắt" / báo lỗi | Xin file `LOI_PHAN_MEM.txt` cạnh file .exe. |
| "Không đọc được PO" | Xin file PO (giữ bí mật). Xác định: PDF có chữ hay scan, khách nào. Chạy `read_document_text` để xem văn bản, rồi parser tương ứng. |
| "PDF scan không đọc được gì" | Kiểm tra thư mục `Tesseract-OCR` còn nằm cạnh .exe không; chạy `HongThien_HaiQuan_Desktop.exe --ocr-self-test`. |
| "Mất dữ liệu sau khi cập nhật" | Thường do giải nén bản mới ra thư mục khác. Chép `DATA_LUU_TRU_HONG_THIEN/` và `config_desktop.json` sang cạnh .exe mới. |
| "Windows chặn file" | SmartScreen: More info → Run anyway; antivirus: thêm thư mục vào ngoại lệ. |
| "Tịnh/cả bì bằng 0" | Mặt hàng chưa có kg/chiếc (hoặc kg/ống): sửa dòng và điền, app nhớ cho lần sau. |
| "Số liệu lệch giữa các chứng từ" (Best) | Xem sheet KiemTra trong file xuất trọn bộ. |

Cách tái hiện nhanh trong Python:
```python
import hongthien_desktop_app as app
store = app.DedicatedDataStore(base_dir="/tmp/data_thu")   # thư mục tạm, không đụng dữ liệu thật
text = app.read_document_text("po.pdf")
prof = app.PROFILES["<ma_khach>"]
print(app.parse_generic_po_text(text, prof, store.items_for_customer("<ma_khach>"), store))
```
(Cần chép `master_catalog.json` của người dùng vào thư mục tạm nếu muốn dùng danh mục khách đã học của họ.)

---

## 14. Checklist cho người tiếp quản

**Ngày đầu**
- [ ] Đọc `HUONG_DAN_DESKTOP_APP.md`, `HUONG_DAN_BAN_EXE.md`, `tests/README.md` và tài liệu này.
- [ ] Có quyền ghi repo `beautifulpain2001-oss/haiquanver2`, xem được tab Actions.
- [ ] Có quyền đọc thư mục file chung của project (`best/QUY_TRINH_BO_HO_SO_BEST.md`, `master_catalog.json`).
- [ ] Clone repo, `pip install -r requirements-dev.txt`, cài Tesseract + tiếng Việt.
- [ ] Chạy `python run_tests.py --gui` (Linux: `xvfb-run -a …`) – tất cả phải xanh (trừ `xfail` có chủ đích).
- [ ] Chạy `python hongthien_desktop_app.py`, thử: chọn Kodi → nạp mẫu → xuất trọn bộ → chuyển Bước 2.
- [ ] Tải bản .exe mới nhất từ Actions → build-exe, giải nén, chạy `--self-test` và `--ocr-self-test`.

**Tuần đầu**
- [ ] Thử trình thêm khách mới với dữ liệu giả trong `tests/test_learn_customer.py` / `tests/test_best_docset.py`.
- [ ] Đọc kỹ `extract_text_from_pdf_or_image_offline`, `parse_generic_po_text`, `build_full_bundle`, `check_lot`.
- [ ] Hỏi anh huy: hạn thanh toán Best 30 hay 60 ngày (mục 12.1 #1).
- [ ] Xác nhận anh huy đã dùng bản .exe build sau PR #10 và đã thêm kg/ống cho quy cách Best mới.

**Quy tắc làm việc**
- [ ] Mỗi thay đổi một nhánh + PR; mô tả bằng tiếng Việt dễ hiểu.
- [ ] Thêm/sửa test cho mọi thay đổi parser hoặc mẫu Excel; **chỉ dữ liệu giả**.
- [ ] Chờ **cả `tests` và `build-exe` xanh** rồi mới merge; nhắc người dùng điều này.
- [ ] Sau khi merge: báo người dùng link tải .exe mới (Actions → build-exe → artifact, hoặc Releases).
- [ ] Không gửi chứng từ thật ra dịch vụ ngoài; không commit file/số liệu thật.
- [ ] Giữ app 100% offline; giữ `Tesseract-OCR` cạnh .exe; giữ tessdata_fast 4.1.0 cho cả eng và vie.
- [ ] Không thay đổi cách đọc Kodi/Tesa nếu không có lý do và test OCR đầy đủ.
- [ ] Trả lời người dùng bằng tiếng Việt, ngắn gọn, có link trực tiếp.

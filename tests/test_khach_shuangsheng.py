"""PO Shuangsheng (scan song ngữ Việt/Hán, không ghi mã hàng, chỉ ghi quy cách 78*6*1005mm):
đọc đủ mọi dòng, kể cả quy cách chưa học."""

import hongthien_desktop_app as app

# Chữ OCR thật của PO 19112026-01 HT-SS (Tesseract vie+eng --psm 4): dòng 01 hỏng quy cách, quy cách nằm ở dòng chữ Hán ngay dưới
OCR = """ĐƠN ĐẶT HÀNG
Số 4ð-#ˆ : 19112026-01 HT-SS
STT Tên Hàng DVT | S.Lượng | Don Giá | Thành tiền | Ghi chú
FF e5 #t #2 | x# #? BBP ik
| Ong lõi giấy quy cách Cái
01 785610018 ya | 2000 | 32.119 | 64.238.000
DRS BLAS 78*ó*1005mm Chất lượng
Ông lõi giây quy cách Cái ống như
02 78%6% 1022mm ie 500 32.662 | 16.331.000| mẫu đã
RAS Ã #L4& 78*6*1 022mm gửi. "À VIETNA
Tả ORS # /ñ My,
Sue ste 80.569.000 | ying ag | N ng
VAT0% gị emir
Tong mm 80.569.000
- Đường kính trong P84: + 1 mm
- Độ dày FH : +0.5 mm
- Chiều dài KH : +2mm
Thời gian giao hàng 3š $f HY l]: 26/11/2026
"""

CAT = [{"name": "Ống lõi giấy 78 x 6 x 1002mm", "code": "", "price": 32023, "div": 5, "kg": 1.366, "unit": "Cái"},
       {"name": "Ống lõi giấy 78 x 6 x 1030mm", "code": "", "price": 33000, "div": 5, "kg": 0, "unit": "Cái"}]
PROF = {"po_pattern": r"\d{8}-\d{2}\s*HT-SS", "unit": "Cái"}


def test_rows_read_with_spec_from_chinese_line():
    rows = app.parse_spec_po_rows(OCR)
    assert [(r["dims"], r["qty"], r["price"], r["amount"]) for r in rows] == [
        (["78", "6", "1005"], 2000, 32119, 64238000), (["78", "6", "1022"], 500, 32662, 16331000)]


def test_unlearned_specs_named_like_learned_items():
    _po, _d, old = app.parse_generic_po_text(OCR, PROF, CAT)
    assert old == []  # trước đây: quy cách chưa học -> không ra dòng nào
    lines = app.lines_from_spec_rows(app.parse_spec_po_rows(OCR), "19112026-01HT-SS", PROF, CAT)
    assert [(x["ten_sp"], x["qty"], x["price"], x["amount"], x["read"]) for x in lines] == [
        ("Ống lõi giấy 78 x 6 x 1005mm", 2000, 32119, 64238000, "suy_ra"),
        ("Ống lõi giấy 78 x 6 x 1022mm", 500, 32662, 16331000, "suy_ra")]
    assert all(x["kg"] == 0 and x["kien"] == 0 for x in lines)  # kg/ống, SL/kiện để người dùng điền, không đoán


def test_learned_spec_keeps_learned_numbers():
    cat = CAT + [{"name": "Ống lõi giấy 78 x 6 x 1005mm", "code": "", "price": 32119, "div": 5, "kg": 1.37, "unit": "Cái"}]
    lines = app.lines_from_spec_rows(app.parse_spec_po_rows(OCR), "P", PROF, cat)
    assert (lines[0]["read"], lines[0]["div"], lines[0]["kien"], lines[0]["kg"]) == ("ok", 5, 400, 1.37)


def test_lot_load_po_reads_all_rows(store, tmp_path, monkeypatch):
    store.save_learned_customer("shuangsheng", {"name": "CÔNG TY TNHH VẬT LIỆU MỚI SHUANGSHENG VIETNAM", "label": "Shuangsheng",
                                                "mst": "4601622355", "addr": "TN", "unit": "Cái", "po_pattern": PROF["po_pattern"]}, CAT)
    pdf = tmp_path / "PO_19112026_HT-SS.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(app, "read_document_text", lambda path, force_ocr=False: OCR)
    monkeypatch.setattr(app, "_pdf_has_text", lambda path: True)
    res = app.lot_load_po(store, str(pdf), "shuangsheng")
    assert res["ok"] and res["po"] == "19112026-01HT-SS"
    assert [(x["ten_sp"][-6:], x["qty"]) for x in res["items"]] == [("1005mm", 2000), ("1022mm", 500)]


def test_bilingual_learned_po_still_reads_by_catalog():
    """PO cũ có quy cách đã học: kết quả như trước (không thêm dòng chữ Hán lặp)."""
    text = ("Số 28102026-01 HT-SS\nOng lõi giấy quy cách Cái\n01 | 78*6*1002mm 18 2000 32.023 64.046.000\n"
            "Z4 BLAS 78%6*1002mm__|\nÔng lõi giấy quy cách Cái\n02 | 78*6*1030mm ez 200 33.000 6.600.000 | mau đã\nRRS BF ALA 78*6*1030mm h-\n")
    rows = app.parse_spec_po_rows(text)
    assert [(r["dims"][2], r["qty"], r["price"]) for r in rows] == [("1002", 2000, 32023), ("1030", 200, 33000)]
    lines = app.lines_from_spec_rows(rows, "P", PROF, CAT)
    assert [x["read"] for x in lines] == ["ok", "ok"]

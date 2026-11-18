"""Khách ÍT MÃ HÀNG (cờ hồ sơ `pickItems`, kiểu Inoac): PO scan không ghi mã hàng, OCR hay đọc hỏng quy cách/đơn giá.
- Đọc PO: nhận dòng theo đơn giá đã học + chiều dài trong quy cách, đối chiếu SL x giá = thành tiền và dòng Tổng cộng.
- Không đọc được: người dùng tích chọn mã trong danh mục khách (bước ②), nhập SL, giá.
- Hóa đơn VAT / PXK Bkav: mỗi mã hàng một chứng từ (`bkavPerItem`), VAT ghi Số PR ở cột UDD_PO (`vatPoField: pr`).

Toàn bộ dữ liệu ở đây là DỮ LIỆU GIẢ (tên công ty, MST, mã hàng, giá, số PO đều bịa).
"""

import openpyxl
import pytest

import hongthien_desktop_app as app
from ui_qt.state import Lot

FAKE = {
    "name": "CHI NHÁNH CÔNG TY TNHH ÍT MÃ MẪU THỬ", "label": "ItMa", "mst": "0100000077-001", "addr": "Lô Y, KCN Mẫu, Phường Thử, Thành phố Hải Phòng, Việt Nam",
    "emails": "a@vd.test;b@vd.test", "province": "Thành phố Hải Phòng", "unit": "Chiếc", "tare": 1.0, "payDays": 30, "linePo": True, "poInDocs": True,
    "veViec": "", "po_pattern": app.infer_po_pattern("AB-XYZ-260901"), "bkavId": "hd itma {d},{m}", "bkavPerItem": True, "vatPoField": "pr", "pickItems": True,
}
ITEMS = [
    {"code": "50x5x400", "name": "Ống giấy (kích thước: phi 50 x 5 x 400 mm)", "ten_hq": "Ống giấy (kích thước: phi 50 x 5 x 400 mm; Hàng mới 100%)",
     "unit": "Chiếc", "price": 11110, "div": 10, "kg": 0.5, "hs": "48229090"},
    {"code": "50x8x1200", "name": "Ống giấy (kích thước: phi 50 x 8 x 1200 mm)", "ten_hq": "Ống giấy (kích thước: phi 50 x 8 x 1200 mm; Hàng mới 100%)",
     "unit": "Chiếc", "price": 77700, "div": 5, "kg": 2.5, "hs": "48229090"},
]

# Chữ OCR giả theo đúng kiểu lỗi đã gặp trên PO scan thật: dòng 1 hỏng quy cách và đọc 1 thành 4 ở đơn giá + thành tiền
PO_TEXT = """PURCHASE ORDER
No.: AB-XYZ-260901
Issue Date /Ngày phát hành. 16-Sep-2026
1 Ong lõi giấy IKioh tước: g(6:8*44890mimi Pcs VND ASPS 1,000.00 41,110.00 41,110,000 |  260916-QQ-02 IVC-1
Paper core Loại giấy: T3
lồng lõi giấy Kích thước:g50.6x8x1200mm E
2 Pe bore Low gáy: Tổ Pcs VND ASPS 500.00 77,700.00 38,850,000 | 260916-QQ-02 IVC-1
Total /Tẳng. | [ 4,500,00 49,960,000.00 +
VAT (if any) /Thué VAT (nếu có) 0.00
C Grand Total /Tông cộng| 49,960,000.00
"""


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def cust(store):
    return store.save_learned_customer("itma", dict(FAKE), [dict(x) for x in ITEMS])


def test_profile_keeps_empty_ve_viec(cust):
    prof = app.PROFILES[cust]
    assert app.is_pick_items(prof) and prof["veViec"] == ""  # PXK 'Về việc' chỉ ghi tên khách
    assert app.lot_bundle_modes({"customer": cust}) == ["PKL", "VAT", "PXK"]


def test_find_po_date_english_month():
    assert app.find_po_date("Issue Date /Ngày phát hành. 16-Sep-2026") == "16/09/2026"
    assert app.find_po_date("Date 3 Oct 2026") == "03/10/2026"


def test_parse_few_items_by_price_and_length():
    rows = app.parse_few_items_po(PO_TEXT, ITEMS, "AB-XYZ-260901")
    assert [(r["code"], r["qty"], r["price"], r["pr"], r["read"]) for r in rows] == [
        ("50x5x400", 1000, 11110, "260916-QQ-02", "suy_ra"),  # đơn giá đọc hỏng 1 chữ số: lấy giá đã học
        ("50x8x1200", 500, 77700, "260916-QQ-02", "ok"),
    ]
    assert "giá đã học" in rows[0]["read_note"]


def test_parse_few_items_does_not_take_row_number_as_qty():
    txt = "1 Ong giay Kich thuoc: 50x5x400mm Pcs VND 2,000.00 11,110.00 22,220,000"
    rows = app.parse_few_items_po(txt, ITEMS)
    assert [(r["code"], r["qty"], r["read"]) for r in rows] == [("50x5x400", 2000, "ok")]


def test_parse_few_items_new_price_needs_length():
    txt = "2 Ong giay Kich thuoc: 50x8x1200mm Pcs VND 100.00 80,000.00 8,000,000"
    rows = app.parse_few_items_po(txt, ITEMS)
    assert [(r["code"], r["qty"], r["price"], r["read"]) for r in rows] == [("50x8x1200", 100, 80000, "suy_ra")]
    assert app.parse_few_items_po("Ong giay Pcs VND 100.00 80,000.00 8,000,000", ITEMS) == []  # giá lạ + không thấy chiều dài: không đoán


def test_load_po_total_confirms_learned_price(store, cust, tmp_path):
    f = tmp_path / "po.txt"
    f.write_text(PO_TEXT, encoding="utf-8")
    res = app.lot_load_po(store, str(f), cust, "1.0")
    assert res["ok"] and res["po"] == "AB-XYZ-260901" and res["po_date"] == "16/09/2026"
    got = [(x["ma_sp"], x["qty"], x["price"], x["kien"], x["net"], x["gross"], x["pr"], x["read"]) for x in res["items"]]
    assert got == [("50x5x400", 1000, 11110, 100, 500.0, 501.0, "260916-QQ-02", "ok"),  # tổng PO khớp: dòng đọc hỏng giá đã được xác nhận
                   ("50x8x1200", 500, 77700, 100, 1250.0, 1251.0, "260916-QQ-02", "ok")]
    assert res["items"][0]["ten_hq"].endswith("Hàng mới 100%)")
    assert "✅" in res["msg"]


def test_load_po_unreadable_returns_po_for_picker(store, cust, tmp_path):
    f = tmp_path / "po.txt"
    f.write_text("PURCHASE ORDER\nNo.: AB-XYZ-260902\n16-Sep-2026\n####  260917-QQ-01\n", encoding="utf-8")
    res = app.lot_load_po(store, str(f), cust, "1.0")
    assert not res["ok"] and (res["po"], res["po_date"], res["pr"]) == ("AB-XYZ-260902", "16/09/2026", "260917-QQ-01")


def test_pick_items_in_lot(store, cust):
    lot = Lot(app, store)
    lot.select_customer(cust)
    assert lot.pick_items
    assert [(c["code"], c["price"]) for c in lot.pick_choices()] == [("50x5x400", 11110), ("50x8x1200", 77700)]
    with pytest.raises(ValueError, match="tích ít nhất"):
        lot.confirm_pick([], "AB-XYZ-260901")
    with pytest.raises(ValueError, match="số lượng"):
        lot.confirm_pick([("50x8x1200", "", "77700")], "AB-XYZ-260901")
    with pytest.raises(ValueError, match="số PO"):
        lot.confirm_pick([("50x8x1200", "10", "77700")], "")
    items = lot.confirm_pick([("50x8x1200", "500", "77,700")], "AB-XYZ-260901", "16/09/2026", "260916-QQ-02")
    it = items[0]
    assert (it["ma_sp"], it["qty"], it["price"], it["kien"], it["gross"], it["po"], it["pr"], it["read"]) == (
        "50x8x1200", 500, 77700, 100, 1251.0, "AB-XYZ-260901", "260916-QQ-02", "tay")
    assert lot.form["po"] == "AB-XYZ-260901" and lot.form["po_date"] == "16/09/2026"


def test_bkav_one_document_per_item(store, cust, tmp_path):
    f = tmp_path / "po.txt"
    f.write_text(PO_TEXT, encoding="utf-8")
    res = app.lot_load_po(store, str(f), cust, "1.0")
    rec = app.lot_build_record(store, {"customer": cust, "doc_date": "2026-09-25", "po": res["po"], "pxk": "00000254", "ldd": "02",
                                       "xe": "99C-000.00", "driver": "Lái Xe Thử"}, res["items"])
    wb = openpyxl.Workbook()
    vat = app.build_vat_bkav_sheet(wb, rec)
    pxk = app.build_pxk_bkav_sheet(wb, rec)
    assert [(vat.cell(r, 1).value, vat.cell(r, 2).value, vat.cell(r, 4).value, vat.cell(r, 24).value) for r in (6, 7)] == [
        (1, "hd itma 25,9 400", "260916-QQ-02", "a@vd.test;b@vd.test"),
        (1, "hd itma 25,9 1200", "260916-QQ-02", "a@vd.test;b@vd.test"),
    ]
    assert [(pxk.cell(r, 1).value, pxk.cell(r, 3).value, pxk.cell(r, 4).value, pxk.cell(r, 13).value, pxk.cell(r, 16).value) for r in (3, 4)] == [
        (1, "hd itma 25,9 400", "AB-XYZ-260901", "LĐĐ25092026-02", FAKE["name"]),
        (1, "hd itma 25,9 1200", "AB-XYZ-260901", "LĐĐ25092026-03", FAKE["name"]),
    ]
    pkl = app.build_pkl_standard_sheet(wb, rec)
    assert pkl["B13"].value.endswith("Hàng mới 100%)") and pkl["C13"].value == "AB-XYZ-260901" and pkl["I14"].value == "=ROUNDUP(E14/5,0)"

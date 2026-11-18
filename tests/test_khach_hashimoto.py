"""Khách ít mã hàng có MÃ HÀNG RIÊNG trên PO scan (kiểu Hashimoto, cờ `pickItems`):
- OCR làm mất cột SL / đơn giá của ô bảng: thấy mã hàng (VD 'Code AB123456') thì SL = thành tiền / giá đã học, dòng vàng.
- 'Code ...' trong tên hàng không bị coi là chiều dài quy cách.
- Mã IDChungTu riêng cho PXK (`bkavIdPxk`), PXK không ghi số PO (`pxkPo: false`), hóa đơn VAT vẫn ghi.

Toàn bộ dữ liệu ở đây là DỮ LIỆU GIẢ (tên công ty, MST, mã hàng, giá, số PO đều bịa).
"""

import openpyxl
import pytest

import hongthien_desktop_app as app

FAKE = {
    "name": "CÔNG TY TNHH MÃ RIÊNG MẪU THỬ", "label": "MaRieng", "mst": "0100000088", "addr": "Lô Z, KCN Mẫu, Phường Thử, Tỉnh Ninh Bình, Việt Nam",
    "emails": "a@vd.test", "province": "Tỉnh Ninh Bình", "unit": "Chiếc", "tare": 1.0, "linePo": True, "poInDocs": True, "veViec": "xuất kho cho",
    "po_pattern": app.infer_po_pattern("11ABCD-123"), "bkavId": "HD MR {dd}{mm}", "bkavIdPxk": "MR {d}.{m}", "pxkPo": False, "pickItems": True,
}
ITEMS = [
    {"code": "40x2x300", "name": "Ống giấy phi 40 x 2 x 300mm", "unit": "ống", "price": 3000, "div": 10, "kg": 0.1, "hs": "48229090"},
    {"code": "AB123456", "name": "Ống lõi giấy 30x0.5x200mm ,màu trắng(Code AB123456)", "unit": "Chiếc", "price": 1500, "div": 150, "kg": 0.02, "hs": "48229090"},
]

# OCR thật của PO kiểu này: ô SL / ĐVT / đơn giá bị mất, chỉ còn mã hàng và thành tiền
PO_TEXT = """DON ĐẶT HÀNG
Ngày: 30/9/2026
SBIR Giao hàng về Nhà máy PO No: 11ABCD-123
Người nhận hàng; Mr A Tel: 0900000000
Ong lõi giấy Code AB123456
+ Đường kính trong: 30mm
+ Dài : 200mm (†-lmm)
+ Dày: 0.5mm (+-0.1mm) f K 15,000,000
Màu trắng cả mặt trong và ngoài.
TOTAL (VND) 15,000,000
"""


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def cust(store):
    return store.save_learned_customer("marieng", dict(FAKE), [dict(x) for x in ITEMS])


def test_item_length_ignores_customer_code():
    assert app._item_length({"code": "AB123456", "name": ITEMS[1]["name"]}) == "200"
    assert app._item_length({"code": "76.5x5x595"}) == "595"


def test_po_without_qty_column_reads_by_code():
    rows = app.parse_few_items_po(PO_TEXT, ITEMS, "11ABCD-123")
    assert [(r["code"], r["qty"], r["price"], r["read"]) for r in rows] == [("AB123456", 10000, 1500, "suy_ra")]
    assert "thành tiền" in rows[0]["read_note"]
    assert app.parse_few_items_po("Ong loi giay Code AB123457\nDai 200mm 1,234,567", ITEMS) == []  # không chia hết cho giá: không đoán


def test_load_po_by_code(store, cust, tmp_path):
    f = tmp_path / "po.txt"
    f.write_text(PO_TEXT, encoding="utf-8")
    res = app.lot_load_po(store, str(f), cust, "1.0")
    assert res["ok"] and res["po"] == "11ABCD-123" and res["po_date"] == "30/09/2026"
    it = res["items"][0]
    assert (it["ma_sp"], it["qty"], it["kien"], it["net"], it["gross"], it["read"]) == ("AB123456", 10000, 67, 200.0, 201.0, "suy_ra")


def test_bkav_ids_and_pxk_without_po(store, cust):
    items = app.lot_pick_items(store, cust, [("AB123456", "10000", "1500")], "11ABCD-123")
    rec = app.lot_build_record(store, {"customer": cust, "doc_date": "2026-10-06", "po": "11ABCD-123", "pxk": "00000318", "ldd": "01",
                                       "xe": "99C-000.00", "driver": "Lái Xe Thử"}, items)
    assert app.get_vat_and_pxk_ids(rec) == ("HD MR 0610", "MR 6.10")
    wb = openpyxl.Workbook()
    vat = app.build_vat_bkav_sheet(wb, rec)
    pxk = app.build_pxk_bkav_sheet(wb, rec)
    assert (vat["B6"].value, vat["D6"].value) == ("HD MR 0610", "11ABCD-123")
    assert (pxk["C3"].value, pxk["D3"].value, pxk["M3"].value, pxk["P3"].value) == ("MR 6.10", "", "LĐĐ06102026-01", "xuất kho cho " + FAKE["name"])


def test_bkav_id_pxk_defaults_to_vat_id(store):
    key = store.save_learned_customer("cungma", {k: v for k, v in FAKE.items() if k != "bkavIdPxk"}, [dict(ITEMS[0])])
    assert app.get_vat_and_pxk_ids({"customer": key, "docDate": "2026-10-06", "items": []}) == ("HD MR 0610", "HD MR 0610")

"""Khách đặt MỘT mã hàng cố định (kiểu Sunlu): không đọc PO, chỉ xác nhận số PO / SL / giá; số PO = tiền tố + ngày + số thứ tự;
bộ chứng từ: Invoice, Hóa đơn VAT, Phiếu xuất kho, Đơn đặt hàng, Biên bản giao nhận, Bảng đối chiếu hàng hóa, Phụ lục X.

Toàn bộ dữ liệu ở đây là DỮ LIỆU GIẢ (tên công ty, MST, mã hàng, giá đều bịa).
"""

import datetime

import openpyxl
import pytest

import hongthien_desktop_app as app
from ui_qt.state import Lot

FAKE = {
    "name": "CÔNG TY TNHH MỘT MÃ MẪU THỬ", "label": "MotMa", "mst": "0100000099", "addr": "Lô X, KCN Mẫu, Xã Thử, Thành phố Hải Phòng, Việt Nam",
    "unit": "chiếc", "tare": 1.0, "payDays": 30, "docStyle": "sunlu", "poGen": "ABCDE{yymmdd}{nnnn}", "fixedItem": "90000001", "bbghSuffix": "MM",
}
ITEMS = [
    {"code": "11110000", "name": "Ống lõi giấy phi 50 x 55 x 40mm (11110000)", "unit": "chiếc", "price": 900, "div": 50, "kg": 0.03, "hs": "48229090"},
    {"code": "90000001", "name": "Ống lõi giấy phi 50 x 55 x 40mm (90000001)", "unit": "chiếc", "price": 1000, "div": 50, "kg": 0.03, "hs": "48229090"},
]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def cust(store):
    return store.save_learned_customer("motma", dict(FAKE), [dict(x) for x in ITEMS])


def make_rec(store, cust, po, qty, price, doc_date="2026-10-09", **form):
    items = app.lot_fixed_order_items(store, cust, po, qty, price, "1.0")
    f = {"customer": cust, "doc_date": doc_date, "po": po, "po_date": "19/09/2026", "pxk": "00000279", "hd": "00003964", "tk": "300000000001"}
    f.update(form)
    return app.lot_build_record(store, f, items)


def test_po_gen_split_three_parts():
    d = datetime.date(2026, 9, 19)
    assert app.po_gen_split("ABCDE{yymmdd}{nnnn}", d) == ("ABCDE", "260919", 4)
    assert app.po_gen_split("HT{yyyymm}{nn}", d) == ("HT", "202609", 2)
    assert app.po_gen_split("HT", d) is None
    assert app.po_gen_format({"poPrefix": "ABCDE"}) == "ABCDE{yymmdd}{nnnn}"  # file học cũ chỉ có tiền tố


def test_profile_flags_and_bundle(cust):
    prof = app.PROFILES[cust]
    assert app.is_sunlu(prof) and app.is_fixed_order(prof)
    assert prof["linePo"] is False and prof["poInDocs"] is False
    assert app.lot_bundle_modes({"customer": cust}) == ["PKL", "VAT", "PXK", "PO", "BBGH", "BDC", "PLX"]  # không ĐNTT, không ĐCCN


def test_defaults_po_sequence_per_day_and_latest_price(store, cust):
    d = app.lot_fixed_order_defaults(store, cust, "2026-09-19")
    assert (d["prefix"], d["date"], d["seq"], d["po"]) == ("ABCDE", "260919", "0001", "ABCDE2609190001")
    assert d["item"]["code"] == "90000001" and d["price"] == 1000 and d["qty"] == 0  # mã cố định, giá danh mục khi chưa có hồ sơ
    app.lot_save_new(store, make_rec(store, cust, "ABCDE2609190001", 20000, 1060, "2026-09-25"), {})
    app.lot_save_new(store, make_rec(store, cust, "ABCDE2609190002", 15000, 1080, "2026-10-02"), {})
    d = app.lot_fixed_order_defaults(store, cust, "2026-09-19")
    assert d["seq"] == "0003" and d["price"] == 1080 and d["qty"] == 15000 and "02/10/2026" in d["price_from"]
    assert store.next_po_number(cust, "2026-09-20") == "ABCDE2609200001"  # ngày mới: số thứ tự bắt đầu lại


def test_fixed_items_validation(store, cust):
    with pytest.raises(ValueError, match="số lượng"):
        app.lot_fixed_order_items(store, cust, "ABCDE2609190001", "", 1000)
    with pytest.raises(ValueError, match="đơn giá"):
        app.lot_fixed_order_items(store, cust, "ABCDE2609190001", 100, 0)
    it = app.lot_fixed_order_items(store, cust, "ABCDE2609190001", "20,000", "1060")[0]
    assert (it["ma_sp"], it["qty"], it["price"], it["kien"], it["net"], it["gross"]) == ("90000001", 20000, 1060, 400, 600.0, 601.0)


def test_export_each_documents(store, cust):
    app.lot_save_new(store, make_rec(store, cust, "ABCDE2609190001", 10000, 1000, "2026-10-02"), {})
    rec = make_rec(store, cust, "ABCDE2609190002", 20000, 1060)
    res = app.lot_export_each(store, rec)
    assert [f["mode"] for f in res["files"]] == ["PKL", "VAT", "PXK", "PO", "BBGH", "BDC", "PLX"] and res["problems"] == []
    path = {f["mode"]: f["path"] for f in res["files"]}

    ws = openpyxl.load_workbook(path["VAT"]).active
    assert ws["D6"].value in (None, "")  # Hóa đơn VAT không ghi số PO
    ws = openpyxl.load_workbook(path["PKL"]).active
    assert ws["E3"].value == "Số ĐĐH:ABCDE2609190002" and ws["I3"].value == "Ngày: 19/09/2026" and ws["E2"].value == "PXKKVCNB :00000279"
    assert ws["E13"].value == 20000 and ws["F13"].value == 0.03 and ws["G13"].value == "=H13+1" and ws["I13"].value == "=ROUNDUP(E13/50,0)"
    assert ws["B13"].value == "90000001" and ws["H13"].value == "=E13*F13" and ws["H12"].value.startswith("Trọng lượng") and ws.max_column == 11  # đã bỏ cột H trống
    merged_in = {(r, c) for rg in ws.merged_cells.ranges for r in range(rg.min_row, rg.max_row + 1) for c in range(rg.min_col, rg.max_col + 1)} - {(rg.min_row, rg.min_col) for rg in ws.merged_cells.ranges}
    assert all(all([ws.cell(row=r, column=c).border.left.style, ws.cell(row=r, column=c).border.right.style, ws.cell(row=r, column=c).border.top.style, ws.cell(row=r, column=c).border.bottom.style])
               for r in range(1, 15) for c in range(1, 12) if (r, c) not in merged_in)  # đủ viền khắp khung (ô nằm trong vùng gộp lấy viền theo vùng)
    ws = openpyxl.load_workbook(path["PO"]).active
    assert ws["A4"].value == "ĐƠN ĐẶT HÀNG" and ws["A5"].value == "Số:ABCDE2609190002" and ws["D10"].value == 20000
    assert "30 ngày" in ws["A16"].value
    ws = openpyxl.load_workbook(path["BBGH"]).active
    assert ws["A2"].value == "Số:10/2026MM" and ws["B15"].value == "00003964" and ws["G15"].value == "=E15*F15"
    ws = openpyxl.load_workbook(path["BDC"]).active  # cả tháng 10: lô đã lưu + lô đang làm
    assert "tháng 10/2026" in ws["A3"].value
    assert [ws[f"B{r}"].value for r in (12, 13)] == ["90000001", "90000001"]  # cột B: mã liệu hiện hành, không phải số PO
    assert all(ws[a].font.b and ws[a].alignment.horizontal == "left" for a in ("A6", "A7"))  # địa chỉ / MST bên bán: đậm, căn trái
    assert (ws["D12"].value, ws["E12"].value) == ("Ống lõi giấy phi", "50x55x40mm")
    assert ws["I14"].value == "=SUM(I12:I13)" and "triệu" in ws["D17"].value
    ws = openpyxl.load_workbook(path["PLX"]).active
    texts = [ws[f"A{r}"].value or "" for r in range(1, 15)]
    assert any("Số lượng: 20.000 PCS" in t and "trị giá DAP 21.200.000" in t for t in texts)
    assert any("300000000001" in t and "00003964" in t for t in texts)


def test_import_learned_fills_missing_profile_fields(store):
    old = {"khach_moi": {"key": "motma", "profile": {"name": FAKE["name"], "mst": FAKE["mst"], "poPrefix": "ABCDE"}, "items": ITEMS[:1]}}
    store.import_learned(old)
    store.import_learned({"version": "hongthien-hoc-v1", "khach_moi": {"key": "motma", "profile": dict(FAKE), "items": ITEMS[1:]}})
    prof = app.PROFILES["motma"]
    assert prof["poGen"] == FAKE["poGen"] and prof["fixedItem"] == "90000001"
    assert app.fixed_order_item(store, "motma")["code"] == "90000001"


def test_lot_state_confirm_fixed_order(store, cust):
    lot = Lot(app, store)
    lot.select_customer(cust)
    assert lot.fixed_order and not Lot(app, store).fixed_order
    d = lot.fixed_defaults()
    lot.confirm_fixed_order(d["po"], "19/09/2026", "20000", "1060")
    assert lot.form["po"] == d["po"] and lot.po_touched and len(lot.items) == 1 and lot.items[0]["po"] == d["po"]
    lot.fill_next_po()
    assert lot.form["po"] == d["po"]  # đã xác nhận thì không tự đổi số PO
    errors, _ = lot.validate()
    assert errors == []

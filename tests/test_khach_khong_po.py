"""Khách KHÔNG có PO đầu vào (cờ hồ sơ `noPo`, kiểu Betterial):
- Bước ② không quét PO: tích mã hàng + nhập số lượng; số PO do Hồng Thiên tự tạo theo `poGen` (HT{yyyymmdd}).
- Bì cộng thêm theo từng mã (ống dài +4 kg, ống ngắn +1 kg), giữ nguyên khi tính lại cả lô.
- Đơn đặt hàng (PO) xuất theo form mẫu của khách: dòng 'TỔNG TIỀN' tìm theo chữ (mẫu có 7 dòng hàng, tổng ở hàng 25).
- Invoice theo form ô {{...}}: số kiện =ROUNDUP(SL/{{dm_kien}},0), cả bì =tịnh+{{bi}}.
- Hóa đơn VAT / PXK Bkav: IDChungTu 'mã d/m', UDD_PO trống.

Toàn bộ dữ liệu ở đây là DỮ LIỆU GIẢ (tên công ty, MST, mã hàng, giá, số PO đều bịa).
"""

import base64
import io

import openpyxl
import pytest

import hongthien_desktop_app as app
from ui_qt.state import Lot

FAKE = {
    "name": "CÔNG TY TNHH KHÔNG PO MẪU THỬ", "label": "KhongPo", "mst": "0100000088", "addr": "Lô Z, KCN Mẫu, Phường Thử, Tỉnh Bắc Ninh, Việt Nam.",
    "emails": "a@vd.test", "unit": "Chiếc", "tare": 1.0, "payDays": 30, "noPo": True, "pickItems": True, "poGen": "HT{yyyymmdd}",
    "linePo": False, "poInDocs": False, "bkavId": "khongpo {d}/{m}", "veViec": "xuất kho bán hàng cho", "extraDocs": "PO",
}
ITEMS = [
    {"code": "99X000.0001", "name": "Ống giấy 70 x 8 x 400mm (99X000.0001)", "unit": "Chiếc", "price": 20000, "div": 20, "kg": 0.7, "hs": "48229090", "tare": 1.0},
    {"code": "99X000.0002", "name": "Ống giấy 70 x 16 x 1100mm (99X000.0002)", "unit": "Chiếc", "price": 100000, "div": 3, "kg": 5.0, "hs": "48229090", "tare": 4.0},
]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


def _b64(wb):
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def po_template():
    """Form PO kiểu Betterial: dòng hàng 18-24, 'TỔNG TIỀN' hàng 25, bằng chữ hàng 28, thời gian giao hàng hàng 29."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A5"] = "ĐƠN ĐẶT HÀNG/ P.O 单"
    ws["A7"], ws["D7"] = "Ngày/ 日期 : 2000.01.01", "Số/ No.  HT20000101"
    for col, h in zip("ABCDEFGH", ("STT", "TÊN HÀNG", "ĐƠN VỊ", "THÔNG SỐ", "SỐ LƯỢNG", "ĐƠN GIÁ", "THÀNH TIỀN", "GHI CHÚ")):
        ws[f"{col}17"] = h
    for r in range(18, 25):
        ws[f"A{r}"], ws[f"B{r}"], ws[f"D{r}"], ws[f"E{r}"], ws[f"F{r}"], ws[f"G{r}"] = r - 17, "Hàng cũ", "cũ", 1, 1, f"=E{r}*F{r}"
    ws["A25"], ws["E25"], ws["G25"] = "TỔNG TIỀN/总价 (VND):", "=SUM(E21:E24)", "=SUM(G21:G24)"
    ws["A26"], ws["G26"] = "THUẾ VAT/ 增值 税 (0%):", 0
    ws["A27"], ws["G27"] = "TỔNG TIỀN BAO GỒM VAT/ 已含增值税 (VND):", "=G25+G26"
    ws["A28"] = "Tổng số tiền bằng chữ 总金额 : "
    ws["A29"] = "* Thời gian giao hàng 交货时间:01/01/2000"
    ws["A30"] = "* Địa điểm giao hàng: Lô Z"
    ws.print_area = "A1:H32"
    return _b64(wb)


def pkl_form():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["I6"], ws["N6"], ws["I7"], ws["N7"] = "Số hóa đơn  : {{so_pxk}}", "Ngày: {{ngay}}", "Số ĐĐH : {{so_po}}", "Ngày: {{ngay_po}}"
    for col, v in {"A": "{{stt}}", "B": "{{ma}}", "C": "{{ten}}", "H": "{{dvt}}", "I": "{{sl}}", "J": "{{kg}}", "K": "=L18+{{bi}}", "L": "=J18*I18",
                   "M": "=ROUNDUP(I18/{{dm_kien}},0)", "N": "{{gia}}", "O": "=N18*I18"}.items():
        ws[f"{col}18"] = v
    ws["A20"], ws["I20"], ws["M20"] = "Tổng", "=SUM(I18:I19)", "=SUM(M18:M19)"
    return _b64(wb)


@pytest.fixture
def cust(store):
    key = store.save_learned_customer("khongpo", dict(FAKE), [dict(x) for x in ITEMS])
    store.save_templates(key, {"po": po_template(), "thay/PKL.xlsx": pkl_form()})
    return key


def make_rec(store, cust, items, po):
    return app.lot_build_record(store, {"customer": cust, "doc_date": "2026-10-29", "po": po, "po_date": "03/10/2026", "pxk": "00000300", "ldd": "02",
                                        "xe": "99C-000.00", "driver": "Lái Xe Thử"}, items)


def test_flags_and_bundle(cust):
    prof = app.PROFILES[cust]
    assert app.is_no_po(prof) and app.is_pick_items(prof)
    assert app.lot_bundle_modes({"customer": cust}) == ["PKL", "VAT", "PXK", "PO"]
    assert not app.is_no_po(app.PROFILES["tesa"])


def test_lot_pick_with_generated_po_and_tare_per_code(store, cust):
    lot = Lot(app, store)
    lot.select_customer(cust)
    lot.form["doc_date"] = "2026-10-29"
    assert lot.no_po and lot.pick_items
    d = lot.no_po_defaults()
    assert d["po"] == "HT20261029"  # HT + năm tháng ngày làm, không có số thứ tự
    items = lot.confirm_pick([("99X000.0001", "1200", "20000"), ("99X000.0002", "882", "100000")], d["po"], "03/10/2026")
    assert [(it["kien"], it["net"], it["gross"], it["tare"]) for it in items] == [(60, 840.0, 841.0, 1.0), (294, 4410.0, 4414.0, 4.0)]
    lot.form["tare"] = "1.0"
    app.lot_recalc(lot.items, cust, "1.0")  # tính lại cả lô (bước ④ / lúc xuất): bì theo mã vẫn giữ
    assert [it["gross"] for it in lot.items] == [841.0, 4414.0]
    app.lot_save_new(store, make_rec(store, cust, lot.items, d["po"]), {})
    assert store.next_po_number(cust, "2026-10-30") == "HT20261030"


def test_export_po_invoice_bkav(store, cust):
    items = app.lot_pick_items(store, cust, [("99X000.0001", "1200", "20000"), ("99X000.0002", "882", "100000")], "HT20261029")
    rec = make_rec(store, cust, items, "HT20261029")
    path = {f["mode"]: f["path"] for f in app.lot_export_each(store, rec)["files"]}
    po = openpyxl.load_workbook(path["PO"]).active
    assert po["A7"].value == "Ngày/ 日期 : 2026.10.03" and po["D7"].value == "Số/ No.  HT20261029"
    assert [(po[f"B{r}"].value, po[f"D{r}"].value, po[f"E{r}"].value) for r in (18, 19)] == [
        ("Ống giấy", ITEMS[0]["name"], 1200), ("Ống giấy", ITEMS[1]["name"], 882)]
    assert po["A20"].value.startswith("TỔNG TIỀN") and po["E20"].value == "=SUM(E18:E19)" and po["G20"].value == "=SUM(G18:G19)"
    assert po["G22"].value == "=G20+G21" and po["C23"].value.startswith("Một trăm mười hai triệu")
    assert po["A24"].value == "* Thời gian giao hàng 交货时间:29/10/2026"
    inv = openpyxl.load_workbook(path["PKL"]).active
    assert (inv["I6"].value, inv["I7"].value, inv["N7"].value) == ("Số hóa đơn  : 00000300", "Số ĐĐH : HT20261029", "Ngày: 03/10/2026")
    assert [(inv[f"K{r}"].value, inv[f"M{r}"].value) for r in (18, 19)] == [("=L18+1", "=ROUNDUP(I18/20,0)"), ("=L19+4", "=ROUNDUP(I19/3,0)")]
    wb = openpyxl.Workbook()
    vat, pxk = app.build_vat_bkav_sheet(wb, rec), app.build_pxk_bkav_sheet(wb, rec)
    assert (vat["B6"].value, vat["C6"].value, vat["D6"].value) == ("khongpo 29/10", ITEMS[0]["name"], "")
    assert (pxk["C3"].value, pxk["D3"].value, pxk["P3"].value) == ("khongpo 29/10", "", "xuất kho bán hàng cho " + FAKE["name"])


def test_po_step_hides_file_drop(qapp, store, cust):
    from ui_qt.pages_lot import PoStep
    lot = Lot(app, store)
    lot.select_customer(cust)
    step = PoStep(lot)
    step.refresh()
    assert step.drop.isHidden() and not step.pick_box.isHidden() and step.p_pr.isHidden()
    assert step.p_po.text() == store.next_po_number(cust, lot.form["doc_date"]) and "không có PO" in step.pick_box.title()
    step.pick_rows[1][2].setText("300")
    step.pick_rows[1][1].setChecked(True)
    step.confirm_pick()
    assert [(it["ma_sp"], it["qty"]) for it in lot.items] == [("99X000.0002", 300)]


def test_other_pick_customer_keeps_tare_of_lot(store):
    key = store.save_learned_customer("itma2", {**FAKE, "name": "CÔNG TY ÍT MÃ KHÁC", "noPo": False}, [dict(ITEMS[1])])
    assert not app.is_no_po(app.PROFILES[key]) and store.items_for_customer(key)[0]["tare"] == 1.0  # khách khác: bì chung như cũ
    it = app.lot_pick_items(store, key, [("99X000.0002", "3", "100000")], "PO1", "1.0")[0]
    assert "bi_ma" not in it and it["gross"] == 16.0

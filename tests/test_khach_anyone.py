"""Khách đặt một mã, KHÔNG dùng ERP, chưa khai hải quan (kiểu Anyone):
- Số ĐĐH tự tạo dạng 'AN-yyyymmdd-stt' (poGen 'AN-{yyyymmdd}-{nnn}').
- PXK Bkav: Lý do xuất kho ghi kèm tên khách (`lyDoXuat`), UDD_PO ghi số ĐĐH.
- Bảng đối chiếu công nợ cả tháng theo mẫu tiếng Việt (`dccnStyle: thang`, như Able).
- `noErp`: không lấy kg / mã / tên từ ERP cho khách này.
- Mẫu riêng: ô {{yy}}, {{bi}}; số điền vào công thức giữ dấu chấm thập phân (=I14*7.79, không phải 7,79).

Toàn bộ dữ liệu ở đây là DỮ LIỆU GIẢ (tên công ty, MST, mã hàng, giá đều bịa).
"""

import io

import openpyxl
import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {
    "name": "CÔNG TY TNHH MỘT MÃ KHÔNG ERP", "label": "KhongErp", "mst": "0100000077", "addr": "Lô Q, KCN Mẫu, Phường Thử, Tỉnh Bắc Ninh, Việt Nam",
    "unit": "Chiếc", "tare": 1.0, "payDays": 30, "fixedItem": "100x10x900", "poGen": "KE-{yyyymmdd}-{nnn}", "linePo": True, "poInDocs": True,
    "bkavId": "kherp {d}/{m}", "veViec": "Xuất kho làm thủ tục hải quan cho", "lyDoXuat": "Xuất chuyển kho cho", "extraDocs": "DCCN",
    "dccnStyle": "thang", "noErp": True,
}
ITEM = {"code": "100x10x900", "name": "Ống lõi giấy phi 100 x 10 x 900mm", "unit": "Chiếc", "price": 200000, "div": 10, "kg": 5.55, "hs": "48229090", "tare": 1.0}


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def cust(store):
    return store.save_learned_customer("khongerp", dict(FAKE), [dict(ITEM)])


def make_rec(store, cust, po, qty, doc_date="2026-08-11", pxk="00000182"):
    items = app.lot_fixed_order_items(store, cust, po, qty, 200000, "1.0")
    return app.lot_build_record(store, {"customer": cust, "doc_date": doc_date, "po": po, "po_date": "05/08/2026", "pxk": pxk, "ldd": "02",
                                        "xe": "99H.000.00", "driver": "Lái Xe Thử"}, items)


def test_po_number_dash_date_dash_seq(store, cust):
    d = app.lot_fixed_order_defaults(store, cust, "2026-08-05")
    assert (d["prefix"], d["date"], d["seq"], d["po"]) == ("KE-", "20260805-", "001", "KE-20260805-001")
    app.lot_save_new(store, make_rec(store, cust, "KE-20260805-002", 100), {})
    assert store.next_po_number(cust, "2026-08-05") == "KE-20260805-003"
    assert store.next_po_number(cust, "2026-08-06") == "KE-20260806-001"


def test_bkav_sheets(store, cust):
    rec = make_rec(store, cust, "KE-20260805-002", 100)
    it = rec["items"][0]
    assert (it["kien"], it["net"], it["gross"]) == (10, 555.0, 556.0)
    wb = openpyxl.Workbook()
    vat, pxk = app.build_vat_bkav_sheet(wb, rec), app.build_pxk_bkav_sheet(wb, rec)
    assert (vat["B6"].value, vat["D6"].value, vat["I6"].value) == ("kherp 11/8", "KE-20260805-002", 0)
    assert (pxk["C3"].value, pxk["D3"].value) == ("kherp 11/8", "KE-20260805-002")
    assert pxk["P3"].value == "Xuất kho làm thủ tục hải quan cho CÔNG TY TNHH MỘT MÃ KHÔNG ERP"
    assert pxk["Q3"].value == "Xuất chuyển kho cho CÔNG TY TNHH MỘT MÃ KHÔNG ERP"
    app.PROFILES[cust]["lyDoXuat"] = ""
    assert app.build_pxk_bkav_sheet(openpyxl.Workbook(), rec)["Q3"].value == "Xuất chuyển kho"  # khách khác giữ như cũ


def test_bundle_and_month_dccn(store, cust):
    app.lot_save_new(store, make_rec(store, cust, "KE-20260801-001", 50, "2026-08-03", pxk="00000170"), {})
    rec = make_rec(store, cust, "KE-20260805-002", 100)
    assert app.lot_bundle_modes(rec) == ["PKL", "VAT", "PXK", "DCCN"]
    assert app.is_dccn_month(app.PROFILES[cust]) and not app.is_able(app.PROFILES[cust])
    res = app.lot_export_each(store, rec)
    path = {f["mode"]: f["path"] for f in res["files"]}
    ws = openpyxl.load_workbook(path["DCCN"]).active
    assert "ĐỐI CHIẾU CÔNG NỢ" in ws["B1"].value and ws["B2"].value == "Ngày日31 tháng月08 năm年 2026"
    assert [ws[f"D{r}"].value for r in (12, 13)] == ["KE-20260801-001", "KE-20260805-002"]  # cả tháng 8: lô đã lưu + lô đang làm
    assert [ws[f"I{r}"].value for r in (12, 13)] == [50, 100] and ws["G19"].value == "CÔNG TY TNHH MỘT MÃ KHÔNG ERP"


def test_no_erp_data_for_customer(store, cust):
    store.data_tong = [
        {"khach": "KhongErp", "ten": "Ống lõi giấy phi 100 x 10 x 900mm", "ma_hang": "100x10x900", "ma_erp": "E1", "kg": 9.99, "kg_nguon": "erp"},
        {"khach": "KhongErp", "ten": "Ống khác", "ma_hang": "200x5x100", "kg": 1.5, "kg_nguon": "invoice", "kien": 20, "kien_nguon": "invoice"},
    ]
    store._dt_cache = {}
    assert [x["ma_hang"] for x in store.dt_items_for(cust)] == ["200x5x100"]  # mục nạp từ ERP bị bỏ
    assert app.lot_erp_info(store, cust, {"ma_sp": "100x10x900", "ma_erp": "E1"}) == {}
    lines = [{"ma_sp": "100x10x900", "ten_sp": ITEM["name"], "kg": 0, "div": 0}]
    store.dt_fill_lines(cust, lines)
    assert lines[0]["kg"] == 0 and not lines[0].get("ma_erp")
    app.PROFILES[cust]["noErp"] = False
    store._dt_cache = {}
    assert len(store.dt_items_for(cust)) == 2  # khách thường vẫn dùng ERP


def test_custom_form_tokens_yy_bi_and_formula_numbers():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Số: {{mm}}{{yy}}AVI"
    ws["A3"], ws["B3"], ws["C3"], ws["D3"] = "{{sl}}", "=A3*{{kg}}", "=B3+{{bi}}", "{{kg}}"
    buf = io.BytesIO()
    wb.save(buf)
    rec = {"docDate": "2026-08-11", "items": [{"ma_sp": "x", "ten_sp": "y", "qty": 100, "price": 1, "kg": 7.79, "net": 779.0, "gross": 780.0, "div": 10, "kien": 10}]}
    consts = {"name": "HT", "addr": "Đ/c", "mst": "1", "date": app._iso_to_date, "words": lambda n: str(n)}
    data, unknown = mau_rieng.fill_xlsx(buf.getvalue(), mau_rieng.batch_values(rec, {}, consts), mau_rieng.item_values(rec))
    out = openpyxl.load_workbook(io.BytesIO(data)).active
    assert unknown == [] and out["A1"].value == "Số: 0826AVI"
    assert (out["A3"].value, out["B3"].value, out["C3"].value, out["D3"].value) == (100, "=A3*7.79", "=B3+1", 7.79)

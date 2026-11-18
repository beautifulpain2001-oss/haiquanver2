"""Form MỖI MÃ HÀNG MỘT PHIẾU (kiểu phiếu kiểm tra chất lượng công đoạn của TSCO, cờ hồ sơ `riengMoiMa`) và các ô quy cách / tiêu chuẩn.

Toàn bộ dữ liệu ở đây là DỮ LIỆU GIẢ (tên công ty, MST, mã hàng, giá, số PO đều bịa).
"""

import io
import os

import openpyxl
import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {
    "name": "CÔNG TY TNHH PHIẾU KIỂM MẪU THỬ", "label": "PhieuKiem", "mst": "0100000077", "addr": "Lô Y, KCN Mẫu, Xã Thử, Tỉnh Phú Thọ, Việt Nam",
    "unit": "Chiếc", "tare": 1.0, "linePo": False, "poInDocs": False, "pxkPo": False, "pickItems": True,
    "po_pattern": app.infer_po_pattern("PUOR1234567-HN"),
    "rieng": ["KiemTra.xlsx"], "riengMoiMa": ["KiemTra.xlsx"],
    "qcItems": {"100x2.5x200": {"ma": "FG-TEST-001", "phi": "0,5"}},
}
ITEMS = [
    {"code": "100x2.5x200", "name": "Ống giấy carton, kích thước 100 x 2.5 x 200mm", "unit": "Chiếc", "price": 4000, "div": 10, "kg": 0.2, "hs": "48229090"},
    {"code": "70x3x80", "name": "Ống giấy carton, kích thước 70 x 3 x 80mm", "unit": "Chiếc", "price": 5000, "div": 10, "kg": 0.05, "hs": "48229090"},
]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


def _form_bytes(with_image=True):
    from openpyxl.drawing.image import Image
    from PIL import Image as PILImage
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mau"
    ws["A1"] = "PHIẾU KIỂM TRA"
    ws["B2"], ws["D2"], ws["F2"] = "{{ma_kt}}", "{{sl}} psc", "{{quy_cach}}"
    ws["B3"], ws["C3"], ws["D3"] = "{{tc_phi}}", "{{phi}}", "{{phi}}"
    ws["B4"], ws["C4"] = "{{tc_day}}", "{{day}}"
    ws["B5"], ws["C5"] = "{{tc_dai}}", "{{dai}}"
    ws["A7"] = "Khách: {{khach_ten}} - Năm {{yyyy}}"
    ws.merge_cells("A1:F1")
    if with_image:
        buf = io.BytesIO()
        PILImage.new("RGB", (20, 10), "red").save(buf, "PNG")
        img = Image(io.BytesIO(buf.getvalue()))
        img.anchor = "H1"
        ws.add_image(img)
    wb.create_sheet("Cu")["A1"] = "phiếu cũ, bỏ đi"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_qc_values_from_spec_and_profile():
    it = {"ma_sp": "100x2.5x200", "ten_sp": "Ống"}
    v = mau_rieng.qc_values(it, FAKE["qcItems"]["100x2.5x200"])
    assert v == {"ma_kt": "FG-TEST-001", "quy_cach": "100 x 2.5 x 200", "phi": 100, "day": 2.5, "dai": 200,
                 "tc_phi": "100±0,5", "tc_day": "2.5±0,2", "tc_dai": "200±2"}
    v2 = mau_rieng.qc_values({"ma_sp": "ABC", "ten_sp": "Ống giấy phi 76 x 7 x 270mm"})
    assert (v2["ma_kt"], v2["quy_cach"], v2["tc_phi"]) == ("ABC", "76 x 7 x 270", "76±0,2")
    assert mau_rieng.qc_values({"ma_sp": "X", "ten_sp": "Pallet gỗ"})["quy_cach"] == ""


def test_fill_per_item_one_sheet_each():
    rec = {"customer": "x", "docDate": "2026-09-16", "items": [
        {"ma_sp": "100x2.5x200", "ten_sp": ITEMS[0]["name"], "qty": 5000, "price": 4000},
        {"ma_sp": "70x3x80", "ten_sp": ITEMS[1]["name"], "qty": 2000, "price": 5000}]}
    batch = {"khach_ten": "KHÁCH THỬ", "yyyy": "2026"}
    out, unknown = mau_rieng.fill_xlsx_per_item(_form_bytes(), batch, mau_rieng.item_values(rec, FAKE["qcItems"]))
    assert unknown == []
    wb = openpyxl.load_workbook(io.BytesIO(out))
    assert wb.sheetnames == ["FG-TEST-001", "70x3x80"]
    a, b = wb.worksheets
    assert (a["B2"].value, a["D2"].value, a["F2"].value, a["B3"].value, a["C3"].value, a["C4"].value) == (
        "FG-TEST-001", "5.000 psc", "100 x 2.5 x 200", "100±0,5", 100, 2.5)
    assert (b["B2"].value, b["D2"].value, b["B3"].value, b["D3"].value, b["B5"].value, b["C5"].value) == (
        "70x3x80", "2.000 psc", "70±0,2", 70, "80±2", 80)
    assert b["A7"].value == "Khách: KHÁCH THỬ - Năm 2026"
    assert "A1:F1" in [str(m) for m in b.merged_cells.ranges]
    assert len(a._images) == 1 and len(b._images) == 1  # logo / ảnh của phiếu mẫu có ở mọi phiếu


def test_export_learned_customer_per_item_form(store, tmp_path):
    key = store.save_learned_customer("phieukiem", dict(FAKE), [dict(x) for x in ITEMS])
    folder = os.path.join(store.template_folder(key), "rieng")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "KiemTra.xlsx"), "wb") as f:
        f.write(_form_bytes())
    items = app.lot_pick_items(store, key, [("100x2.5x200", "5000", "4000"), ("70x3x80", "2000", "5000")], "PUOR1234567-HN")
    rec = app.lot_build_record(store, {"customer": key, "doc_date": "2026-09-16", "po": "PUOR1234567-HN", "pxk": "00000300", "ldd": "02",
                                       "xe": "99C-000.00", "driver": "Lái Xe Thử"}, items)
    assert "R:KiemTra.xlsx" in app.lot_bundle_modes(rec)
    res = app.lot_export(store, rec, "R:KiemTra.xlsx")
    wb = openpyxl.load_workbook(res["path"])
    assert wb.sheetnames == ["FG-TEST-001", "70x3x80"]
    assert wb.worksheets[1]["D2"].value == "2.000 psc"
    # form thường (không ghi trong riengMoiMa) vẫn nhân dòng hàng trong một sheet như cũ
    app.PROFILES[key]["riengMoiMa"] = []
    wb2 = openpyxl.load_workbook(app.lot_export(store, rec, "R:KiemTra.xlsx")["path"])
    assert wb2.sheetnames == ["Mau", "Cu"] and (wb2["Mau"]["B2"].value, wb2["Mau"]["B3"].value) == ("FG-TEST-001", "70x3x80")


def test_quy_cach_token_in_table_form():
    rec = {"items": [{"ma_sp": "114x2.5x265", "ten_sp": "Ống giấy carton, kích thước 114 x 2.5 x 265mm", "qty": 1, "price": 1}]}
    assert mau_rieng.item_values(rec)[0]["quy_cach"] == "114 x 2.5 x 265"

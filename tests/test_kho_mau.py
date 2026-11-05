"""Kho mẫu chung: mẫu Word/Excel dùng lại giữa các khách, đặt tên LOẠI_Khách_số; mượn mẫu khi tạo khách mới; xem mẫu. Dữ liệu giả."""

import io
import os
import zipfile

import openpyxl
import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {"name": "CÔNG TY TNHH KHO MẪU THỬ", "label": "KhoThu", "mst": "0100000088", "addr": "Lô Z, KCN Thử, Hải Phòng", "unit": "chiếc", "tare": 1.0, "payDays": 30}
ITEMS = [{"code": "A1", "name": "Ống lõi giấy phi 50 x 55 x 40mm (A1)", "unit": "chiếc", "price": 1000, "div": 50, "kg": 0.03}]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def rec(store):
    store.save_learned_customer("khothu", dict(FAKE), [dict(x) for x in ITEMS])
    items = [{"stt": 1, "po": "P1", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 21212, "price": 1060, "amount": 22484720, "div": 50, "kg": 0.04, "kien": 425, "net": 848.48, "gross": 849.48, "hs": "48229090"},
             {"stt": 2, "po": "P1", "ma_sp": "A2", "ten_sp": "Ống B", "unit": "chiếc", "qty": 100, "price": 500, "amount": 50000, "div": 50, "kg": 0.1, "kien": 2, "net": 10, "gross": 11, "hs": "48229090"}]
    return app.lot_build_record(store, {"customer": "khothu", "doc_date": "2026-11-05", "po": "P1", "po_date": "01/11/2026", "pxk": "00000321", "hd": "00001", "tk": "3000"}, items)


def test_kho_is_seeded_once_and_names_follow_convention(store):
    names = [(m["file"], m["loai"], m["khach"], m["so"], m["ext"]) for m in store.kho_list()]
    assert ("PLX_Arizon_01.xlsx", "PLX", "Arizon", "01", "xlsx") in names and ("PLX_Sunlu_01.docx", "PLX", "Sunlu", "01", "docx") in names
    assert all(not m["unknown"] and m["tokens"] for m in store.kho_list())
    store.kho_remove("PLX_Sunlu_01.docx")
    assert "PLX_Sunlu_01.docx" not in [m["file"] for m in store.kho_list()]  # xóa rồi không bị gieo lại


def test_kho_add_numbers_up_and_validates(store, tmp_path):
    src = tmp_path / "x.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "{{so_po}}"
    wb.save(src)
    assert store.kho_add(str(src), "plx", "Arizon")[0] == "PLX_Arizon_02.xlsx"
    assert store.kho_add(str(src), "BBGH", "Sun lu")[0] == "BBGH_Sunlu_01.xlsx"
    empty = tmp_path / "e.xlsx"
    openpyxl.Workbook().save(empty)
    with pytest.raises(ValueError, match="ô thay thế"):
        store.kho_add(str(empty), "PLX", "Arizon")
    with pytest.raises(ValueError, match="Word"):
        store.kho_add(str(tmp_path / "y.txt"), "PLX", "Arizon")


def test_borrow_arizon_excel_and_sunlu_word_then_export(store, rec):
    store.kho_list()
    store.kho_borrow("khothu", "PLX_Arizon_01.xlsx")
    store.kho_borrow("khothu", "PLX_Sunlu_01.docx")
    assert store.custom_forms("khothu") == ["PLX_Arizon_01.xlsx", "PLX_Sunlu_01.docx"]
    res = app.lot_export(store, rec, "R:PLX_Arizon_01.xlsx")
    ws = openpyxl.load_workbook(res["path"]).active
    assert ws["A4"].value == f"Tên nhà sản xuất: {app.HT_NAME}" and ws["C6"].value == "21.312" and "00001" in ws["A8"].value
    assert [ws[f"C{r}"].value for r in (11, 12)] == ["Ống A", "Ống B"] and [ws[f"D{r}"].value for r in (11, 12)] == [21212, 100]  # dòng hàng nhân lên, số thật
    assert "Khai tại văn bản này" in ws["A14"].value  # đoạn cam kết bị đẩy xuống đúng chỗ
    res = app.lot_export(store, rec, "R:PLX_Sunlu_01.docx")
    texts = mau_rieng.preview("docx", open(res["path"], "rb").read())["text"].split("\n")
    assert texts[6] == "Số lượng: 21.312 PCS , Ống A; Ống B , trị giá DAP 22.534.720  VND"
    assert "Hóa Đơn Số: 00001 ngày 05/11/2026" in texts[7] and texts[12].strip() == "Bắc Ninh, ngày 05 tháng 11  năm 2026"
    # đưa mẫu riêng của khách vào kho chung với tên theo khách
    name, _k, _u = store.kho_publish("khothu", "PLX_Arizon_01.xlsx", "PLX")
    assert name == "PLX_KhoThu_01.xlsx"


def test_preview_shapes(store):
    store.kho_list()
    word = mau_rieng.preview("docx", store.kho_read("PLX_Sunlu_01.docx"))
    assert word["kind"] == "text" and "Phụ lục X" in word["text"] and "{{tong_sl}}" in word["text"]
    grid = mau_rieng.preview("xlsx", store.kho_read("PLX_Arizon_01.xlsx"))
    assert grid["kind"] == "grid" and grid["rows"][0][0] == "PHỤ LỤC X" and grid["rows"][10][:4] == ["{{stt}}", "{{ma}}", "{{ten}}", "{{sl}}"]


def test_kho_page_preview_and_use_for_customer(qapp, store, rec):
    from ui_qt.pages_kho import MauPage
    page = MauPage(app, store)
    page.refresh()
    assert page.table.rowCount() >= 2
    names = [it["file"] for it in page.items]
    page.table.selectRow(names.index("PLX_Sunlu_01.docx"))
    assert "Phụ lục X" in page.preview.text.toPlainText() and "tong_sl" in page.preview.caption.text()
    page.table.selectRow(names.index("PLX_Arizon_01.xlsx"))
    assert page.preview.grid.item(0, 0).text() == "PHỤ LỤC X"
    page.use_for_customer("khothu")
    assert store.custom_forms("khothu") == ["PLX_Arizon_01.xlsx"] and "Đã có mẫu" not in page.msg.text() and "PLX_Arizon_01.xlsx" in page.msg.text()
    page.close()


def test_new_customer_flow_three_files_then_pick_template(qapp, store, tmp_path):
    from ui_qt.dialogs import LearnCustomerDialog, LearnFilesDialog
    dlg = LearnFilesDialog()
    assert not dlg.go.isEnabled()
    dlg.set_path("invoice", "/x/iv.xlsx")
    dlg.set_path("hoadon", "/x/vat.xml")
    assert not dlg.go.isEnabled()
    dlg.set_path("pxk", "/x/pxk.xml")
    assert dlg.go.isEnabled() and dlg.file_list() == ["/x/iv.xlsx", "/x/vat.xml", "/x/pxk.xml"]
    dlg.close()
    draft = {"profile": {"name": "CÔNG TY MỚI ABC", "mst": "0100000055", "addr": "Hải Phòng"}, "items": [{"code": "Z1", "name": "Hàng Z", "unit": "chiếc", "price": 10, "div": 5, "kg": 0.1}],
             "errors": [], "sample_po": "", "tare": 0.0, "po_text": ""}
    d = LearnCustomerDialog(app, store, [], draft=draft)
    d.edits["key"].setText("abcmoi")
    d.edits["label"].setText("AbcMoi")
    d.kho.list.item([it["file"] for it in d.kho.items].index("PLX_Arizon_01.xlsx")).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Checked)
    d.save()
    assert d.key == "abcmoi" and store.custom_forms("abcmoi") == ["PLX_Arizon_01.xlsx"]
    assert app.lot_bundle_modes({"customer": "abcmoi"}) == ["PKL", "VAT", "PXK", "R:PLX_Arizon_01.xlsx"]
    d.close()

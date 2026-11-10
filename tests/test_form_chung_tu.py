"""Kho mẫu thành nơi sửa form chứng từ của từng khách: chứng từ dựng sẵn đổi thành form Excel/Word có ô {{...}},
sửa trong phần mềm, các lần xuất sau dùng form đã sửa, giữ bản gốc để khôi phục. Dữ liệu giả."""

import io
import os

import openpyxl
import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {"name": "CÔNG TY TNHH ARIZON THỬ", "label": "ArzThu", "mst": "0100000088", "addr": "Lô Z, KCN Thử", "unit": "chiếc", "tare": 1.0, "payDays": 30,
        "extraDocs": "PLX,DNTT,BBGH,PO,SC,DCCN"}
ITEMS = [{"stt": 1, "po": "P1", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 21212, "price": 1060, "amount": 22484720, "div": 50, "kg": 0.04, "kien": 425,
          "net": 848.48, "gross": 849.48, "tare": 1, "hs": "48229090"},
         {"stt": 2, "po": "P1", "ma_sp": "A2", "ten_sp": "Ống B", "unit": "chiếc", "qty": 100, "price": 500, "amount": 50000, "div": 50, "kg": 0.1, "kien": 2,
          "net": 10, "gross": 11, "tare": 1, "hs": "48229090"}]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def rec(store):
    store.save_learned_customer("arz", dict(FAKE), [{"code": "A1", "name": "Ống", "unit": "chiếc", "price": 1000, "div": 50, "kg": 0.03}])
    return app.lot_build_record(store, {"customer": "arz", "doc_date": "2026-11-05", "po": "P1", "po_date": "01/11/2026", "pxk": "00000321", "hd": "00001",
                                        "tk": "3000", "pay_days": "30"}, [dict(x) for x in ITEMS])


def _norm(v):
    if v in ("", None):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 3)
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return v


def test_customer_docs_lists_bundle_with_kinds(store, rec):
    kinds = {d["mode"]: d["kind"] for d in store.customer_docs("arz")}
    assert kinds == {"PKL": "builtin", "VAT": "bkav", "PXK": "bkav", "PLX": "builtin", "DNTT": "builtin", "BBGH": "builtin", "PO": "builtin", "SC": "builtin", "DCCN": "builtin"}
    with pytest.raises(ValueError, match="Bkav|giữ đúng"):
        store.form_make("arz", "VAT")


@pytest.mark.parametrize("mode", ["PKL", "PLX", "DNTT", "BBGH", "PO", "SC", "DCCN"])
def test_form_from_builtin_exports_same_as_builtin(store, rec, mode):
    """Chuyển sang form rồi xuất: từng ô giống hệt mẫu dựng sẵn (trừ công thức theo định mức/bì đã thành số app tính)."""
    wb, _f, _p = app.lot_mode_workbook(store, rec, mode)
    app.mau_chung_tu.autofit_workbook(wb)
    path, warns = store.form_make("arz", mode)
    assert os.path.basename(path) == f"{mode}.xlsx" and store.form_override("arz", mode) == path
    assert mode != "DCCN" or not warns
    res = app.lot_export(store, rec, mode)
    assert res["fname"].startswith(app.FORM_FILE_PREFIX[mode]) and not res["problems"]
    out = openpyxl.load_workbook(res["path"]).worksheets[0]
    diffs = []
    for row in wb.worksheets[0].iter_rows():
        for c in row:
            v, fv = c.value, out[c.coordinate].value
            if isinstance(v, str) and v.startswith("=") and isinstance(fv, (int, float)):
                continue  # =ROUNDUP(E13/50,0), =H13+1: mỗi mặt hàng một định mức nên form lấy số app tính
            if isinstance(v, str) and isinstance(fv, (int, float)) and v.replace(".", "").isdigit():
                v = float(v.replace(".", ""))
            if _norm(v) != _norm(fv):
                diffs.append((c.coordinate, v, fv))
    assert diffs == []


def test_form_rows_and_totals_follow_item_count(store, rec):
    store.form_make("arz", "PKL")
    rec["items"].append(dict(ITEMS[1], ma_sp="A3", ten_sp="Ống C", qty=7, amount=3500))
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "PKL")["path"]).worksheets[0]
    assert [ws[f"H{r}"].value for r in (13, 14, 15)] == ["=ROUNDUP(E13*F13,2)", "=ROUNDUP(E14*F14,2)", "=ROUNDUP(E15*F15,2)"]  # công thức dòng hàng dời theo dòng
    assert ws["E16"].value == "=SUBTOTAL(9,E13:E15)" and ws["D17"].value == "=I16"  # tổng kéo dài, ô dưới dời xuống
    assert ws["B15"].value == "A3\nỐng C"


def test_edit_form_keeps_original_and_restore_and_drop(store, rec):
    path, _w = store.form_make("arz", "PLX")
    goc = store.doc_read(path)
    data = mau_rieng.set_xlsx_cells(goc, {("PLX", 1, 1): "PHỤ LỤC X (ĐÃ SỬA)"})
    store.doc_write(path, data)
    assert openpyxl.load_workbook(app.lot_export(store, rec, "PLX")["path"]).worksheets[0]["A1"].value == "PHỤ LỤC X (ĐÃ SỬA)"  # lần xuất sau dùng form đã sửa
    assert store.customer_docs("arz")[3]["goc"]
    store.doc_restore(path)
    assert store.doc_read(path) == goc
    store.form_drop("arz", "PLX")
    assert store.form_override("arz", "PLX") is None
    assert {d["mode"]: d["kind"] for d in store.customer_docs("arz")}["PLX"] == "builtin"
    with pytest.raises(ValueError):
        store.doc_write(os.path.join(store.base_dir, "x.xlsx"), b"")  # chỉ ghi trong thư mục mẫu chứng từ


def test_custom_form_edit_backup_and_learned_export_roundtrip(store, rec, tmp_path):
    store.kho_list()
    store.kho_borrow("arz", "PLX_Sunlu_01.docx")
    path = os.path.join(store.template_folder("arz"), "rieng", "PLX_Sunlu_01.docx")
    paras = mau_rieng.docx_paragraphs(store.doc_read(path))
    i = next(n for n, t in enumerate(paras) if "Bắc Ninh, ngày" in t)
    store.doc_write(path, mau_rieng.set_docx_paragraphs(store.doc_read(path), {i: "Hải Phòng, ngày {{dd}}/{{mm}}/{{yyyy}}"}))
    assert store.doc_original(path) and mau_rieng.docx_paragraphs(store.doc_read(path))[i] == "Hải Phòng, ngày {{dd}}/{{mm}}/{{yyyy}}"
    res = app.lot_export(store, rec, "R:PLX_Sunlu_01.docx")
    assert "Hải Phòng, ngày 05/11/2026" in mau_rieng.preview("docx", open(res["path"], "rb").read())["text"]
    # form đã sửa đi theo "Xuất dữ liệu học" sang máy khác
    store.form_make("arz", "SC")
    data = store.export_learned("arz")
    assert "thay/SC.xlsx" in data["khach_moi"]["mau"]
    import shutil
    shutil.rmtree(store.form_dir("arz"))
    store.import_learned(data, True)
    assert store.form_override("arz", "SC")


def test_builtin_customers_and_sunlu_word(store, rec):
    for key in ("shirai", "kodi", "tesa"):
        for d in store.customer_docs(key):
            if d["kind"] == "builtin":
                ext, data, _w = app.form_from_builtin(store, key, d["mode"])
                assert ext == "xlsx" and mau_rieng.template_tokens(ext, data)[0]
            elif d["kind"] in ("bkav", "fixed"):
                assert app.form_from_builtin(store, key, d["mode"], tokenize=False)[1]
    store.save_learned_customer("sunluthu", {"name": "CÔNG TY TNHH SUNLU THỬ", "label": "SunluThu", "docStyle": "sunlu", "unit": "chiếc"}, [])
    ext, data, _w = app.form_from_builtin(store, "sunluthu", "PLX")
    assert ext == "docx" and "{{tong_sl}}" in mau_rieng.preview("docx", data)["text"]


def test_xlsx_cell_helpers_keep_format():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    ws["A1"] = "x"
    ws["A1"].number_format = "#,##0"
    ws.merge_cells("B1:C1")
    buf = io.BytesIO()
    wb.save(buf)
    out = mau_rieng.set_xlsx_cells(buf.getvalue(), {("S", 1, 1): "1234", ("S", 1, 3): "bỏ qua (ô gộp)", ("S", 2, 1): "=A1*2"})
    ws = openpyxl.load_workbook(io.BytesIO(out))["S"]
    assert ws["A1"].value == 1234 and ws["A1"].number_format == "#,##0" and ws["A2"].value == "=A1*2"
    cells = mau_rieng.xlsx_cells(out)[0]
    assert cells["rows"][0][0] == "1234" and (1, 3) in cells["merged"]


def test_kho_page_per_customer_convert_edit(qapp, store, rec, monkeypatch):
    """Tab Kho mẫu: chọn khách -> thấy chứng từ của khách; chuyển PLX thành form, sửa trong app, lưu, khôi phục bản gốc, bỏ form."""
    from ui_qt import pages_kho
    monkeypatch.setattr(pages_kho.widgets, "ask", lambda *a, **k: True)
    page = pages_kho.MauPage(app, store)
    page.resize(1400, 900)
    page.show()
    page.refresh()
    assert page.cust is None and page.items  # mặc định: kho chung
    assert page.select_customer("arz")
    assert [d["mode"] for d in page.docs][:4] == ["PKL", "VAT", "PXK", "PLX"]
    page.listw.setCurrentRow(1)
    assert page.conv_btn.isHidden() and page.edit_btn.isHidden() and "Bkav" in page.kind_hint.text()
    page.listw.setCurrentRow(3)
    assert not page.conv_btn.isHidden() and page.view.pages  # hình form sẽ tạo
    page.convert()
    d = page.current_doc()
    assert d["kind"] == "form" and not page.edit_btn.isHidden() and page.restore_btn.isEnabled()
    dlg = pages_kho.EditTemplateDialog(app, store, "PLX.xlsx", page, path=d["path"], title="ArzThu / PLX")
    dlg.tabs.setCurrentIndex(1)
    dlg.content.grid.item(0, 0).setText("PHỤ LỤC X - SỬA TRONG APP")
    assert dlg.dirty and dlg.save_btn.isEnabled()
    dlg.content.grid.setCurrentCell(2, 0)
    dlg.token.setCurrentIndex(dlg.token.findData("so_tk"))
    dlg.insert()
    assert dlg.content.grid.item(2, 0).text().endswith("{{so_tk}}")
    dlg.save()
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "PLX")["path"]).worksheets[0]
    assert ws["A1"].value == "PHỤ LỤC X - SỬA TRONG APP" and ws["A3"].value.endswith("3000")
    page.refresh(select="PLX")
    assert page.restore_btn.isEnabled()
    page.restore()
    assert openpyxl.load_workbook(io.BytesIO(store.doc_read(d["path"]))).worksheets[0]["A1"].value == "PHỤ LỤC X"
    page.drop()
    assert page.current_doc()["kind"] == "builtin"
    page.close()

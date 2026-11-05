"""Mẫu riêng của khách (Word/Excel): nhập file mẫu có ô {{...}}, phần mềm điền và xuất lại đúng định dạng file đó. Dữ liệu giả."""

import io
import os
import zipfile

import openpyxl
import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {"name": "CÔNG TY TNHH MẪU RIÊNG THỬ", "label": "MauRieng", "mst": "0100000077", "addr": "Lô Y, KCN Thử, Hải Phòng", "unit": "chiếc", "tare": 1.0, "payDays": 30}
ITEMS = [{"code": "A1", "name": "Ống lõi giấy phi 50 x 55 x 40mm (A1)", "unit": "chiếc", "price": 1000, "div": 50, "kg": 0.03}]

_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    '<w:p><w:r><w:t>Số PO: {{so</w:t></w:r><w:r><w:t>_po}} ngày {{ngay}} &amp; khách {{khach_ten}}</w:t></w:r></w:p>'
    '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>STT</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Tên</w:t></w:r></w:p></w:tc></w:tr>'
    '<w:tr><w:tc><w:p><w:r><w:t>{{stt}}</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>{{ten}} x {{sl}}</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    '<w:p><w:r><w:t>Tổng: {{tong_sl}} / {{khong_co}}</w:t></w:r></w:p></w:body></w:document>'
)


def make_docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", _DOC)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def rec(store):
    store.save_learned_customer("maurieng", dict(FAKE), [dict(x) for x in ITEMS])
    items = [{"stt": 1, "po": "P1", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 21212, "price": 1060, "amount": 22484720, "div": 50, "kg": 0.04, "kien": 425, "net": 848.48, "gross": 849.48},
             {"stt": 2, "po": "P1", "ma_sp": "A2", "ten_sp": "Ống B & C", "unit": "chiếc", "qty": 100, "price": 500, "amount": 50000, "div": 50, "kg": 0.1, "kien": 2, "net": 10, "gross": 11}]
    return app.lot_build_record(store, {"customer": "maurieng", "doc_date": "2026-11-05", "po": "P1", "po_date": "01/11/2026", "pxk": "00000321", "hd": "00001", "tk": "3000"}, items)


def test_template_tokens_known_and_unknown():
    known, unknown = mau_rieng.template_tokens("docx", make_docx())
    assert {"so_po", "ngay", "khach_ten", "stt", "ten", "sl", "tong_sl"} <= set(known) and unknown == ["khong_co"]


def test_fill_docx_repeats_item_row_and_keeps_split_tokens(store, rec):
    prof = app.PROFILES["maurieng"]
    consts = {"name": app.HT_NAME, "addr": app.ADDR_HT, "mst": app.MST_HT, "date": app._iso_to_date, "words": app.num_to_vn_words}
    out, unknown = mau_rieng.fill_docx(make_docx(), mau_rieng.batch_values(rec, prof, consts), mau_rieng.item_values(rec))
    assert unknown == ["khong_co"]
    xml = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode()
    assert "Số PO: P1 ngày 05/11/2026 &amp; khách CÔNG TY TNHH MẪU RIÊNG THỬ" in xml  # ô bị tách qua hai đoạn chữ vẫn nhận; & được thoát đúng
    assert xml.count("<w:tr>") == 3 and "Ống A x 21.212" in xml and "Ống B &amp; C x 100" in xml  # dòng mẫu nhân lên theo 2 mặt hàng
    assert "Tổng: 21.312 / {{khong_co}}" in xml


def test_fill_xlsx_inserts_rows_and_writes_real_numbers(store, rec):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "PO {{so_po}} - {{khach_ten}}"
    ws["A3"], ws["B3"], ws["C3"] = "{{stt}}", "{{ten}}", "{{thanh_tien}}"
    ws["A4"], ws["C4"] = "Cộng", "=SUM(C3:C3)"
    buf = io.BytesIO()
    wb.save(buf)
    prof = app.PROFILES["maurieng"]
    consts = {"name": app.HT_NAME, "addr": app.ADDR_HT, "mst": app.MST_HT, "date": app._iso_to_date, "words": app.num_to_vn_words}
    out, unknown = mau_rieng.fill_xlsx(buf.getvalue(), mau_rieng.batch_values(rec, prof, consts), mau_rieng.item_values(rec))
    ws = openpyxl.load_workbook(io.BytesIO(out)).active
    assert ws["A1"].value == "PO P1 - CÔNG TY TNHH MẪU RIÊNG THỬ" and unknown == []
    assert [ws[f"B{r}"].value for r in (3, 4)] == ["Ống A", "Ống B & C"] and [ws[f"C{r}"].value for r in (3, 4)] == [22484720, 50000]  # số thật, cộng được
    assert ws["A5"].value == "Cộng"  # dòng bên dưới được đẩy xuống


def test_add_form_export_import_and_bundle(store, rec, tmp_path):
    src = tmp_path / "PLX khach.docx"
    src.write_bytes(make_docx())
    fname, known, unknown = store.add_custom_form("maurieng", str(src))
    assert fname == "PLX khach.docx" and "so_po" in known and unknown == ["khong_co"]
    assert store.custom_forms("maurieng") == ["PLX khach.docx"]
    assert app.lot_bundle_modes({"customer": "maurieng"}) == ["PKL", "VAT", "PXK", "R:PLX khach.docx"]
    res = app.lot_export(store, rec, "R:PLX khach.docx")
    assert res["fname"].endswith(".docx") and os.path.isfile(res["path"]) and any("khong_co" in p for p in res["problems"])
    assert app.lot_mode_label("R:PLX khach.docx") == "PLX khach"
    each = app.lot_export_each(store, rec)
    assert any("khong_co" in p for p in each["problems"])  # ô lạ được báo lên cùng các điểm lệch khác
    files = each["files"]
    assert [f["mode"] for f in files] == ["PKL", "VAT", "PXK", "R:PLX khach.docx"]
    # file học mang theo mẫu riêng sang máy khác
    data = store.export_learned("maurieng")
    assert "rieng/PLX khach.docx" in data["khach_moi"]["mau"]
    other = app.DedicatedDataStore(base_dir=str(tmp_path / "may2"))
    app.PROFILES.pop("maurieng", None)
    other.import_learned(data)
    assert other.custom_forms("maurieng") == ["PLX khach.docx"]
    store.remove_custom_form("maurieng", "PLX khach.docx")
    assert store.custom_forms("maurieng") == [] and "R:PLX khach.docx" not in app.lot_bundle_modes({"customer": "maurieng"})


def test_add_form_validation(store, rec, tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("x")
    with pytest.raises(ValueError, match="Word"):
        store.add_custom_form("maurieng", str(bad))
    empty = tmp_path / "e.xlsx"
    openpyxl.Workbook().save(empty)
    with pytest.raises(ValueError, match="ô thay thế"):
        store.add_custom_form("maurieng", str(empty))
    with pytest.raises(ValueError, match="không dành cho"):
        store.add_custom_form("tesa", str(empty))


def test_customers_page_add_form_and_export_button(qapp, store, rec, tmp_path):
    """Giao diện: thêm mẫu riêng ở trang Khách hàng rồi bước xuất có nút riêng cho mẫu đó."""
    from ui_qt.pages_other import CustomersPage
    page = CustomersPage(app, store)
    page.refresh(select="maurieng")
    src = tmp_path / "Mau X.docx"
    src.write_bytes(make_docx())
    page.add_form(str(src))
    assert "Đã thêm mẫu" in page.msg.text() and store.custom_forms("maurieng") == ["Mau X.docx"]
    page.close()


def test_export_step_shows_button_per_custom_form(qapp, store, rec, tmp_path):
    from ui_qt.pages_lot import ExportStep
    from ui_qt.state import Lot
    src = tmp_path / "PLX khach.docx"
    src.write_bytes(make_docx())
    store.add_custom_form("maurieng", str(src))
    lot = Lot(app, store)
    lot.select_customer("maurieng")
    lot.items = [dict(x) for x in rec["items"]]
    lot.form.update(po="P1", pxk="00000321")
    step = ExportStep(lot)
    step.refresh()
    assert list(step.rieng_btns) == ["R:PLX khach.docx"] and not step.rieng_box.isHidden() or step.rieng_btns
    step.do_export("R:PLX khach.docx")
    assert any(f["mode"] == "R:PLX khach.docx" and f["name"].endswith(".docx") for f in lot.files)
    step.close()

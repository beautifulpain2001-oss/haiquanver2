"""Kho mẫu giữ bộ chứng từ xuất gần nhất của từng khách (bản sao ở MAU_CHUNG_TU/<khách>/bo_moi_nhat) để xem mẫu thật trông như nào. Dữ liệu giả."""

import os

import pytest

import hongthien_desktop_app as app

FAKE = {"name": "CÔNG TY TNHH THỬ BỘ MỚI", "label": "BoMoi", "mst": "0100000077", "addr": "Lô Y, KCN Thử", "unit": "chiếc", "tare": 1.0, "payDays": 30,
        "extraDocs": "PLX,DNTT"}
ITEM = {"stt": 1, "po": "P1", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 1000, "price": 1000, "amount": 1000000, "div": 50, "kg": 0.04,
        "kien": 20, "net": 40, "gross": 41, "tare": 1, "hs": "48229090"}


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


def _rec(store, pxk, day="2026-11-05"):
    return app.lot_build_record(store, {"customer": "bomoi", "doc_date": day, "po": "P1", "po_date": "01/11/2026", "pxk": pxk, "hd": "00001",
                                        "tk": "3000", "pay_days": "30"}, [dict(ITEM)])


@pytest.fixture
def cust(store):
    store.save_learned_customer("bomoi", dict(FAKE), [{"code": "A1", "name": "Ống", "unit": "chiếc", "price": 1000, "div": 50, "kg": 0.04}])
    return "bomoi"


def test_no_set_before_export(store, cust):
    assert store.latest_set(cust) is None


def test_export_all_keeps_copy_of_whole_set(store, cust):
    res = app.lot_export_each(store, _rec(store, "00000321"))
    s = store.latest_set(cust)
    assert s["pxkNo"] == "00000321" and s["docDate"] == "2026-11-05"
    assert [f["mode"] for f in s["files"]] == [f["mode"] for f in res["files"] if f["mode"] != "CHECK"]
    for f in s["files"]:
        assert os.path.dirname(f["path"]) == store.latest_set_dir(cust)
        assert f["label"] and f["ext"] in ("xlsx", "docx")
    src = {f["name"]: f["path"] for f in res["files"]}
    for f in s["files"]:
        with open(f["path"], "rb") as a, open(src[f["name"]], "rb") as b:
            assert a.read() == b.read()


def test_same_lot_replaces_one_doc_new_lot_replaces_set(store, cust):
    app.lot_export_each(store, _rec(store, "00000321"))
    n = len(store.latest_set(cust)["files"])
    app.lot_export(store, _rec(store, "00000321"), "PLX")  # cùng lô: chỉ thay Phụ lục X, giữ các chứng từ khác
    assert len(store.latest_set(cust)["files"]) == n
    app.lot_export(store, _rec(store, "00000555", "2026-11-09"), "PKL")  # lô khác: bộ cũ bỏ, bộ mới bắt đầu
    s = store.latest_set(cust)
    assert s["pxkNo"] == "00000555" and [f["mode"] for f in s["files"]] == ["PKL"]
    assert sorted(os.listdir(store.latest_set_dir(cust))) == sorted([store.LATEST_META, s["files"][0]["name"]])


def test_set_survives_lot_folder_removed(store, cust):
    import shutil
    res = app.lot_export_each(store, _rec(store, "00000321"))
    shutil.rmtree(os.path.dirname(res["files"][0]["path"]))
    s = store.latest_set(cust)
    assert s and all(os.path.isfile(f["path"]) for f in s["files"])


def test_export_not_blocked_when_copy_fails(store, cust, monkeypatch):
    logged = []
    monkeypatch.setattr(app, "log_soft_error", logged.append)  # không ghi LOI_PHAN_MEM.txt vào thư mục mã nguồn
    monkeypatch.setattr(app.shutil, "copy2", lambda *a, **k: (_ for _ in ()).throw(OSError("đĩa đầy")))
    res = app.lot_export(store, _rec(store, "00000321"), "DNTT")
    assert os.path.isfile(res["path"]) and any("đĩa đầy" in m for m in logged)


def test_kho_page_shows_latest_set(qapp, store, cust):
    """Tab Kho mẫu: chọn khách, bấm "Bộ xuất gần nhất" -> danh sách file đã xuất của lô gần nhất, hình xem trước như bản in."""
    from ui_qt import pages_kho
    page = pages_kho.MauPage(app, store)
    page.resize(1400, 900)
    page.show()
    page.refresh()
    assert page.seg_moi.isHidden()  # kho chung: không có bộ xuất
    assert page.select_customer(cust)
    assert not page.seg_moi.isHidden()
    page.set_latest_mode(True)
    assert not page.docs and "chưa xuất" in page.kind_hint.text()
    app.lot_export_each(store, _rec(store, "00000321"))
    page.refresh()
    assert [d["mode"] for d in page.docs][:3] == ["PKL", "VAT", "PXK"] and all(d["kind"] == "latest" for d in page.docs)
    page.listw.setCurrentRow(0)
    assert page.view.pages and "PXK 00000321" in page.kind_hint.text() and "05/11/2026" in page.kind_hint.text()
    assert not page.open_btn.isHidden() and not page.lot_btn.isHidden() and page.edit_btn.isHidden()
    page.set_latest_mode(False)
    assert page.docs[0]["kind"] != "latest"
    page.close()


def test_preview_computes_simple_formulas():
    """Hình xem trước tính công thức đơn giản (file openpyxl ghi không có số tính sẵn); công thức lạ giữ nguyên."""
    import openpyxl
    from ui_qt.mau_render import _Formulas, _fmt_number
    ws = openpyxl.Workbook().active
    ws["D13"], ws["D14"] = 1000, 500
    ws["E13"], ws["F13"] = "=F13+1", "=ROUNDUP(D13*1.96,2)"
    ws["H13"], ws["D15"], ws["A1"], ws["B1"] = "=ROW()-12", "=SUBTOTAL(9,D13:D14)", '=IF(D13>1,"a","b")', "=B1+1"
    calc = _Formulas(ws)
    assert calc.value(13, 5) == 1961 and calc.value(13, 8) == 1 and calc.value(15, 4) == 1500
    for r, c in ((1, 1), (1, 2)):
        with pytest.raises(ValueError):
            calc.value(r, c)
    assert _fmt_number(1234567.5, "#,##0") == "1,234,568" and _fmt_number(37.1, "#,##0.00") == "37.10" and _fmt_number(0.5, "0%") == "50%"


def _pdf(path):
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(595, 842)
    with open(path, "wb") as f:
        w.write(f)


def test_pdf_pxk_and_invoice_from_lot_folder_join_set(store, cust):
    """PDF phiếu xuất kho / hóa đơn Bkav thả vào thư mục lô (sau khi xuất) cũng vào bộ mới nhất, đứng sau file Excel cùng loại."""
    res = app.lot_export_each(store, _rec(store, "00000321"))
    lot = os.path.dirname(res["files"][0]["path"])
    for n in ("PXK 321.pdf", "HĐ 321.pdf", "PO_scan.pdf"):
        _pdf(os.path.join(lot, n))
    s = store.latest_set(cust)
    modes = [f["mode"] for f in s["files"]]
    assert "PDF:PO_scan.pdf" not in modes
    assert modes.index("PDF:HĐ 321.pdf") == modes.index("VAT") + 1 and modes.index("PDF:PXK 321.pdf") == modes.index("PXK") + 1
    pdfs = {f["name"]: f for f in s["files"] if f["ext"] == "pdf"}
    assert pdfs["PXK 321.pdf"]["label"] == "Phiếu xuất kho (PDF Bkav)" and pdfs["HĐ 321.pdf"]["label"] == "Hóa đơn VAT (PDF Bkav)"
    assert all(os.path.dirname(f["path"]) == store.latest_set_dir(cust) for f in pdfs.values())
    app.lot_export(store, _rec(store, "00000321"), "DNTT")  # xuất lại cùng lô: PDF vẫn giữ
    assert "PDF:PXK 321.pdf" in [f["mode"] for f in store.latest_set(cust)["files"]]


def test_kho_page_previews_pdf(qapp, store, cust):
    from ui_qt import pages_kho
    res = app.lot_export_each(store, _rec(store, "00000321"))
    _pdf(os.path.join(os.path.dirname(res["files"][0]["path"]), "PXK 321.pdf"))
    page = pages_kho.MauPage(app, store)
    page.show()
    page.select_customer(cust)
    page.set_latest_mode(True)
    i = [d["mode"] for d in page.docs].index("PDF:PXK 321.pdf")
    page.listw.setCurrentRow(i)
    assert len(page.view.pages) == 1 and "PDF" in page.title.text()
    page.close()

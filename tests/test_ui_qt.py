"""Kiểm thử giao diện mới (PySide6) ở chế độ offscreen, không cần màn hình."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

import hongthien_desktop_app as core  # noqa: E402
from test_po_parsers import KODI_PO_TEXT  # noqa: E402
from ui_qt import dialogs, main_window as mw, widgets  # noqa: E402
import os  # noqa: E402


@pytest.fixture
def win(qapp, store, monkeypatch):
    app = qapp
    app.setStyleSheet(mw.theme.STYLE)
    shown = []
    # Không bật hộp thoại chặn trong test; ghi lại để kiểm tra
    for fn in ("info", "warn"):
        monkeypatch.setattr(widgets, fn, lambda parent, title, text, _f=fn: shown.append((_f, title, text)))
    monkeypatch.setattr(widgets, "ask", lambda *a, **k: True)
    monkeypatch.setattr(widgets, "open_folder", lambda path: shown.append(("open", path, "")))
    monkeypatch.setattr(core, "extract_text_from_pdf_or_image_offline", lambda *a, **k: KODI_PO_TEXT)
    w = mw.MainWindow(core, store)
    w.shown = shown
    w.app = app
    yield w
    w.close()


def wait(win, cond, timeout=10):
    end = time.time() + timeout
    while time.time() < end and not cond():
        win.app.processEvents()
        time.sleep(0.01)
    win.app.processEvents()
    assert cond(), "quá thời gian chờ"


def load_kodi_po(win, tmp_path):
    win.lot.step1.cards["kodi"].click()
    f = tmp_path / "po.pdf"
    f.write_bytes(b"%PDF-1.4")
    win.lot.step2.load_file(str(f))
    wait(win, lambda: bool(win.lot.lot.items))


def test_nav_switches_pages(win):
    assert win.nav.count() == len(mw.NAV) == win.pages.count()
    for i in range(win.nav.count()):
        win.nav.setCurrentRow(i)
        assert win.pages.currentIndex() == i


def test_settings_page_shows_data_folder(win, store):
    page = win.pages.widget(len(mw.NAV) - 1)
    assert any(str(store.base_dir) in lb.text() for lb in page.findChildren(mw.QLabel))


def test_step_bar_and_buttons(win):
    lot = win.lot
    assert len(lot.bar.labels) == 4 and lot.bar.current == 0 and not lot.back.isEnabled()
    assert not lot.next.isEnabled()  # chưa chọn khách thì chưa đi tiếp
    lot.step1.cards["kodi"].click()
    assert lot.step1.customer == "kodi" and lot.next.isEnabled()
    lot.next.click()
    assert lot.bar.current == 1 and lot.stack.currentWidget() is lot.step2 and lot.next.isEnabled()
    lot.next.click()
    lot.next.click()
    assert lot.bar.current == 3 and lot.stack.currentIndex() == 3 and not lot.next.isEnabled()  # thông tin chuyến và xuất hồ sơ chung một bước
    assert [lb.property("step") for lb in lot.bar.labels] == ["done", "done", "done", "current"]
    lot.go(99)
    assert lot.bar.current == 3
    lot.go(-5)
    assert lot.bar.current == 0 and not lot.back.isEnabled()


def test_customer_and_po_are_separate_steps(win):
    lot = win.lot
    assert lot.stack.currentWidget() is lot.step1
    assert not hasattr(lot.step1, "drop")  # bước chọn khách không có nút chọn file PO
    lot.step1.cards["tesa"].click()
    lot.next.click()
    assert lot.stack.currentWidget() is lot.step2 and lot.step2.drop.isEnabled()
    assert "Tesa" in lot.step2.who.text()


def test_customer_step_shows_customer_info(win):
    win.lot.step1.cards["kodi"].click()
    txt = win.lot.step1.info_text.text()
    assert "KODI NEW MATERIAL" in txt and "2400903592" in txt


def test_pick_customer_selects_only_one_card(win):
    step = win.lot.step1
    assert set(step.cards) >= {"shirai", "kodi", "tesa"}
    step.cards["tesa"].click()
    step.cards["shirai"].click()
    assert [k for k, b in step.cards.items() if b.isChecked()] == ["shirai"]


def test_load_po_in_background_fills_table(win, tmp_path):
    load_kodi_po(win, tmp_path)
    assert "03102026-01KDHT" in win.lot.step2.status.text()
    win.lot.go(2)
    assert win.lot.step3.table.rowCount() == 2
    assert "2 dòng" in win.lot.step3.summary.text()


def test_unreadable_po_shows_message_and_keeps_going(win, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "extract_text_from_pdf_or_image_offline", lambda *a, **k: "trống")
    win.lot.step1.cards["kodi"].click()
    step = win.lot.step2
    f = tmp_path / "x.pdf"
    f.write_bytes(b"x")
    step.load_file(str(f))
    wait(win, lambda: not step.busy.isVisible() and "Không" in step.status.text())
    win.lot.go(1)
    assert win.lot.lot.items == [] and win.lot.next.isEnabled()


def test_load_without_customer_warns(win, tmp_path):
    win.lot.step2.load_file(str(tmp_path / "x.pdf"))
    assert win.shown and win.shown[0][0] == "warn"


def test_item_dialog_adds_and_flags_missing_norm(win, tmp_path):
    load_kodi_po(win, tmp_path)
    lot = win.lot.lot
    dlg = dialogs.ItemDialog(lot)
    for k, v in dict(ma_sp="Z1", ten_sp="Ống mới", qty="100", price="1000", div="0", kg="0").items():
        dlg.edits[k].setText(v)
    dlg.save()
    win.lot.go(2)
    assert win.lot.step3.table.rowCount() == 3
    assert "Thiếu kg/chiếc" in win.lot.step3.table.item(2, 14).text()
    assert "1 dòng cần xem" in win.lot.step3.summary.text()


def test_item_dialog_bad_number_keeps_dialog_open(win, tmp_path):
    load_kodi_po(win, tmp_path)
    dlg = dialogs.ItemDialog(win.lot.lot)
    dlg.edits["ten_sp"].setText("A")
    dlg.edits["qty"].setText("abc")
    dlg.save()
    assert win.shown[-1][0] == "warn" and len(win.lot.lot.items) == 2


def test_delete_row_needs_selection(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(2)
    win.lot.step3.delete()
    assert win.shown[-1][0] == "warn" and len(win.lot.lot.items) == 2
    win.lot.step3.table.selectRow(0)
    win.lot.step3.delete()
    assert len(win.lot.lot.items) == 1


def test_info_step_edits_flow_into_record(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(3)
    e = win.lot.step4.edits
    e["pxk"].setText("0000555")
    e["pxk"].textEdited.emit("0000555")
    assert win.lot.lot.record()["pxkNo"] == "0000555"
    assert not win.lot.step4.groups["pay"].isVisibleTo(win.lot.step4)  # chỉ khách Best mới có hạn thanh toán


def test_export_all_then_save_then_reopen(win, tmp_path, store):
    load_kodi_po(win, tmp_path)
    win.lot.lot.form.update(pxk="0000777", hd="0000888")
    win.lot.go(4)
    step = win.lot.step5
    assert step.big.isEnabled()
    step.do_export("ALL")
    assert len(step.done_lines) == 5 and "Đã xuất 5 file" in step.msg.text()  # mỗi chứng từ một file
    step.do_save()
    assert win.lot.lot.saved
    win.nav.setCurrentRow(2)
    rows = [win.records.table.item(r, 2).text() for r in range(win.records.table.rowCount())]
    assert "03102026-01KDHT" in rows
    win.records.table.selectRow(rows.index("03102026-01KDHT"))
    win.records.reopen()
    assert win.nav.currentRow() == 0 and win.lot.bar.current == 2 and win.lot.lot.form["pxk"] == "0000777"


def test_export_blocked_without_items(win):
    win.lot.step1.cards["kodi"].click()
    win.lot.go(4)
    assert not win.lot.step5.big.isEnabled()
    assert "Chưa có dòng hàng" in win.lot.step5.check_lines[0]


def test_new_lot_resets(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(4)
    win.lot.step5.on_new()
    assert win.lot.lot.customer is None and win.lot.bar.current == 0 and not win.lot.next.isEnabled()


def test_check_text_is_wrapped_and_complete(win, tmp_path):
    load_kodi_po(win, tmp_path)
    lot = win.lot.lot
    long_name = "Ống lõi giấy phi 33.02 x 2.65 x 1750mm_51036 blue red (39817-91750-00)- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013123)" * 2
    lot.items[0]["ten_sp"] = long_name
    lot.items[0]["kg"] = 0
    win.lot.go(4)
    step = win.lot.step5
    assert step.checks.wordWrap()  # tự xuống dòng thay vì cắt chữ
    assert any("TAH-COC-013123" in t for t in step.check_lines)  # hiện đủ tên hàng dài
    assert long_name[:60] in step.checks.text()


def test_export_shows_each_file_in_done_list(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(4)
    win.lot.step5.do_export("ALL")
    text = " ".join(win.lot.step5.done_lines)
    for label in ("Hóa đơn VAT", "Phiếu xuất kho", "Đề nghị thanh toán", "Kiểm tra chéo"):
        assert label in text


# --------------------------------------------------------------------------- Cài đặt công ty / Khách hàng
def test_settings_company_form_saves_and_applies(win, store):
    page = win.settings
    assert page.company["name"].text() == "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN"
    page.company["name"].setText("CÔNG TY TNHH GIAO DIỆN MỚI")
    page.company["mst"].setText("0109998887")
    page.save_company()
    assert core.HT_NAME == "CÔNG TY TNHH GIAO DIỆN MỚI" and core.MST_HT == "0109998887"
    assert "Đã lưu" in page.company_msg.text()
    assert store.company_info()["mst"] == "0109998887"


def test_settings_company_bad_input_warns_and_keeps_old(win):
    page = win.settings
    page.company["mst"].setText("abc")
    page.save_company()
    assert win.shown[-1][0] == "warn" and "Mã số thuế" in win.shown[-1][2]
    assert core.MST_HT == "2300723980"


def test_settings_defaults_button_refills_form(win):
    page = win.settings
    page.company["name"].setText("X")
    page.fill_defaults()
    assert page.company["name"].text() == "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN"


def test_settings_page_opens_instantly_even_if_ocr_check_is_slow(win, monkeypatch):
    def slow():
        time.sleep(0.6)
        return True
    monkeypatch.setattr(core, "_OCR_OK", None)
    monkeypatch.setattr(core, "ocr_available", slow)
    t = time.time()
    win.settings.refresh()
    assert time.time() - t < 0.3 and "Đang kiểm tra" in win.settings.ocr.text()  # trang hiện ngay, không chờ OCR
    wait(win, lambda: "sẵn sàng" in win.settings.ocr.text())


def test_customers_edit_saves_and_updates_lot_step(win, store):
    win.nav.setCurrentRow(4)
    page = win.customers
    page.table.selectRow(page.keys.index("kodi"))
    assert page.form.edits["name"].text() == "CÔNG TY TNHH KODI NEW MATERIAL VIỆT NAM"
    page.form.edits["name"].setText("CÔNG TY KODI TÊN SỬA")
    page.form.edits["addr"].setText("Địa chỉ đã sửa")
    page.save()
    assert core.PROFILES["kodi"]["name"] == "CÔNG TY KODI TÊN SỬA" and store.profile_overrides["kodi"]["addr"] == "Địa chỉ đã sửa"
    win.lot.step1.cards["kodi"].click()
    assert "CÔNG TY KODI TÊN SỬA" in win.lot.step1.info_text.text()  # bước chọn khách thấy thông tin mới


def test_customers_bad_mst_warns(win):
    win.nav.setCurrentRow(4)
    win.customers.table.selectRow(win.customers.keys.index("tesa"))
    win.customers.form.edits["mst"].setText("12")
    win.customers.save()
    assert win.shown[-1][0] == "warn"


def test_customers_add_new_appears_as_card(win, store):
    key = store.add_customer({"name": "CÔNG TY TNHH THỬ KHÁCH", "mst": "0311111111", "addr": "Hải Phòng"})
    win.customers.changed.emit()
    assert key in win.lot.step1.cards


# --------------------------------------------------------------------------- Danh mục: theo tháng / theo khách hàng
def add_record(store, customer, doc_date, tk="", po="PO-X", folder_files=True):
    base = next(r for r in store.records if r["customer"] == customer)
    rec = dict(base, id=f"HS-{doc_date}-{po}", docDate=doc_date, tkNo=tk, poNumber=po, zone="WORKING", files=dict(base.get("files") or {}))
    store.records.append(rec)
    if folder_files:
        os.makedirs(store.get_record_folder_path(rec), exist_ok=True)
    return rec


def this_month():
    import datetime
    return datetime.date.today().strftime("%Y-%m")


def test_catalog_has_month_and_customer_views_first(win):
    tabs = [win.catalog.tabs.tabText(i) for i in range(win.catalog.tabs.count())]
    assert tabs[0] == "Hồ sơ theo tháng" and tabs[1] == "Hồ sơ theo khách hàng" and tabs[2].startswith("Thư viện cân nặng")


def test_month_view_defaults_to_current_month(win, store):
    import datetime
    today = datetime.date.today()
    add_record(store, "kodi", today.strftime("%Y-%m-%d"), tk="306000000001", po="PO-THANG-NAY")
    add_record(store, "tesa", "2020-03-15", tk="306000000002", po="PO-CU")
    win.nav.setCurrentRow(3)
    mv = win.catalog.by_month
    assert mv.combo.currentData() == this_month()
    assert [mv.table.item(r, 4).text() for r in range(mv.table.rowCount())] == ["PO-THANG-NAY"]  # chỉ hồ sơ tháng này
    assert "1 hồ sơ" in mv.summary.text() and "1 đã khai" in mv.summary.text()


def test_month_view_switch_months_and_empty_current_month(win, store):
    add_record(store, "tesa", "2020-03-15", tk="306000000002", po="PO-CU")
    win.nav.setCurrentRow(3)
    mv = win.catalog.by_month
    assert mv.combo.currentData() == this_month() and mv.table.rowCount() == 0 and "chưa có hồ sơ" in mv.empty.text()
    mv.prev.click()  # lùi về tháng trước đó có hồ sơ
    while mv.combo.currentData() != "2020-03" and mv.prev.isEnabled():
        mv.prev.click()
    assert mv.combo.currentData() == "2020-03" and [mv.table.item(r, 4).text() for r in range(mv.table.rowCount())] == ["PO-CU"]
    assert mv.combo.currentText() == "Tháng 03/2020"
    while mv.next.isEnabled():
        mv.next.click()
    assert mv.combo.currentData() == this_month()


def test_customer_view_lists_declared_customs_and_folder_link(win, store, monkeypatch):
    t1 = add_record(store, "tesa", "2026-09-10", tk="306111111111", po="PO-T1", folder_files=True)
    add_record(store, "tesa", "2026-08-10", tk="", po="PO-CHUA-KHAI")
    add_record(store, "kodi", "2026-09-11", tk="306222222222", po="PO-K1")
    win.nav.setCurrentRow(3)
    win.catalog.tabs.setCurrentIndex(1)
    cv = win.catalog.by_customer
    labels = [cv.list.item(i).text() for i in range(cv.list.count())]
    assert any(t.startswith("Tesa") for t in labels) and any(t.startswith("Kodi") for t in labels)
    cv.list.setCurrentRow(cv.keys.index("tesa"))
    tk_col = [cv.table.item(r, 2).text() for r in range(cv.table.rowCount())]
    assert "306111111111" in tk_col and "Chưa khai" not in tk_col  # mặc định chỉ hiện tờ khai đã khai
    assert not any("PO-K1" in cv.table.item(r, 4).text() for r in range(cv.table.rowCount()))  # không lẫn khách khác
    r = [cv.table.item(i, 4).text() for i in range(cv.table.rowCount())].index("PO-T1")
    folder = win.catalog.by_customer.table.folder_of(t1)
    assert cv.table.item(r, 9).text() == folder  # đường dẫn thư mục trên máy
    btn = cv.table.cellWidget(r, 10)
    assert btn.isEnabled()
    btn.click()
    assert ("open", folder, "") in win.shown
    cv.all_box.setChecked(True)
    assert "PO-CHUA-KHAI" in [cv.table.item(i, 4).text() for i in range(cv.table.rowCount())]


def test_catalog_lists_only_real_folders_like_declarations_page(win, store):
    """Danh mục và 'Tờ khai đang có' dùng chung nguồn là thư mục thật: hồ sơ chưa có thư mục không hiện, thư mục chưa có hồ sơ vẫn hiện."""
    add_record(store, "kodi", "2026-09-11", tk="306222222222", po="PO-CHUA-XUAT", folder_files=False)
    d = os.path.join(store.customs_root(), "Arizon", "2026_Thang_11", "2026-11-02")
    os.makedirs(d)
    open(os.path.join(d, "308389024810_tokhai.pdf"), "w").write("x")
    win.nav.setCurrentRow(3)
    win.catalog.tabs.setCurrentIndex(1)
    cv = win.catalog.by_customer
    cv.list.setCurrentRow(next(i for i in range(cv.list.count()) if cv.list.item(i).text().startswith("Arizon")))
    assert "308389024810" in [cv.table.item(r, 2).text() for r in range(cv.table.rowCount())]
    assert cv.table.cellWidget(0, 10).isEnabled()
    cv.list.setCurrentRow(cv.keys.index("kodi"))
    cv.all_box.setChecked(True)
    assert "PO-CHUA-XUAT" not in [cv.table.item(i, 4).text() for i in range(cv.table.rowCount())]


def test_catalog_and_customer_pages_list_data(win):
    win.nav.setCurrentRow(3)
    win.catalog.tabs.setCurrentIndex(2)
    assert win.catalog.weights.model().rowCount() > 100 and win.catalog.erp.model().rowCount() > 1000
    win.nav.setCurrentRow(4)
    assert {"Shirai", "Kodi", "Tesa"} <= {win.customers.table.item(r, 0).text() for r in range(win.customers.table.rowCount())}


def test_export_files_land_in_customs_customer_month_day_folder(win, tmp_path, store):
    load_kodi_po(win, tmp_path)
    win.lot.lot.form["doc_date"] = "2026-11-01"
    win.lot.go(4)
    win.lot.step5.do_export("ALL")
    day = os.path.join(store.base_dir, "HAI_QUAN", "Kodi", "2026_Thang_11", "2026-11-01")
    files = [f for f in win.lot.lot.files]
    gen = os.path.join(day, "DO_PHAN_MEM_TAO")  # chứng từ do phần mềm tạo nằm trong thư mục con; bên ngoài dành cho scan, PDF Bkav, file hải quan
    assert len(files) == 5 and all(os.path.dirname(f["path"]) == gen for f in files)
    assert sorted(os.listdir(gen)) == sorted([os.path.basename(f["path"]) for f in files] + ["PO_goc_po.pdf"])  # kèm bản sao PO gốc
    assert os.listdir(day) == ["DO_PHAN_MEM_TAO"]
    assert os.listdir(os.path.join(store.base_dir, "HAI_QUAN", "Kodi")) == ["2026_Thang_11"]
    win.lot.step5.do_save()
    win.lot.go(4)
    win.lot.step5.do_export("VAT")  # xuất lại cùng lô: vẫn cùng thư mục, không tạo thêm
    assert os.listdir(os.path.join(store.base_dir, "HAI_QUAN", "Kodi", "2026_Thang_11")) == ["2026-11-01"]
    rec = next(r for r in store.records if r["customer"] == "kodi" and r["poNumber"] == "03102026-01KDHT" and r["docDate"] == "2026-11-01")
    assert rec["folder"] == os.path.join("HAI_QUAN", "Kodi", "2026_Thang_11", "2026-11-01")  # hồ sơ nhớ thư mục của nó


# --------------------------------------------------------------------------- Shirai: chọn ngày giao để khai; dữ liệu học
SHIRAI_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "po_shirai_gia.xls")


def load_shirai_po(win):
    win.lot.step1.cards["shirai"].click()
    win.lot.step2.load_file(SHIRAI_FIXTURE)
    wait(win, lambda: bool(win.lot.lot.items))


def test_delivery_dates_are_checkboxes_default_all_one_invoice(win):
    assert not win.lot.step2.dates_box.isVisibleTo(win.lot.step2)  # chưa nạp PO: không hiện
    load_shirai_po(win)
    step = win.lot.step2
    assert step.dates_box.isVisibleTo(step) and list(step.date_checks) == ["25.10", "29.10"]
    assert all(cb.isChecked() for cb in step.date_checks.values()) and len(win.lot.lot.items) == 4
    assert "(2 dòng)" in step.date_checks["25.10"].text()


def test_uncheck_a_date_makes_invoice_for_the_other_date_only(win):
    load_shirai_po(win)
    step = win.lot.step2
    step.date_checks["25.10"].setChecked(False)
    assert win.lot.lot.selected_dates == ["29.10"] and len(win.lot.lot.items) == 2
    assert "29.10" in step.status.text() and "2 dòng" in step.status.text()
    win.lot.go(2)
    assert win.lot.step3.table.rowCount() == 2


def test_cannot_uncheck_every_date(win):
    load_shirai_po(win)
    step = win.lot.step2
    step.date_checks["25.10"].setChecked(False)
    step.date_checks["29.10"].setChecked(False)
    assert win.shown[-1][0] == "warn" and "ít nhất một ngày" in win.shown[-1][2]
    assert len(win.lot.lot.items) == 2 and step.date_checks["29.10"].isChecked()  # khôi phục


def test_single_date_po_hides_date_picker(win, tmp_path, monkeypatch):
    load_kodi_po(win, tmp_path)
    assert not win.lot.step2.dates_box.isVisibleTo(win.lot.step2)


def test_settings_import_learned_file(win, store, tmp_path):
    import json
    f = tmp_path / "hoc.json"
    f.write_text(json.dumps({"item_mem": {"Mặt hàng thử": {"div": 50, "kg": 0.05, "hs": ""}}}), encoding="utf-8")
    win.settings.import_learned(str(f))
    assert store.item_mem["Mặt hàng thử"]["div"] == 50 and "Đã thêm 1" in win.settings.learn_msg.text()
    bad = tmp_path / "hong.json"
    bad.write_text("{không phải json", encoding="utf-8")
    win.settings.import_learned(str(bad))
    assert win.shown[-1][0] == "warn"


def test_declarations_page_lists_folders_and_opens_link(win, monkeypatch):
    opened = []
    monkeypatch.setattr("ui_qt.widgets.open_folder", lambda p: opened.append(p))
    d = os.path.join(win.store.base_dir, "HAI_QUAN", "Best", "2026_Thang_10", "2026-10-29")
    os.makedirs(d)
    win.nav.setCurrentRow(1)
    page = win.declarations
    assert any(o["path"] == d for o in page.shown)
    row = [o["path"] for o in page.shown].index(d)
    page.table.cellWidget(row, 6).click()
    assert opened == [d]


def test_big_tables_open_instantly_and_data_tong_cells_are_editable(win):
    """Danh mục (hàng nghìn dòng ERP) và Data tổng dùng model ảo: không lag; sửa ô kg/SL-kiện được lưu."""
    from PySide6.QtCore import Qt
    win.store.erp_catalog = [{"ma_sp": f"TM{i}", "ten_sp": f"Sản phẩm {i}", "mota": "m"} for i in range(5000)]
    win.store.data_tong = [{"khach": "K", "ten": f"Sản phẩm {i}", "kg": 0.1, "kg_nguon": "erp", "kien": 0, "kien_nguon": ""} for i in range(9000)]
    t = time.time()
    win.nav.setCurrentRow(3)
    win.catalog.tabs.setCurrentIndex(3)
    win.nav.setCurrentRow(5)
    assert time.time() - t < 3 and win.data_tong.model.rowCount() == 9000
    idx = win.data_tong.model.index(0, 6)
    assert win.data_tong.model.setData(idx, "40") and win.store.data_tong[0]["kien"] == 40 and win.store.data_tong[0]["kien_nguon"] == "tay"
    assert not (win.data_tong.model.flags(win.data_tong.model.index(0, 1)) & Qt.ItemIsEditable)  # chỉ sửa ô kg và SL/kiện


def test_add_files_dialog_builds_plan_and_copies(win, tmp_path):
    from ui_qt.pages_other import AddFilesDialog
    from PySide6.QtCore import QDate
    src = tmp_path / "in"
    src.mkdir()
    for n in ("00000113_308389723740.xls", "pxk 113.pdf", "HĐ 00000008.pdf", "IV PK.xlsx"):
        (src / n).write_text("x")
    dlg = AddFilesDialog(win.core, win.store)
    dlg.cust.setCurrentText("Able")
    dlg.day.setDate(QDate(2026, 4, 1))
    dlg.paths = [str(src / n) for n in sorted(os.listdir(src))]
    dlg.rebuild()
    assert dlg.ok.isEnabled() and dlg.table.rowCount() == 4
    names = {dlg.table.item(r, 2).text() for r in range(4)}
    assert {"PXK 113.pdf", "HĐ 113.pdf", "00000113_308389723740.xls", "invoice_IV PK.xlsx"} == names
    dlg.add()
    day = os.path.join(win.store.customs_root(), "Able", "2026_Thang_04", "2026-04-01")
    assert os.path.isfile(os.path.join(day, "HĐ 113.pdf")) and os.path.isfile(os.path.join(day, "DO_PHAN_MEM_TAO", "invoice_IV PK.xlsx")) and dlg.added == 4


def _read_lot(win, store):
    """Lô giả có PO được đọc theo từng dòng: 1 đọc đủ, 1 suy ra, 1 chưa đọc được."""
    from PySide6.QtCore import Qt as _Qt  # noqa: F401
    win.lot.step1.cards["kodi"].click()
    base = dict(win.lot.lot.new_item_values(), ten_sp="Hàng A", qty=100, price=1000, kg=0.1, div=10)
    lot = win.lot.lot
    lot.items = [dict(lot.core.lot_item_from_values(store, "kodi", base, "1.0"), read="ok"),
                 dict(lot.core.lot_item_from_values(store, "kodi", dict(base, ten_sp="Hàng B"), "1.0"), read="suy_ra", read_note="suy ra từ thành tiền"),
                 {"stt": 3, "po": "P", "hs": "", "ma_sp": "", "ten_sp": "", "unit": "cái", "qty": 0, "price": 0, "amount": 0, "div": 0, "kg": 0, "kien": 0, "net": 0.0,
                  "gross": 0.0, "tare": 0.0, "read": "loi", "read_note": "Không đọc được dòng này, hãy nhập tay"}]
    return lot


def test_items_step_shows_read_status_per_line_and_blocks_export(win, store):
    lot = _read_lot(win, store)
    st = win.lot.step3
    st.refresh()
    assert not st.table.isColumnHidden(1)
    assert [st.table.item(r, 1).text() for r in range(3)] == ["✅ Đọc đủ", "🟡 Suy ra, kiểm tra", "❌ Chưa đọc được"]
    assert "Chưa đọc được 1/3 dòng" in st.banner.text() and "dòng 3" in st.banner.text() and st.banner.objectName() == "banner_bad"
    st.set_filter("bad")
    assert [st.table.isRowHidden(r) for r in range(3)] == [True, True, False]
    st.set_filter("all")
    st.table.selectRow(0)
    st.goto_next()
    assert st.selected() == 2  # nhảy tới dòng chưa đọc được trước
    errors, warns = lot.validate()
    assert errors and "dòng 3" in errors[0]
    lot.save_item({"po": "P", "ma_sp": "X", "ten_sp": "Hàng C", "hs": "48229090", "unit": "cái", "qty": "5", "price": "10", "div": "1", "kg": "1"}, 2)
    assert lot.items[2]["read"] == "tay"
    errors, warns = lot.validate()
    assert not errors and any("Dòng 2" in w for w in warns)


def test_lookup_dialog_searches_and_adds_lines(win, store):
    from ui_qt.dialogs import LookupDialog
    win.lot.step1.cards["kodi"].click()
    lot = win.lot.lot
    lot.items = []
    dlg = LookupDialog(lot)
    first = dlg.hits[0]
    dlg.search.setText(first["ma_sp"] or first["ten_sp"][:6])
    dlg.run_search()
    assert dlg.table.rowCount() >= 1
    dlg.add()  # chưa nhập số lượng: báo ngay cạnh ô, không thêm
    assert "số lượng" in dlg.msg.text() and not lot.items
    dlg.qty.setText("250")
    dlg.add()
    assert len(lot.items) == 1 and lot.items[0]["qty"] == 250 and lot.items[0]["read"] == "tay" and "Đã thêm" in dlg.msg.text()
    dlg.search.setText("khong-co-mat-hang-nay")
    dlg.run_search()
    assert dlg.table.rowCount() == 0 and "Không thấy" in dlg.empty.text()


def test_customers_page_has_learn_button_and_records_export(win, store, tmp_path):
    from ui_qt.pages_other import CustomersPage, RecordsPage  # noqa: F401
    assert "Học khách mới" in win.customers.learn_btn.text()
    out = tmp_path / "log.xlsx"
    win.records.export_log(str(out))
    import openpyxl
    ws = openpyxl.load_workbook(out).active
    assert ws.cell(1, 3).value == "Khách hàng" and ws.max_row == 1 + len(store.records)


def test_po_read_marks_status_for_every_customer_and_shows_banner(win, tmp_path):
    """Trạng thái đọc từng dòng áp cho mọi khách, không chỉ Able."""
    load_kodi_po(win, tmp_path)
    lot = win.lot.lot
    assert lot.items and all(it.get("read") in ("ok", "suy_ra", "loi") for it in lot.items)
    win.lot.go(2)
    st = win.lot.step3
    assert not st.table.isColumnHidden(1) and st.banner.isVisibleTo(st)
    assert st.table.item(0, 1).text() in ("✅ Đọc đủ", "🟡 Suy ra, kiểm tra", "❌ Chưa đọc được")


def test_load_po_reports_progress_and_hides_bar_when_done(win, tmp_path, monkeypatch):
    seen = []
    orig = win.lot.lot.read_po

    def fake(path, append=False, progress=None):
        if progress:
            progress("Đang đọc trang 1/2…", 0.25)
            progress("Đang đọc trang 2/2 · 5 dòng đã xong", 0.75)
        return orig(path, append)

    monkeypatch.setattr(win.lot.lot, "read_po", fake)
    win.lot.step1.cards["kodi"].click()
    st = win.lot.step2
    monkeypatch.setattr(st, "on_progress", lambda t, f, _o=st.on_progress: (seen.append((t, f)), _o(t, f)))
    f = tmp_path / "po.pdf"
    f.write_bytes(b"%PDF-1.4")
    st.load_file(str(f))
    wait(win, lambda: bool(win.lot.lot.items))
    assert [round(x[1], 2) for x in seen] == [0.25, 0.75] and "trang 2/2" in seen[-1][0]
    assert not st.busy.isVisible()


def test_po_viewer_opens_beside_table_and_follows_selected_row(win, tmp_path):
    pdf = tmp_path / "po.pdf"
    core.make_scanned_pdf(str(pdf), ["Trang 1", "Trang 2"])
    win.lot.step1.cards["kodi"].click()
    lot = win.lot.lot
    base = dict(lot.new_item_values(), ten_sp="Hàng A", qty=10, price=100, kg=0.1, div=5)
    lot.items = [dict(lot.core.lot_item_from_values(win.store, "kodi", base, "1.0"), read="ok", page=1, po_file=str(pdf)),
                 dict(lot.core.lot_item_from_values(win.store, "kodi", dict(base, ten_sp="Hàng B"), "1.0"), read="suy_ra", page=2, po_file=str(pdf))]
    lot.po_files = [str(pdf)]
    win.lot.go(2)
    st = win.lot.step3
    assert st.viewer.isVisibleTo(st) and st.viewer.pages == 2  # có dòng cần soát: khung xem PO mở sẵn
    st.table.selectRow(1)
    assert st.viewer.page == 1 and "trang 2/2" in st.viewer.title.text()
    st.table.selectRow(0)
    assert st.viewer.page == 0
    st.hide_viewer()
    assert not st.viewer.isVisibleTo(st)


def test_finish_step_merges_info_and_export_and_flags_missing_numbers(win):
    win.lot.step1.cards["kodi"].click()
    win.lot.go(3)
    fin = win.lot.finish
    assert fin.info is win.lot.step4 and fin.export is win.lot.step5 and win.lot.stack.currentWidget() is fin
    e = win.lot.step4.edits["pxk"]
    win.lot.lot.form["pxk"] = ""
    win.lot.step4.mark_missing()
    assert e.property("warn") is True and "Chưa có số PXK" in e.placeholderText()
    e.setText("0000777")
    win.lot.step4.on_edit("pxk", "0000777")
    assert e.property("warn") is False


def test_pxk_autofills_next_number_once_and_user_edit_sticks(win, store):
    store.records = [{"id": "HS-X", "customer": "kodi", "pxkNo": "0000294", "docDate": "2026-10-01"}]
    win.lot.step1.cards["kodi"].click()
    win.lot.lot.form["pxk"] = ""
    win.lot.go(3)
    e = win.lot.step4.edits["pxk"]
    assert e.text() == "0000295" and win.lot.lot.form["pxk"] == "0000295" and win.lot.lot.pxk_auto
    win.lot.step4.on_edit("pxk", "0000999")  # người dùng sửa
    e.setText("0000999")
    win.lot.go(2)
    win.lot.go(3)
    assert e.text() == "0000999" and not win.lot.lot.pxk_auto
    e.setText("")
    win.lot.step4.on_edit("pxk", "")
    win.lot.go(3)
    assert e.text() == ""  # đã tự xóa thì không điền lại


def test_pick_numbers_dialog_lists_numbers_and_saves_choice(win, tmp_path):
    from ui_qt.dialogs import PickNumbersDialog
    win.lot.step1.cards["kodi"].click()
    lot = win.lot.lot
    base = dict(lot.new_item_values(), ten_sp="Hàng A", qty=211000504, price=100, kg=0.1, div=5)
    it = lot.core.lot_item_from_values(win.store, "kodi", base, "1.0")
    it["src"] = "10 211000504 Hàng A 100 PC 75,430 7,543,000"
    lot.items = [it]
    d = PickNumbersDialog(lot, 0)
    assert [d.boxes["qty"].itemText(i) for i in range(d.boxes["qty"].count())] == ["10", "211000504", "100", "75,430", "7,543,000"]
    d.boxes["qty"].setEditText("0")
    d.save()
    assert not d.result() and "lớn hơn 0" in d.msg.text()  # lỗi báo ngay trong hộp thoại, không đóng
    d.boxes["qty"].setEditText("100")
    d.boxes["price"].setEditText("75,430")
    d.save()
    assert d.result() and lot.items[0]["qty"] == 100 and lot.items[0]["price"] == 75430 and lot.items[0]["read"] == "tay"

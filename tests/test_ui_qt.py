"""Kiểm thử giao diện mới (PySide6) ở chế độ offscreen, không cần màn hình."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

import hongthien_desktop_app as core  # noqa: E402
from test_po_parsers import KODI_PO_TEXT  # noqa: E402
from ui_qt import dialogs, main_window as mw, widgets  # noqa: E402


@pytest.fixture
def win(store, monkeypatch):
    app = mw.QApplication.instance() or mw.QApplication([])
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
    step = win.lot.step1
    step.cards["kodi"].click()
    f = tmp_path / "po.pdf"
    f.write_bytes(b"%PDF-1.4")
    step.load_file(str(f))
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
    assert lot.bar.current == 0 and not lot.back.isEnabled()
    assert not lot.next.isEnabled()  # chưa chọn khách thì chưa đi tiếp
    lot.step1.cards["kodi"].click()
    assert lot.step1.customer == "kodi" and lot.next.isEnabled()
    lot.next.click()
    lot.next.click()
    assert lot.bar.current == 2 and lot.stack.currentIndex() == 2
    assert [lb.property("step") for lb in lot.bar.labels] == ["done", "done", "current", "todo"]
    lot.next.click()
    assert lot.bar.current == 3 and not lot.next.isEnabled()
    lot.go(99)
    assert lot.bar.current == 3
    lot.go(-5)
    assert lot.bar.current == 0 and not lot.back.isEnabled()


def test_pick_customer_selects_only_one_card(win):
    step = win.lot.step1
    assert set(step.cards) >= {"shirai", "kodi", "tesa"}
    step.cards["tesa"].click()
    step.cards["shirai"].click()
    assert [k for k, b in step.cards.items() if b.isChecked()] == ["shirai"]


def test_load_po_in_background_fills_table(win, tmp_path):
    load_kodi_po(win, tmp_path)
    assert "03102026-01KDHT" in win.lot.step1.status.text()
    win.lot.go(1)
    assert win.lot.step2.table.rowCount() == 2
    assert "2 dòng" in win.lot.step2.summary.text()


def test_unreadable_po_shows_message_and_keeps_going(win, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "extract_text_from_pdf_or_image_offline", lambda *a, **k: "trống")
    step = win.lot.step1
    step.cards["kodi"].click()
    f = tmp_path / "x.pdf"
    f.write_bytes(b"x")
    step.load_file(str(f))
    wait(win, lambda: not step.busy.isVisible() and "Không" in step.status.text())
    assert win.lot.lot.items == [] and win.lot.next.isEnabled()


def test_load_without_customer_warns(win, tmp_path):
    win.lot.step1.load_file(str(tmp_path / "x.pdf"))
    assert win.shown and win.shown[0][0] == "warn"


def test_item_dialog_adds_and_flags_missing_norm(win, tmp_path):
    load_kodi_po(win, tmp_path)
    lot = win.lot.lot
    dlg = dialogs.ItemDialog(lot)
    for k, v in dict(ma_sp="Z1", ten_sp="Ống mới", qty="100", price="1000", div="0", kg="0").items():
        dlg.edits[k].setText(v)
    dlg.save()
    win.lot.go(1)
    assert win.lot.step2.table.rowCount() == 3
    assert "Thiếu kg/chiếc" in win.lot.step2.table.item(2, 13).text()
    assert "1 dòng cần xem" in win.lot.step2.summary.text()


def test_item_dialog_bad_number_keeps_dialog_open(win, tmp_path):
    load_kodi_po(win, tmp_path)
    dlg = dialogs.ItemDialog(win.lot.lot)
    dlg.edits["ten_sp"].setText("A")
    dlg.edits["qty"].setText("abc")
    dlg.save()
    assert win.shown[-1][0] == "warn" and len(win.lot.lot.items) == 2


def test_delete_row_needs_selection(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(1)
    win.lot.step2.delete()
    assert win.shown[-1][0] == "warn" and len(win.lot.lot.items) == 2
    win.lot.step2.table.selectRow(0)
    win.lot.step2.delete()
    assert len(win.lot.lot.items) == 1


def test_info_step_edits_flow_into_record(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(2)
    e = win.lot.step3.edits
    e["pxk"].setText("0000555")
    e["pxk"].textEdited.emit("0000555")
    assert win.lot.lot.record()["pxkNo"] == "0000555"
    assert not win.lot.step3.groups["pay"].isVisibleTo(win.lot.step3)  # chỉ khách Best mới có hạn thanh toán


def test_export_all_then_save_then_reopen(win, tmp_path, store):
    load_kodi_po(win, tmp_path)
    win.lot.lot.form.update(pxk="0000777", hd="0000888")
    win.lot.go(3)
    step = win.lot.step4
    assert step.big.isEnabled()
    step.do_export("ALL")
    assert len(step.done_lines) == 5 and "Đã xuất 5 file" in step.msg.text()  # mỗi chứng từ một file
    step.do_save()
    assert win.lot.lot.saved
    win.nav.setCurrentRow(1)
    rows = [win.records.table.item(r, 2).text() for r in range(win.records.table.rowCount())]
    assert "03102026-01KDHT" in rows
    win.records.table.selectRow(rows.index("03102026-01KDHT"))
    win.records.reopen()
    assert win.nav.currentRow() == 0 and win.lot.bar.current == 1 and win.lot.lot.form["pxk"] == "0000777"


def test_export_blocked_without_items(win):
    win.lot.step1.cards["kodi"].click()
    win.lot.go(3)
    assert not win.lot.step4.big.isEnabled()
    assert "Chưa có dòng hàng" in win.lot.step4.check_lines[0]


def test_new_lot_resets(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(3)
    win.lot.step4.on_new()
    assert win.lot.lot.customer is None and win.lot.bar.current == 0 and not win.lot.next.isEnabled()


def test_catalog_and_customer_pages_list_data(win):
    win.nav.setCurrentRow(2)
    assert win.catalog.weights.rowCount() > 100 and win.catalog.erp.rowCount() > 1000
    win.nav.setCurrentRow(3)
    assert {"shirai", "kodi", "tesa"} <= {win.customers.table.item(r, 0).text() for r in range(win.customers.table.rowCount())}


def test_check_text_is_wrapped_and_complete(win, tmp_path):
    load_kodi_po(win, tmp_path)
    lot = win.lot.lot
    long_name = "Ống lõi giấy phi 33.02 x 2.65 x 1750mm_51036 blue red (39817-91750-00)- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013123)" * 2
    lot.items[0]["ten_sp"] = long_name
    lot.items[0]["kg"] = 0
    win.lot.go(3)
    step = win.lot.step4
    assert step.checks.wordWrap()  # tự xuống dòng thay vì cắt chữ
    assert any("TAH-COC-013123" in t for t in step.check_lines)  # hiện đủ tên hàng dài
    assert long_name[:60] in step.checks.text()


def test_export_shows_each_file_in_done_list(win, tmp_path):
    load_kodi_po(win, tmp_path)
    win.lot.go(3)
    win.lot.step4.do_export("ALL")
    text = " ".join(win.lot.step4.done_lines)
    for label in ("Hóa đơn VAT", "Phiếu xuất kho", "Đề nghị thanh toán", "Kiểm tra chéo"):
        assert label in text

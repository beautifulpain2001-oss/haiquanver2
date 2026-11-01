"""Kiểm thử khung giao diện mới (PySide6) ở chế độ offscreen, không cần màn hình."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

import hongthien_desktop_app as core  # noqa: E402
from ui_qt import main_window as mw  # noqa: E402


@pytest.fixture
def win(store):
    app = mw.QApplication.instance() or mw.QApplication([])
    app.setStyleSheet(mw.theme.STYLE)
    w = mw.MainWindow(core, store)
    yield w
    w.close()


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
    lot.go(99)  # vượt biên thì dừng ở bước cuối
    assert lot.bar.current == 3
    lot.go(-5)
    assert lot.bar.current == 0 and not lot.back.isEnabled()


def test_pick_customer_selects_only_one_card(win):
    step = win.lot.step1
    assert set(step.cards) >= {"shirai", "kodi", "tesa"}
    step.cards["tesa"].click()
    step.cards["shirai"].click()
    assert [k for k, b in step.cards.items() if b.isChecked()] == ["shirai"]

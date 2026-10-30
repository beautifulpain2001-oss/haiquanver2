"""Kiểm thử khói giao diện Tkinter: mở app, nạp lô mẫu, xuất trọn bộ, chuyển sang Bước 2.

Cần Tkinter và màn hình. Trên Linux không màn hình dùng: xvfb-run -a python -m pytest
"""

import pytest

import hongthien_desktop_app as app

pytestmark = pytest.mark.gui


@pytest.fixture
def gui(store, monkeypatch):
    if app.tk is None:
        pytest.skip("Không có Tkinter")
    try:
        root = app.tk.Tk()
    except app.tk.TclError as e:
        pytest.skip(f"Không có màn hình: {e}")
    root.withdraw()
    shown = []
    for fn in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(app.messagebox, fn, lambda title, msg, *a, _fn=fn, **k: shown.append((_fn, title)))
    ui = app.HongThienCustomsDesktopApp(root, store)
    ui.shown = shown
    yield ui
    root.destroy()


def test_app_starts_with_kodi_sample(gui):
    assert gui.cur_customer.get() == "kodi"
    assert len(gui.cur_items) == 2
    assert len(gui.tree_items.get_children()) == 2


@pytest.mark.parametrize("customer", ["shirai", "kodi", "tesa"])
def test_export_all_and_transfer_to_step2(gui, store, customer):
    gui.cur_customer.set(customer)
    gui.load_sample_batch(customer)
    rec = gui.build_current_step1_record()

    gui.export_step1_excel("ALL")
    assert gui.shown and gui.shown[-1][0] == "showinfo"
    out_dir = store.get_record_folder_path(rec)
    files = __import__("os").listdir(out_dir)
    assert any(f.startswith("Bo_Ho_So_Xuat_Hang_") for f in files), files

    before = len(store.records)
    gui.transfer_step1_to_step2()
    assert len(store.records) == before  # cùng khách + PO thì cập nhật, không nhân bản
    saved = next(r for r in store.records if r["customer"] == customer and r["poNumber"] == rec["poNumber"])
    assert saved["files"]["vat"]["name"].startswith("Bo_Ho_So_Xuat_Hang_")

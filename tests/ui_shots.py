"""Chụp màn hình giao diện mới ở nhiều kích thước (offscreen) và dùng chung cho test bố cục.

Chạy:
    python tests/ui_shots.py --out <thư mục> [--size 1366x768] [--size 1920x1080]

Mặc định chụp cả 1366x768 và 1920x1080. Tên file: <kích thước>_<trang>.png.
Dữ liệu dùng kho tạm và PO Kodi giả, không đụng dữ liệu thật. Không chạy trong CI.
"""

import argparse
import os
import pathlib
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

DEFAULT_SIZES = ("1366x768", "1920x1080")


def pump(app, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def parse_size(text):
    w, h = text.lower().split("x")
    return int(w), int(h)


def make_window(core, store, app, size=(1366, 768)):
    """Dựng cửa sổ chính, đặt kích thước và hiện lên. Gọi bởi script và test."""
    from ui_qt import main_window as mw

    app.setStyleSheet(mw.theme.STYLE)
    win = mw.MainWindow(core, store)
    win.resize(*size)
    win.show()
    pump(app, 0.5)
    return win


def load_kodi_po(win, app, workdir):
    """Chọn khách Kodi và nạp PO giả (cần core.extract_text_from_pdf_or_image_offline đã bị thay)."""
    win.lot.step1.cards["kodi"].click()
    f = pathlib.Path(workdir) / "po.pdf"
    f.write_bytes(b"%PDF-1.4")
    win.lot.step2.load_file(str(f))
    end = time.time() + 15
    while time.time() < end and not win.lot.lot.items:
        app.processEvents()
        time.sleep(0.02)
    pump(app, 0.3)


def view_names(mw):
    """Tên các màn hình cần kiểm: 4 bước Làm chứng từ rồi các trang còn lại."""
    names = ["lam_chung_tu_b1", "lam_chung_tu_b2", "lam_chung_tu_b3", "lam_chung_tu_b4"]
    for i in range(1, len(mw.NAV)):
        names.append(f"trang_{i + 1}")
    return names


def show_view(win, app, name):
    """Chuyển cửa sổ tới màn hình `name` (xem view_names)."""
    if name.startswith("lam_chung_tu_b"):
        win.nav.setCurrentRow(0)
        win.lot.go(int(name[-1]) - 1)
    else:
        win.nav.setCurrentRow(int(name.split("_")[1]) - 1)
    pump(app, 0.3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="thư mục lưu ảnh")
    ap.add_argument("--size", action="append", help="ví dụ 1366x768 (lặp lại được)")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    import hongthien_desktop_app as core
    from test_po_parsers import KODI_PO_TEXT
    from PySide6.QtWidgets import QApplication
    from ui_qt import main_window as mw, widgets

    app = QApplication.instance() or QApplication([])
    mw.load_fonts() if hasattr(mw, "load_fonts") else None
    for fn in ("info", "warn"):
        setattr(widgets, fn, lambda *a, **k: None)
    widgets.ask = lambda *a, **k: True
    core.extract_text_from_pdf_or_image_offline = lambda *a, **k: KODI_PO_TEXT

    tmp = pathlib.Path(tempfile.mkdtemp())
    store = core.DedicatedDataStore(base_dir=str(tmp / "DATA"))
    store.config_file = str(tmp / "cfg.json")

    for size_text in args.size or DEFAULT_SIZES:
        size = parse_size(size_text)
        win = make_window(core, store, app, size)
        load_kodi_po(win, app, tmp)
        for name in view_names(mw):
            show_view(win, app, name)
            path = out / f"{size_text}_{name}.png"
            win.grab().save(str(path))
            print(path)
        win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

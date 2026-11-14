"""Kiểm tra bố cục giao diện ở 1366x768: chữ bị cắt, ô nhập đè nhau, menu phải thấy hết.

Đây là "thước đo" cho các phần sửa giao diện. Lỗi đã biết đánh dấu xfail(strict=True):
khi PR sửa xong, test sẽ báo XPASS và PR đó gỡ dấu xfail tương ứng.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

import hongthien_desktop_app as core  # noqa: E402
import ui_shots  # noqa: E402
from test_po_parsers import KODI_PO_TEXT  # noqa: E402
from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractSpinBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from ui_qt import main_window as mw, widgets  # noqa: E402

pytestmark = pytest.mark.gui

SIZE = (1366, 768)
VIEWS = ui_shots.view_names(mw)

# Lỗi đã biết ở 1366x768 -> phần việc sẽ sửa
KNOWN_CLIPPED = {"lam_chung_tu_b3": "G4: thanh nút bước ③ bị cắt chữ, sửa ở T4"}
KNOWN_OVERLAP = {"lam_chung_tu_b4": "G3: ô nhập bước ④ đè nhau, sửa ở T3"}


@pytest.fixture
def win(qapp, store, monkeypatch, tmp_path):
    for fn in ("info", "warn"):
        monkeypatch.setattr(widgets, fn, lambda *a, **k: None)
    monkeypatch.setattr(widgets, "ask", lambda *a, **k: True)
    monkeypatch.setattr(core, "extract_text_from_pdf_or_image_offline", lambda *a, **k: KODI_PO_TEXT)
    w = ui_shots.make_window(core, store, qapp, SIZE)
    ui_shots.load_kodi_po(w, qapp, tmp_path)
    w.app = qapp
    yield w
    w.close()


def _params(known):
    return [pytest.param(n, marks=pytest.mark.xfail(strict=True, reason=known[n])) if n in known else n for n in VIEWS]


def _rect(widget, root):
    return QRect(widget.mapTo(root, widget.rect().topLeft()), widget.size())


def _visible(widgets_):
    return [w for w in widgets_ if w.isVisible() and w.width() > 0 and w.height() > 0]


def clipped_texts(win):
    """Nút/nhãn đang hiện có chữ rộng hơn vùng chứa (không tính nhãn tự xuống dòng)."""
    bad = []
    for w in _visible(win.findChildren(QPushButton) + win.findChildren(QLabel)):
        if isinstance(w, QLabel):
            if w.wordWrap() or not w.text() or w.textFormat() == w.textFormat().RichText or "<" in w.text():
                continue
        text = w.text().replace("&", "")
        if not text:
            continue
        need = max(w.fontMetrics().horizontalAdvance(line) for line in text.split("\n"))
        if isinstance(w, QPushButton):
            # nút còn phải chừa chỗ cho biểu tượng nếu có
            if not w.icon().isNull():
                need += w.iconSize().width() + 4
        if need > w.contentsRect().width():
            bad.append(f"{w.metaObject().className()} '{text}' cần {need}px, có {w.contentsRect().width()}px")
    return bad


def _groups(win):
    """Các vùng có ô nhập xếp theo biểu mẫu: QGroupBox và widget dùng QFormLayout."""
    seen = []
    for g in win.findChildren(QGroupBox) + [w for w in win.findChildren(QWidget) if isinstance(w.layout(), QFormLayout)]:
        if g not in seen and g.isVisible():
            seen.append(g)
    return seen


def _own_edits(group):
    out = []
    for e in group.findChildren(QLineEdit):
        if isinstance(e.parent(), (QAbstractSpinBox, QComboBox)):
            continue  # ô nhập nội bộ của spinbox/combobox
        out.append(e)
    return _visible(out)


def overlaps(win):
    """Cặp ô nhập đè nhau, hoặc ô nhập đè nhãn của dòng khác, trong cùng nhóm."""
    bad = []
    for g in _groups(win):
        edits = _own_edits(g)
        labels = _visible(g.findChildren(QLabel))
        own_label = {}
        lay = g.layout()
        if isinstance(lay, QFormLayout):
            for e in edits:
                lb = lay.labelForField(e)
                if lb is not None:
                    own_label[e] = lb
        title = g.title() if isinstance(g, QGroupBox) else g.objectName()
        for i, a in enumerate(edits):
            ra = _rect(a, win)
            for b in edits[i + 1:]:
                if ra.intersects(_rect(b, win)):
                    bad.append(f"[{title}] ô '{a.text() or a.placeholderText()}' đè ô '{b.text() or b.placeholderText()}'")
            for lb in labels:
                if lb is own_label.get(a) or not lb.text():
                    continue
                if ra.intersects(_rect(lb, win)):
                    bad.append(f"[{title}] ô '{a.text() or a.placeholderText()}' đè nhãn '{lb.text()}'")
    return bad


@pytest.mark.parametrize("name", _params(KNOWN_CLIPPED))
def test_no_clipped_text(win, name):
    ui_shots.show_view(win, win.app, name)
    assert not clipped_texts(win), f"{name}: chữ bị cắt:\n" + "\n".join(clipped_texts(win))


@pytest.mark.parametrize("name", _params(KNOWN_OVERLAP))
def test_no_overlapping_fields(win, name):
    ui_shots.show_view(win, win.app, name)
    assert not overlaps(win), f"{name}: ô đè nhau:\n" + "\n".join(overlaps(win))


@pytest.mark.xfail(strict=True, reason="G2: menu 8 mục không vừa 768px, mục cuối bị cắt; sửa ở T2")
def test_nav_last_item_fully_visible(win):
    nav = win.nav
    last = nav.item(nav.count() - 1)
    nav.scrollToItem(nav.item(0))
    ui_shots.pump(win.app, 0.2)
    view = nav.viewport().rect()
    assert view.contains(nav.visualItemRect(last)), "mục menu cuối nằm ngoài vùng nhìn thấy"
    assert not nav.verticalScrollBar().isVisible(), "menu phải không cần thanh cuộn"


def test_checker_detects_overlap_and_clipping(qapp):
    """Máy dò phải bắt được lỗi giả dựng sẵn, nếu không các test trên vô nghĩa."""
    root = QWidget()
    root.resize(300, 200)
    box = QGroupBox("Thử", root)
    box.setGeometry(0, 0, 300, 100)
    e1, e2 = QLineEdit(box), QLineEdit(box)
    e1.setGeometry(10, 20, 100, 30)
    e2.setGeometry(50, 30, 100, 30)
    btn = QPushButton("Một dòng chữ rất rất dài không thể vừa", root)
    btn.setGeometry(0, 120, 60, 30)
    root.show()
    qapp.processEvents()
    assert overlaps(root) and clipped_texts(root)

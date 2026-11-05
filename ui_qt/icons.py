"""Bộ biểu tượng nét đơn sắc vẽ bằng QPainter (không dùng emoji, không cần QtSvg vì bản .exe đã bỏ QtSvg).

Mỗi nút bấm có chữ bắt đầu bằng emoji cũ được đổi sang biểu tượng cùng bộ nét: đồng nhất trên mọi máy, đổi màu theo vai trò nút
(chữ trắng trên nút chính, xanh navy trên nút phụ, đỏ trên nút xóa) và mờ khi nút bị khóa.
Cài một lần ở `install(app)`: bộ lọc sự kiện đổi từng nút ngay lần hiện đầu tiên, kể cả nút trong hộp thoại mở sau.
"""

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QPushButton

SIZE = 18  # kích thước hiển thị (px logic)


def _p(*cmds):
    """Đường vẽ từ lệnh đơn giản trong khung 24x24: ('M', x, y) / ('L', x, y) / ('C', x1, y1, x2, y2, x, y) / ('A', x, y, w, h, start, span) / ('Z',)."""
    path = QPainterPath()
    for c in cmds:
        k = c[0]
        if k == "M":
            path.moveTo(c[1], c[2])
        elif k == "L":
            path.lineTo(c[1], c[2])
        elif k == "C":
            path.cubicTo(*c[1:7])
        elif k == "A":
            path.arcMoveTo(QRectF(c[1], c[2], c[3], c[4]), c[5])
            path.arcTo(QRectF(c[1], c[2], c[3], c[4]), c[5], c[6])
        elif k == "R":
            path.addRoundedRect(QRectF(c[1], c[2], c[3], c[4]), c[5], c[5])
        elif k == "E":
            path.addEllipse(QRectF(c[1], c[2], c[3], c[4]))
        elif k == "Z":
            path.closeSubpath()
    return path


SHAPES = {
    "plus": [("M", 12, 5), ("L", 12, 19), ("M", 5, 12), ("L", 19, 12)],
    "search": [("E", 4, 4, 12, 12), ("M", 14, 14), ("L", 20, 20)],
    "edit": [("M", 4, 20), ("L", 5, 15), ("L", 16, 4), ("L", 20, 8), ("L", 9, 19), ("Z",), ("M", 14, 6), ("L", 18, 10)],
    "trash": [("M", 4, 7), ("L", 20, 7), ("M", 9, 7), ("L", 9, 4), ("L", 15, 4), ("L", 15, 7), ("M", 6, 7), ("L", 7, 20), ("L", 17, 20), ("L", 18, 7),
              ("M", 10, 11), ("L", 10, 16), ("M", 14, 11), ("L", 14, 16)],
    "refresh": [("A", 4, 4, 16, 16, 30, 270), ("M", 20, 4), ("L", 20, 9), ("L", 15, 9)],
    "folder": [("M", 3, 7), ("L", 3, 19), ("L", 21, 19), ("L", 21, 9), ("L", 11, 9), ("L", 9, 6), ("L", 4, 6), ("Z",)],
    "folder-open": [("M", 3, 19), ("L", 3, 6), ("L", 9, 6), ("L", 11, 8), ("L", 19, 8), ("L", 19, 11), ("M", 3, 19), ("L", 6, 11), ("L", 22, 11), ("L", 19, 19), ("Z",)],
    "download": [("M", 12, 4), ("L", 12, 15), ("M", 7, 11), ("L", 12, 16), ("L", 17, 11), ("M", 4, 20), ("L", 20, 20)],
    "upload": [("M", 12, 16), ("L", 12, 5), ("M", 7, 9), ("L", 12, 4), ("L", 17, 9), ("M", 4, 20), ("L", 20, 20)],
    "save": [("M", 5, 4), ("L", 17, 4), ("L", 20, 7), ("L", 20, 20), ("L", 5, 20), ("Z",), ("M", 8, 4), ("L", 8, 9), ("L", 15, 9), ("L", 15, 4), ("M", 8, 20), ("L", 8, 14), ("L", 16, 14), ("L", 16, 20)],
    "next": [("M", 5, 5), ("L", 14, 12), ("L", 5, 19), ("Z",), ("M", 18, 5), ("L", 18, 19)],
    "undo": [("M", 9, 6), ("L", 4, 11), ("L", 9, 16), ("M", 4, 11), ("L", 14, 11), ("C", 18, 11, 20, 13, 20, 16.5), ("C", 20, 19, 19, 19.5, 18, 20)],
    "file": [("M", 6, 3), ("L", 14, 3), ("L", 19, 8), ("L", 19, 21), ("L", 6, 21), ("Z",), ("M", 14, 3), ("L", 14, 8), ("L", 19, 8)],
    "file-text": [("M", 6, 3), ("L", 14, 3), ("L", 19, 8), ("L", 19, 21), ("L", 6, 21), ("Z",), ("M", 9, 12), ("L", 16, 12), ("M", 9, 16), ("L", 16, 16)],
    "table": [("R", 3, 5, 18, 14, 2), ("M", 3, 10), ("L", 21, 10), ("M", 3, 15), ("L", 21, 15), ("M", 9, 5), ("L", 9, 19)],
    "link": [("A", 3, 9, 10, 6, 90, 180), ("A", 11, 9, 10, 6, 270, 180), ("M", 9, 12), ("L", 15, 12)],
    "box": [("M", 12, 3), ("L", 20, 7.5), ("L", 20, 16.5), ("L", 12, 21), ("L", 4, 16.5), ("L", 4, 7.5), ("Z",), ("M", 4, 7.5), ("L", 12, 12), ("L", 20, 7.5), ("M", 12, 12), ("L", 12, 21)],
    "left": [("M", 20, 12), ("L", 4, 12), ("M", 10, 6), ("L", 4, 12), ("L", 10, 18)],
    "right": [("M", 4, 12), ("L", 20, 12), ("M", 14, 6), ("L", 20, 12), ("L", 14, 18)],
    "chev-left": [("M", 15, 5), ("L", 8, 12), ("L", 15, 19)],
    "chev-right": [("M", 9, 5), ("L", 16, 12), ("L", 9, 19)],
    "check": [("M", 5, 12.5), ("L", 10, 17), ("L", 19, 7)],
    "doc-edit": [("M", 6, 3), ("L", 14, 3), ("L", 19, 8), ("L", 19, 21), ("L", 6, 21), ("Z",), ("M", 9, 15), ("L", 16, 8)],
    "users": [("E", 8, 5, 6, 6), ("M", 3, 20), ("C", 3, 14, 6, 13, 11, 13), ("C", 16, 13, 19, 14, 19, 20), ("E", 15, 6, 4, 4)],
    "settings": [("E", 8, 8, 8, 8), ("M", 12, 2), ("L", 12, 5), ("M", 12, 19), ("L", 12, 22), ("M", 2, 12), ("L", 5, 12), ("M", 19, 12), ("L", 22, 12)],
    "grid": [("R", 4, 4, 7, 7, 1.5), ("R", 13, 4, 7, 7, 1.5), ("R", 4, 13, 7, 7, 1.5), ("R", 13, 13, 7, 7, 1.5)],
    "clock": [("E", 3, 3, 18, 18), ("M", 12, 7), ("L", 12, 12), ("L", 16, 14)],
    "database": [("E", 5, 3, 14, 5), ("M", 5, 5.5), ("L", 5, 18.5), ("C", 5, 21, 19, 21, 19, 18.5), ("L", 19, 5.5), ("M", 5, 12), ("C", 5, 14.5, 19, 14.5, 19, 12)],
}

# emoji đầu chữ nút (cách cũ) -> tên biểu tượng
EMOJI = {
    "➕": "plus", "🆕": "plus", "✏": "edit", "🗑": "trash", "🔄": "refresh", "📂": "folder-open", "📁": "folder", "🗂️": "folder", "🗂": "folder",
    "📥": "download", "📤": "upload", "💾": "save", "🔎": "search", "🔍": "search", "⏭": "next", "↩": "undo", "📄": "file", "🧾": "file-text",
    "📊": "table", "🔗": "link", "📦": "box", "←": "left", "→": "right", "◀": "chev-left", "▶": "chev-right", "📝": "doc-edit", "📑": "file-text",
    "📚": "database", "📎": "link", "🗃": "database", "👥": "users", "⚙": "settings", "⚙️": "settings",
}

_cache = {}


def make_icon(name, color="#FFFFFF", disabled="#A0AEC0", size=SIZE):
    key = (name, color, disabled, size)
    if key in _cache:
        return _cache[key]
    icon = QIcon()
    for mode, col in ((QIcon.Normal, color), (QIcon.Disabled, disabled)):
        scale = 2
        pm = QPixmap(size * scale, size * scale)
        pm.fill(Qt.transparent)
        pm.setDevicePixelRatio(scale)
        qp = QPainter(pm)
        qp.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(col), 1.9)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        qp.setPen(pen)
        qp.setBrush(Qt.NoBrush)
        qp.scale(size / 24.0, size / 24.0)
        qp.drawPath(_p(*SHAPES[name]))
        qp.end()
        icon.addPixmap(pm, mode)
    _cache[key] = icon
    return icon


ROLE_COLOR = {"": "#FFFFFF", "sec": "#0B4FA8", "dng": "#A21B1B", "ghost": "#0B4FA8", "big": "#FFFFFF", "chip": "#0B4FA8"}


def split_emoji(text):
    """('📁  Mở thư mục', ...) -> ('folder', 'Mở thư mục'); không có emoji nhận ra thì (None, text)."""
    for emo in sorted(EMOJI, key=len, reverse=True):
        if text.startswith(emo):
            return EMOJI[emo], text[len(emo):].lstrip(" ️")
    return None, text


def style_button(btn):
    """Đổi emoji đầu chữ thành biểu tượng nét, đặt con trỏ tay. Gọi lại nhiều lần vẫn an toàn."""
    if btn.property("_iconized"):
        return
    btn.setProperty("_iconized", True)
    btn.setCursor(Qt.PointingHandCursor)
    name, rest = split_emoji(btn.text())
    if not name and btn.text().rstrip().endswith("→"):  # "Tiếp tục →": mũi tên đặt bên phải chữ
        btn.setText(btn.text().rstrip()[:-1].rstrip() + "  ")
        btn.setIcon(make_icon("right", ROLE_COLOR.get(btn.objectName(), "#FFFFFF")))
        btn.setLayoutDirection(Qt.RightToLeft)
        return
    if name:
        btn.setText(" " + rest)  # chừa khoảng thở giữa biểu tượng và chữ
        role = btn.objectName()
        btn.setIcon(make_icon(name, ROLE_COLOR.get(role, "#FFFFFF" if not role else "#0B4FA8")))
        btn.setIconSize(btn.iconSize().__class__(SIZE, SIZE))


class _Filter(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and isinstance(obj, QPushButton):
            style_button(obj)
        return False


_filter = None


def install(app):
    global _filter
    _filter = _Filter(app)
    app.installEventFilter(_filter)

"""Khung xem file PO (PDF/ảnh) đặt cạnh bảng dòng hàng để so số liệu mà không phải mở file khác.

PDF dựng bằng pypdfium2 (đã có sẵn trong phần mềm), ảnh mở bằng Pillow. PO Excel không xem được ở đây: hiện hướng dẫn mở bằng Excel.
"""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def _polys(box):
    """`box` là một khung 4 điểm hoặc danh sách nhiều khung (dòng đã gộp)."""
    if not box:
        return []
    polys = box if isinstance(box[0][0], (list, tuple)) else [box]
    return [b for b in polys if b and len(b) == 4]


class PoStack(QSplitter):
    """Khung xem PO chia 1–3 ô xếp dọc: mỗi ô một trang PO (dòng gộp từ nhiều PO thì mỗi PO một ô, tô sáng các dòng của mã đó)."""

    closed = Signal()

    def __init__(self, core):
        super().__init__(Qt.Vertical)
        self.setChildrenCollapsible(False)
        self.panes = [PoViewer(core) for _ in range(3)]
        for p in self.panes:
            self.addWidget(p)
            p.closed.connect(self.closed)
        self.specs = []
        for p in self.panes[1:]:
            p.hide()

    file = property(lambda self: self.panes[0].file)
    page = property(lambda self: self.panes[0].page)
    box = property(lambda self: self.panes[0].box)
    pages = property(lambda self: self.panes[0].pages)
    title = property(lambda self: self.panes[0].title)

    def can_view(self, path):
        return self.panes[0].can_view(path)

    def show_page(self, path, page=0, box=None):
        self.show_many([(path, page, box)])

    def show_many(self, specs):
        self.specs = specs = list(specs)[:3] or [("", 0, None)]
        for i, p in enumerate(self.panes):
            if i < len(specs):
                p.show()
                p.show_page(*specs[i])
            else:
                p.hide()


class PoViewer(QWidget):
    """Xem từng trang PO. `show_page(file, page)` nhảy tới đúng trang của dòng đang chọn."""

    closed = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.file, self.page, self.pages, self.zoom, self.box = "", 0, 0, 1.0, None
        self.cache = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        bar = QHBoxLayout()
        self.title = QLabel("Xem PO")
        self.title.setObjectName("h2")
        bar.addWidget(self.title, 1)
        self.prev = QPushButton("◀")
        self.prev.setObjectName("sec")
        self.prev.setToolTip("Trang trước")
        self.prev.setAccessibleName("Trang PO trước")
        self.next = QPushButton("▶")
        self.next.setObjectName("sec")
        self.next.setToolTip("Trang sau")
        self.next.setAccessibleName("Trang PO sau")
        self.zoom_out = QPushButton("−")
        self.zoom_out.setObjectName("sec")
        self.zoom_out.setToolTip("Thu nhỏ")
        self.zoom_out.setAccessibleName("Thu nhỏ PO")
        self.zoom_in = QPushButton("+")
        self.zoom_in.setObjectName("sec")
        self.zoom_in.setToolTip("Phóng to")
        self.zoom_in.setAccessibleName("Phóng to PO")
        for b in (self.prev, self.next, self.zoom_out, self.zoom_in):
            b.setFixedWidth(40)
            bar.addWidget(b)
        close = QPushButton("Ẩn")
        close.setObjectName("ghost")
        close.clicked.connect(self.closed)
        bar.addWidget(close)
        lay.addLayout(bar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        lay.addWidget(self.scroll, 1)
        self.prev.clicked.connect(lambda: self.show_page(self.file, self.page - 1))
        self.next.clicked.connect(lambda: self.show_page(self.file, self.page + 1))
        self.zoom_in.clicked.connect(lambda: self.set_zoom(self.zoom * 1.25))
        self.zoom_out.clicked.connect(lambda: self.set_zoom(self.zoom / 1.25))

    # ---- nội dung --------------------------------------------------------------
    def can_view(self, path):
        ext = os.path.splitext(path or "")[1].lower()
        return os.path.isfile(path or "") and (ext == ".pdf" or ext in IMAGE_EXT)

    def _render(self, path, page):
        width = max(300, self.scroll.viewport().width() - 24)  # vừa bề ngang khung xem, rồi nhân với mức phóng
        key = (path, page, round(self.zoom, 2), width // 40)
        if key in self.cache:
            return self.cache[key]
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            doc = self.core.pdfium.PdfDocument(path)
            self.pages = len(doc)
            pg = doc[max(0, min(page, self.pages - 1))]
            scale = max(0.6, min(4.0, width * self.zoom / max(1.0, pg.get_width())))
            pil = pg.render(scale=scale).to_pil().convert("RGBA")
        else:
            from PIL import Image
            self.pages = 1
            pil = Image.open(path).convert("RGBA")
            w = int(width * self.zoom)
            pil = pil.resize((w, int(pil.height * w / pil.width)))
        img = QImage(pil.tobytes("raw", "RGBA"), pil.width, pil.height, pil.width * 4, QImage.Format_RGBA8888).copy()
        pm = QPixmap.fromImage(img)
        if len(self.cache) > 6:
            self.cache.clear()
        self.cache[key] = pm
        return pm

    def _highlighted(self, pm, box):
        """Bản sao trang có tô sáng dòng đang chọn: nền vàng trong, viền cam, mũi tên bên trái để thấy ngay cả khi PO nhiều dòng sát nhau."""
        polys = _polys(box)
        if not polys:
            return pm
        out = QPixmap(pm)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing, True)
        W, H = pm.width(), pm.height()
        for box in polys:
            self._draw_box(p, box, W, H)
        p.end()
        return out

    @staticmethod
    def _draw_box(p, box, W, H):
        poly = QPolygonF([QPointF(x * W, y * H) for x, y in box])
        p.setPen(QPen(QColor("#EA580C"), 2.5))
        p.setBrush(QColor(255, 214, 0, 80))
        p.drawPolygon(poly)
        mid_y = sum(y for _x, y in box) / 4 * H
        left = min(x for x, _y in box) * W
        arrow = QPolygonF([QPointF(left - 22, mid_y - 9), QPointF(left - 4, mid_y), QPointF(left - 22, mid_y + 9)])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EA580C"))
        p.drawPolygon(arrow)

    def show_page(self, path, page=0, box=None):
        if not self.can_view(path):
            self.file, self.pages = "", 0
            self.label.setText("PO này là file Excel hoặc chưa còn trên máy: mở bằng Excel để so.\n(Chỉ xem được PO dạng PDF hoặc ảnh.)")
            self.label.adjustSize()
            self.title.setText("Xem PO")
            self._buttons()
            return
        try:
            pm = self._render(path, max(0, page))
        except Exception as e:  # noqa: BLE001 - file hỏng: báo ngay trong khung xem, không làm hỏng bước kiểm tra
            self.label.setText(f"Không mở được PO để xem: {e}")
            self.label.adjustSize()
            return
        self.file, self.page, self.box = path, max(0, min(page, self.pages - 1)), box
        pm = self._highlighted(self._render(path, self.page), box)
        self.label.setPixmap(pm)
        self.label.resize(pm.size())
        polys = _polys(box)
        if polys:  # cuộn để dòng đầu tiên đang chọn nằm giữa khung xem
            cy = int(sum(y for _x, y in polys[0]) / 4 * pm.height())
            bar = self.scroll.verticalScrollBar()
            bar.setValue(max(0, cy - self.scroll.viewport().height() // 2))
        self.title.setText(f"Xem PO — {os.path.basename(path)} · trang {self.page + 1}/{self.pages}")
        self._buttons()

    def set_zoom(self, z):
        self.zoom = max(0.4, min(3.0, z))
        if self.file:
            self.show_page(self.file, self.page, self.box)

    def _buttons(self):
        self.prev.setEnabled(bool(self.file) and self.page > 0)
        self.next.setEnabled(bool(self.file) and self.page < self.pages - 1)
        self.zoom_in.setEnabled(bool(self.file))
        self.zoom_out.setEnabled(bool(self.file))

"""Khung xem file PO (PDF/ảnh) đặt cạnh bảng dòng hàng để so số liệu mà không phải mở file khác.

PDF dựng bằng pypdfium2 (đã có sẵn trong phần mềm), ảnh mở bằng Pillow. PO Excel không xem được ở đây: hiện hướng dẫn mở bằng Excel.
"""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


class PoViewer(QWidget):
    """Xem từng trang PO. `show_page(file, page)` nhảy tới đúng trang của dòng đang chọn."""

    closed = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.file, self.page, self.pages, self.zoom = "", 0, 0, 1.0
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

    def show_page(self, path, page=0):
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
        self.file, self.page = path, max(0, min(page, self.pages - 1))
        pm = self._render(path, self.page)
        self.label.setPixmap(pm)
        self.label.resize(pm.size())
        self.title.setText(f"Xem PO — {os.path.basename(path)} · trang {self.page + 1}/{self.pages}")
        self._buttons()

    def set_zoom(self, z):
        self.zoom = max(0.4, min(3.0, z))
        if self.file:
            self.show_page(self.file, self.page)

    def _buttons(self):
        self.prev.setEnabled(bool(self.file) and self.page > 0)
        self.next.setEnabled(bool(self.file) and self.page < self.pages - 1)
        self.zoom_in.setEnabled(bool(self.file))
        self.zoom_out.setEnabled(bool(self.file))

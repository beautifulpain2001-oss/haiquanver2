"""Khung giao diện mới: thanh điều hướng bên trái + thanh 4 bước ở trang "Làm chứng từ".

PR B chỉ dựng khung và kiểm tra đóng gói; nội dung từng trang làm ở các PR sau.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from . import theme

STEPS = ["① Chọn khách & nạp PO", "② Kiểm tra dòng hàng", "③ Thông tin chuyến hàng", "④ Xuất & lưu hồ sơ"]
NAV = ["Làm chứng từ", "Hồ sơ đã lưu", "Danh mục", "Khách hàng", "Cài đặt"]


def _page(title, hint):
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 24, 28, 24)
    t = QLabel(title)
    t.setObjectName("title")
    h = QLabel(hint)
    h.setObjectName("hint")
    h.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(h)
    lay.addStretch(1)
    return w


class StepBar(QWidget):
    """Thanh tiến trình 4 bước; bước đã qua màu xanh, bước hiện tại tô đậm."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.labels = [QLabel(s) for s in STEPS]
        for lb in self.labels:
            lay.addWidget(lb)
        lay.addStretch(1)
        self.set_current(0)

    def set_current(self, idx):
        self.current = idx
        for i, lb in enumerate(self.labels):
            lb.setProperty("step", "done" if i < idx else "current" if i == idx else "todo")
            lb.style().unpolish(lb)
            lb.style().polish(lb)


class LotPage(QWidget):
    """Trang "Làm chứng từ": thanh 4 bước + vùng nội dung từng bước + nút Quay lại / Tiếp tục."""

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        self.bar = StepBar()
        lay.addWidget(self.bar)
        self.stack = QStackedWidget()
        card = QFrame()
        card.setObjectName("card")
        QVBoxLayout(card).addWidget(self.stack)
        lay.addWidget(card, 1)
        for s in STEPS:
            self.stack.addWidget(_page(s[2:], "Đang xây dựng. Hiện dùng giao diện cũ để làm chứng từ."))
        nav = QHBoxLayout()
        self.back = QPushButton("← Quay lại")
        self.next = QPushButton("Tiếp tục →")
        self.back.clicked.connect(lambda: self.go(self.bar.current - 1))
        self.next.clicked.connect(lambda: self.go(self.bar.current + 1))
        nav.addWidget(self.back)
        nav.addStretch(1)
        nav.addWidget(self.next)
        lay.addLayout(nav)
        self.go(0)

    def go(self, idx):
        idx = max(0, min(len(STEPS) - 1, idx))
        self.bar.set_current(idx)
        self.stack.setCurrentIndex(idx)
        self.back.setEnabled(idx > 0)
        self.next.setEnabled(idx < len(STEPS) - 1)


class MainWindow(QMainWindow):
    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        self.setWindowTitle("Hồ sơ hải quan Hồng Thiên")
        self.resize(1180, 740)
        self.setMinimumSize(900, 600)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(210)
        self.nav.addItems(NAV)
        self.pages = QStackedWidget()
        self.lot = LotPage()
        self.pages.addWidget(self.lot)
        self.pages.addWidget(_page("Hồ sơ đã lưu", "Tra cứu, mở lại và xuất sổ tổng hợp các hồ sơ đã làm."))
        self.pages.addWidget(_page("Danh mục", "Thư viện cân nặng, danh mục ERP và danh mục hàng theo khách."))
        self.pages.addWidget(_page("Khách hàng", "Danh sách khách và thêm khách mới từ chứng từ mẫu."))
        self.pages.addWidget(_page("Cài đặt", f"Thư mục dữ liệu hiện tại: {store.base_dir}"))
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav)
        lay.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)


def run(core, store, smoke=False):
    """Mở giao diện mới. `smoke`: tự đóng sau 3 giây (kiểm tra bản đóng gói)."""
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.STYLE)
    win = MainWindow(core, store)
    win.show()
    if smoke:
        QTimer.singleShot(3000, app.quit)
    return app.exec()

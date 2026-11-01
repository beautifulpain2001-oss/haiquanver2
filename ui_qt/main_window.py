"""Khung giao diện mới: thanh điều hướng bên trái + thanh 4 bước ở trang "Làm chứng từ".

PR B chỉ dựng khung và kiểm tra đóng gói; nội dung từng trang làm ở các PR sau.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from . import theme

STEPS = ["① Chọn khách & nạp PO", "② Kiểm tra dòng hàng", "③ Thông tin chuyến hàng", "④ Xuất & lưu hồ sơ"]
NAV = ["📝  Làm chứng từ", "🗂  Hồ sơ đã lưu", "📚  Danh mục", "👥  Khách hàng", "⚙  Cài đặt"]


def _page(title, hint, inner=False):
    """Trang tạm: tiêu đề + dòng giải thích, canh giữa. `inner`: nằm trong khung trắng (nền trong suốt)."""
    w = QWidget()
    w.setObjectName("inner" if inner else "page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.addStretch(1)
    for text, name in (("🛠", None), (title, "title"), (hint, "hint")):
        lb = QLabel(text)
        lb.setAlignment(Qt.AlignCenter)
        lb.setWordWrap(True)
        if name:
            lb.setObjectName(name)
        else:
            lb.setStyleSheet("font-size: 28pt;")
        lay.addWidget(lb)
    lay.addStretch(2)
    return w


class CustomerStep(QWidget):
    """Bước ①: chọn khách bằng thẻ lớn + chọn file PO. (Đọc PO sẽ nối ở PR sau.)"""

    def __init__(self, core, on_change):
        super().__init__()
        self.setObjectName("inner")
        self.on_change = on_change
        self.customer = None
        self.po_path = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        h = QLabel("Khách hàng nào?")
        h.setObjectName("h2")
        lay.addWidget(h)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = {}
        for i, (key, prof) in enumerate(core.PROFILES.items()):
            b = QPushButton(f"{prof.get('label') or key}")
            b.setObjectName("cust")
            b.setCheckable(True)
            b.setMinimumHeight(64)
            b.clicked.connect(lambda _=False, k=key: self.pick(k))
            self.cards[key] = b
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)
        h2 = QLabel("File PO của khách")
        h2.setObjectName("h2")
        lay.addWidget(h2)
        self.drop = QPushButton("📂  Bấm để chọn file PO (PDF, Excel, ảnh)")
        self.drop.setObjectName("drop")
        self.drop.clicked.connect(self.choose_file)
        lay.addWidget(self.drop)
        self.note = QLabel("Phần tự đọc PO sẽ có ở bản sau. Hiện bản này chỉ để xem trước giao diện.")
        self.note.setObjectName("hint")
        lay.addWidget(self.note)
        lay.addStretch(1)

    def pick(self, key):
        self.customer = key
        for k, b in self.cards.items():
            b.setChecked(k == key)
        self.on_change()

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file PO", "", "File PO (*.pdf *.xlsx *.xls *.png *.jpg *.jpeg *.txt)")
        if path:
            self.po_path = path
            self.drop.setText("✅  " + path.replace("\\", "/").split("/")[-1])
            self.on_change()


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

    def __init__(self, core):
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
        self.step1 = CustomerStep(core, self.refresh_buttons)
        self.stack.addWidget(self.step1)
        for s in STEPS[1:]:
            self.stack.addWidget(_page(s[2:], "Đang xây dựng. Hiện dùng giao diện cũ để làm chứng từ.", inner=True))
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
        self.refresh_buttons()

    def refresh_buttons(self):
        idx = self.bar.current
        self.back.setEnabled(idx > 0)
        # Bước ① phải chọn khách rồi mới đi tiếp
        self.next.setEnabled(idx < len(STEPS) - 1 and (idx > 0 or self.step1.customer is not None))


class MainWindow(QMainWindow):
    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        self.setWindowTitle("Hồ sơ hải quan Hồng Thiên")
        self.resize(1180, 740)
        self.setMinimumSize(900, 600)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.addItems(NAV)
        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(230)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        brand = QLabel("HỒNG THIÊN")
        brand.setObjectName("brand")
        sub = QLabel("Hồ sơ hải quan")
        sub.setObjectName("brandsub")
        sl.addWidget(brand)
        sl.addWidget(sub)
        sl.addWidget(self.nav, 1)
        self.pages = QStackedWidget()
        self.lot = LotPage(core)
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
        lay.addWidget(side)
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

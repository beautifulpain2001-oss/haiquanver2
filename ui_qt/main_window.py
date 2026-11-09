"""Cửa sổ chính của giao diện mới: thanh điều hướng bên trái + các trang."""

import datetime
import os
import sys
import traceback

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from . import icons, theme, widgets
from .frame import BANNERS, Banner
from .pages_lot import STEPS, LotPage  # noqa: F401 - STEPS giữ ở đây cho code/test cũ
from .pages_kho import MauPage
from .pages_other import CatalogPage, CustomersPage, DataTongPage, DeclarationsPage, RecordsPage, SettingsPage

NAV = ["📝  Làm chứng từ", "📑  Tờ khai đang có", "🗂  Hồ sơ đã lưu", "📚  Danh mục", "👥  Khách hàng", "🗃  Data tổng", "📎  Kho mẫu", "⚙  Cài đặt"]


class MainWindow(QMainWindow):
    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        self.setWindowTitle("Hồ sơ hải quan Hồng Thiên")
        self.resize(1280, 780)
        self.setMinimumSize(980, 640)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for text in NAV:  # biểu tượng nét trắng thay emoji; chữ giữ nguyên
            name, rest = icons.split_emoji(text)
            it = QListWidgetItem(rest)
            if name:
                it.setIcon(icons.make_icon(name, "#36506F", "#94A3B8", 24))
            self.nav.addItem(it)
        self.nav.setIconSize(QSize(24, 24))
        self.nav.setViewMode(QListView.IconMode)  # biểu tượng ở trên, tên mục ở dưới
        self.nav.setFlow(QListView.TopToBottom)
        self.nav.setWrapping(False)
        self.nav.setMovement(QListView.Static)
        self.nav.setUniformItemSizes(True)
        self.nav.setTextElideMode(Qt.ElideNone)
        self.nav.setWordWrap(True)
        self.nav.setGridSize(QSize(98, 92))
        for i in range(self.nav.count()):
            it = self.nav.item(i)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            words = it.text().split(" ", 1)
            it.setText("\n".join(words))  # tên mục xuống dòng ở chữ đầu để vừa 104px
        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(104)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        logo = QLabel("H")  # logo ô vuông; tên công ty nằm ở thanh trên cùng
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background:#1570D8;color:white;font-size:22px;font-weight:700;border-radius:14px")
        sl.addSpacing(14)
        sl.addWidget(logo, 0, Qt.AlignHCenter)
        sl.addSpacing(10)
        sl.addWidget(self.nav, 1)

        self.lot = LotPage(core, store)
        self.declarations = DeclarationsPage(core, store)
        self.records = RecordsPage(core, store)
        self.catalog = CatalogPage(core, store)
        self.customers = CustomersPage(core, store)
        self.data_tong = DataTongPage(core, store)
        self.kho = MauPage(core, store)
        self.settings = SettingsPage(core, store)
        self.pages = QStackedWidget()
        for p in (self.lot, self.declarations, self.records, self.catalog, self.customers, self.data_tong, self.kho, self.settings):
            self.pages.addWidget(p)
        self.nav.currentRowChanged.connect(self.show_page)
        self.lot.saved.connect(self.records.refresh)
        self.lot.saved.connect(self.declarations.refresh)
        self.records.open_record.connect(self.open_record)
        self.settings.data_changed.connect(self.lot.start_new)
        self.customers.changed.connect(self.lot.step1.refresh)
        self.customers.make_lot.connect(self.make_lot_for)
        # Kiểm tra OCR chạy chương trình Tesseract (chậm): làm sẵn ở nền ngay khi mở để trang Cài đặt hiện tức thì
        widgets.run_job(self, core.ocr_available, lambda _ok: None)

        # Nhiều máy dùng chung một thư mục dữ liệu: máy khác vừa lưu thì tự đọc lại và làm mới trang đang xem
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_shared)
        self.sync_timer.start(15000)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        top = QWidget()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(36, 14, 36, 4)
        brand = QLabel("HỒNG THIÊN  ·  Hồ sơ hải quan")
        brand.setObjectName("brand")
        tl.addWidget(brand)
        tl.addStretch(1)
        rv.addWidget(top)
        bw = QWidget()
        bl = QVBoxLayout(bw)
        bl.setContentsMargins(36, 6, 36, 8)
        self.banner = Banner()
        bl.addWidget(self.banner)
        rv.addWidget(bw)
        rv.addWidget(self.pages, 1)
        for p in (self.lot, self.declarations, self.records, self.catalog, self.customers, self.data_tong, self.kho, self.settings):
            lab = p.findChild(QLabel, "title")  # tiêu đề riêng của trang đã có trong banner
            if lab is not None:
                lab.hide()
        lay.addWidget(right, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)
        self._folder_sig = None
        self.folder_timer = QTimer(self)  # Danh mục / Tờ khai đang làm theo thư mục THẬT: xóa hay thêm thư mục ngoài Explorer thì danh sách tự đổi
        self.folder_timer.timeout.connect(self.watch_folders)
        self.folder_timer.start(3000)

    def watch_folders(self):
        page = self.pages.currentWidget()
        if page not in (self.declarations, self.catalog) or not hasattr(page, "refresh"):
            self._folder_sig = None
            return
        try:
            sig = self.store.folders_signature()
        except Exception:
            return
        if self._folder_sig is not None and sig != self._folder_sig:
            page.refresh()
        self._folder_sig = sig

    def sync_shared(self):
        try:
            if self.store.sync():
                page = self.pages.currentWidget()
                if page in (self.declarations, self.records, self.catalog, self.customers, self.data_tong, self.kho) and hasattr(page, "refresh"):
                    page.refresh()
        except Exception:
            pass  # thư mục dùng chung tạm thời không đọc được (đang đồng bộ): thử lại lần sau

    def closeEvent(self, e):
        widgets.wait_jobs()  # đợi việc nền xong, tránh hủy luồng giữa chừng
        super().closeEvent(e)

    def show_page(self, i):
        self.pages.setCurrentIndex(i)
        if 0 <= i < len(BANNERS):
            self.banner.set_text(*BANNERS[i])
        self.sync_shared()
        page = self.pages.widget(i)
        if hasattr(page, "refresh"):
            page.refresh()

    def make_lot_for(self, key):
        """Nút 'Tạo bộ hồ sơ cho khách hàng này' ở trang Khách hàng: sang Làm chứng từ với khách đã chọn."""
        self.lot.start_new()
        self.lot.lot.select_customer(key)
        self.lot.step1.refresh()
        self.nav.setCurrentRow(0)

    def open_record(self, rec):
        self.lot.open_record(rec)
        self.nav.setCurrentRow(0)


def _install_error_hook(core, parent_getter):
    """Bản .exe không có console: ghi lỗi ra LOI_PHAN_MEM.txt cạnh phần mềm và báo bằng hộp thoại."""
    def hook(exc_type, exc, tb):
        err = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(os.path.join(core.get_app_dir(), "LOI_PHAN_MEM.txt"), "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.datetime.now():%d/%m/%Y %H:%M:%S} (giao diện mới) =====\n{err}")
        except Exception:
            pass
        sys.stderr and sys.stderr.write(err)
        QMessageBox.critical(parent_getter(), "Phần mềm gặp lỗi",
                             f"{exc}\n\nChi tiết đã ghi vào file LOI_PHAN_MEM.txt cạnh phần mềm. Gửi file này cho người hỗ trợ.")
    sys.excepthook = hook


def load_fonts():
    """Nạp font Be Vietnam Pro đóng gói kèm phần mềm (thư mục fonts/, giấy phép OFL); không có thì dùng Segoe UI."""
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    d = os.path.join(root, "fonts")
    n = 0
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if fn.lower().endswith(".ttf") and QFontDatabase.addApplicationFont(os.path.join(d, fn)) >= 0:
            n += 1
    return n


def run(core, store, smoke=False):
    """Mở giao diện mới. `smoke`: tự đóng sau 3 giây (kiểm tra bản đóng gói)."""
    app = QApplication.instance() or QApplication([])
    load_fonts()
    app.setStyleSheet(theme.STYLE)
    icons.install(app)
    win = MainWindow(core, store)
    _install_error_hook(core, lambda: win)
    win.show()
    if smoke:
        QTimer.singleShot(3000, app.quit)
    return app.exec()

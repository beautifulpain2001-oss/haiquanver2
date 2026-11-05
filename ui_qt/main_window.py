"""Cửa sổ chính của giao diện mới: thanh điều hướng bên trái + các trang."""

import datetime
import os
import sys
import traceback

from PySide6.QtCore import QSize, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from . import icons, theme, widgets
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
                it.setIcon(icons.make_icon(name, "#E2E8F0", "#94A3B8", 20))
            self.nav.addItem(it)
        self.nav.setIconSize(QSize(20, 20))
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
        lay.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)

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
        self.sync_shared()
        page = self.pages.widget(i)
        if hasattr(page, "refresh"):
            page.refresh()

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


def run(core, store, smoke=False):
    """Mở giao diện mới. `smoke`: tự đóng sau 3 giây (kiểm tra bản đóng gói)."""
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.STYLE)
    icons.install(app)
    win = MainWindow(core, store)
    _install_error_hook(core, lambda: win)
    win.show()
    if smoke:
        QTimer.singleShot(3000, app.quit)
    return app.exec()

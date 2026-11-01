"""Các trang ngoài luồng làm chứng từ: Hồ sơ đã lưu, Danh mục, Khách hàng, Cài đặt."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from . import widgets


def _head(title, hint=""):
    t = QLabel(title)
    t.setObjectName("title")
    h = QLabel(hint)
    h.setObjectName("hint")
    h.setWordWrap(True)
    return t, h


def _table(headers, stretch_col=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().hide()
    t.setAlternatingRowColors(True)
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_col is not None:
        hh.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    return t


def _fill(table, rows, right=()):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            cell = QTableWidgetItem("" if v is None else str(v))
            if c in right:
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, cell)


class _Page(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(28, 24, 28, 24)
        self.lay.setSpacing(10)

    def search_box(self, placeholder, on_change):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.textChanged.connect(on_change)
        return e


class RecordsPage(_Page):
    open_record = Signal(dict)

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.shown = core, store, []
        self.lay.addWidget(_head("Hồ sơ đã lưu", "Các lô hàng đã làm. Chọn một dòng để mở lại và làm tiếp.")[0])
        self.lay.addWidget(_head("", "Các lô hàng đã làm. Chọn một dòng để mở lại và làm tiếp.")[1])
        self.search = self.search_box("🔍  Tìm theo số PO, PXK, hóa đơn, tờ khai hoặc tên khách…", lambda _t: self.refresh())
        self.lay.addWidget(self.search)
        self.table = _table(["Khách", "Ngày chứng từ", "Số PO", "Số PXK", "Số HĐ", "Số tờ khai", "Thành tiền (VNĐ)", "Cả bì / Tịnh (kg)", "File đã nạp"], 2)
        self.table.doubleClicked.connect(lambda _i: self.reopen())
        self.lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        b1 = QPushButton("✏  Mở lại để làm tiếp")
        b1.clicked.connect(self.reopen)
        b2 = QPushButton("📁  Mở thư mục hồ sơ")
        b2.setObjectName("sec")
        b2.clicked.connect(self.open_dir)
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)
        self.lay.addLayout(row)

    def refresh(self):
        q = self.search.text().lower().strip()
        slots = self.core.DOC_SLOTS
        rows, self.shown = [], []
        for r in self.store.records:
            hay = f"{r.get('poNumber','')} {r.get('pxkNo','')} {r.get('hdNo','')} {r.get('tkNo','')} {r.get('customer','')}".lower()
            if q and q not in hay:
                continue
            files = r.get("files") or {}
            label = self.core.PROFILES.get(r.get("customer", ""), {}).get("label", r.get("customer", ""))
            rows.append([label, r.get("docDate", ""), r.get("poNumber", ""), r.get("pxkNo") or "Chờ cấp", r.get("hdNo") or "Chờ ký",
                         r.get("tkNo") or "Chưa khai", widgets.fmt_num(r.get("totalAmount")),
                         f"{r.get('totalGross', 0):,.1f} / {r.get('totalNet', 0):,.1f}", f"{sum(1 for k, _, _ in slots if files.get(k))}/{len(slots)}"])
            self.shown.append(r)
        _fill(self.table, rows, right=(6, 7))

    def current(self):
        rows = self.table.selectionModel().selectedRows()
        return self.shown[rows[0].row()] if rows else None

    def reopen(self):
        rec = self.current()
        if rec is None:
            widgets.warn(self, "Mở hồ sơ", "Hãy bấm chọn một hồ sơ trong danh sách trước.")
            return
        self.open_record.emit(rec)

    def open_dir(self):
        rec = self.current()
        if rec is not None:
            widgets.open_folder(self.store.get_record_folder_path(rec))


class CatalogPage(_Page):
    def __init__(self, core, store):
        super().__init__()
        self.store = store
        t, h = _head("Danh mục", "Tra cứu định mức cân nặng và mã hàng ERP. Định mức của từng mặt hàng được sửa khi bấm “Sửa dòng” lúc làm chứng từ.")
        self.lay.addWidget(t)
        self.lay.addWidget(h)
        self.search = self.search_box("🔍  Gõ để lọc theo tên hoặc mã…", lambda _t: self.refresh())
        self.lay.addWidget(self.search)
        self.tabs = QTabWidget()
        self.weights = _table(["STT", "Tên hàng hóa & quy cách", "Cân thực tế (g)", "Định mức (kg/cái)"], 1)
        self.erp = _table(["STT", "Mã SP / TM", "Tên sản phẩm", "Mô tả"], 2)
        self.tabs.addTab(self.weights, "Thư viện cân nặng")
        self.tabs.addTab(self.erp, "Danh mục ERP (mã TM)")
        self.lay.addWidget(self.tabs, 1)

    def refresh(self):
        q = self.search.text().lower().strip()
        w = [(n, it) for n, it in self.store.weights_db.items() if not q or q in n.lower()]
        _fill(self.weights, [[i, n, it.get("g", ""), it.get("kg", "")] for i, (n, it) in enumerate(w, 1)], right=(2, 3))
        e = [x for x in self.store.erp_catalog if not q or q in f"{x.get('ma_sp','')} {x.get('ten_sp','')}".lower()]
        _fill(self.erp, [[i, x.get("ma_sp", ""), x.get("ten_sp", ""), x.get("mota", "")] for i, x in enumerate(e, 1)])
        self.tabs.setTabText(0, f"Thư viện cân nặng ({len(w)})")
        self.tabs.setTabText(1, f"Danh mục ERP ({len(e)})")


class CustomersPage(_Page):
    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        t, h = _head("Khách hàng", "Danh sách khách hàng phần mềm đã biết. Thêm khách mới từ chứng từ mẫu hiện làm ở giao diện cũ "
                                   "(bấm đúp file .exe); chức năng này sẽ chuyển sang giao diện mới ở bản sau.")
        self.lay.addWidget(t)
        self.lay.addWidget(h)
        self.table = _table(["Mã", "Tên khách hàng", "Mã số thuế", "ĐVT", "Số mặt hàng đã biết", "Loại"], 1)
        self.lay.addWidget(self.table, 1)

    def refresh(self):
        c = self.core
        rows = [[k, p.get("name", ""), p.get("mst", ""), p.get("unit", ""), len(self.store.items_for_customer(k)),
                 "Có sẵn" if k in c.BUILTIN_CUSTOMERS else "Đã học"] for k, p in c.PROFILES.items()]
        _fill(self.table, rows, right=(4,))


class SettingsPage(_Page):
    data_changed = Signal()

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        t, h = _head("Cài đặt", "Nơi lưu dữ liệu và tình trạng bộ đọc ảnh scan (OCR).")
        self.lay.addWidget(t)
        self.lay.addWidget(h)
        self.path = QLabel()
        self.path.setWordWrap(True)
        self.path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lay.addWidget(self.path)
        row = QHBoxLayout()
        b1 = QPushButton("📂  Đổi thư mục lưu dữ liệu…")
        b1.clicked.connect(self.change_dir)
        b2 = QPushButton("📁  Mở thư mục dữ liệu")
        b2.setObjectName("sec")
        b2.clicked.connect(lambda: widgets.open_folder(self.store.base_dir))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)
        self.lay.addLayout(row)
        self.ocr = QLabel()
        self.ocr.setWordWrap(True)
        self.lay.addWidget(self.ocr)
        tip = QLabel("Mẹo: nên đặt thư mục dữ liệu ở nơi cố định (ví dụ D:\\HongThien hoặc ổ mạng dùng chung), tránh thư mục Downloads vì dễ bị dọn nhầm.")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        self.lay.addWidget(tip)
        self.lay.addStretch(1)
        self.refresh()

    def refresh(self):
        self.path.setText(f"Thư mục dữ liệu hiện tại: {self.store.base_dir}")
        ok = self.core.ocr_available()
        self.ocr.setText("✅  Đọc ảnh scan (OCR): sẵn sàng." if ok else
                         "⚠  Đọc ảnh scan (OCR): chưa dùng được. Hãy để thư mục Tesseract-OCR cạnh file .exe. PDF có sẵn chữ và file Excel vẫn đọc bình thường.")

    def change_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu dữ liệu")
        if not d:
            return
        self.store.change_base_dir(d)
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã đổi thư mục dữ liệu", f"Phần mềm sẽ lưu và đọc dữ liệu tại:\n{self.store.base_dir}")

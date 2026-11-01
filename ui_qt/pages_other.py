"""Các trang ngoài luồng làm chứng từ: Hồ sơ đã lưu, Danh mục, Khách hàng, Cài đặt."""

import datetime
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
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


REC_COLS = ["Khách", "Ngày chứng từ", "Số tờ khai", "Luồng", "Số PO", "Số PXK", "Số HĐ", "Thành tiền (VNĐ)", "Người làm", "Thư mục trên máy", "Mở"]
COL_CUST, COL_FOLDER, COL_OPEN = 0, 9, 10


class RecordTable(QTableWidget):
    """Bảng hồ sơ kèm đường dẫn thư mục trên máy và nút mở thư mục."""

    def __init__(self, core, store, show_customer=True, compact=False):
        super().__init__(0, len(REC_COLS))
        self.core, self.store, self.recs = core, store, []
        self.setHorizontalHeaderLabels(REC_COLS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)  # đường dẫn dài: rút gọn ở giữa thay vì bẻ từng ký tự (rê chuột để xem đủ)
        self.setTextElideMode(Qt.ElideMiddle)
        self.verticalHeader().setDefaultSectionSize(46)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_FOLDER, QHeaderView.Stretch)
        hh.setMinimumSectionSize(60)
        hh.setSectionResizeMode(COL_OPEN, QHeaderView.Fixed)
        self.setColumnWidth(COL_OPEN, 150)
        self.setColumnHidden(COL_CUST, not show_customer)
        for c in ((3, 5, 6, 7) if compact else ()):  # bản gọn: chỉ giữ ngày, số tờ khai, số PO, thư mục để nút mở thư mục luôn trong tầm nhìn
            self.setColumnHidden(c, True)

    def folder_of(self, rec):
        return self.store.get_record_folder_path(rec)

    def set_records(self, recs):
        self.recs = list(recs)
        self.setRowCount(len(self.recs))
        for r, rec in enumerate(self.recs):
            folder = self.folder_of(rec)
            label = self.core.PROFILES.get(rec.get("customer", ""), {}).get("label", rec.get("customer", ""))
            vals = [label, rec.get("docDate", ""), rec.get("tkNo") or "Chưa khai", rec.get("luong", ""), rec.get("poNumber", ""),
                    rec.get("pxkNo") or "Chờ cấp", rec.get("hdNo") or "Chờ ký", widgets.fmt_num(rec.get("totalAmount")), rec.get("workedBy") or "", folder]
            for c, v in enumerate(vals):
                cell = QTableWidgetItem(str(v))
                if c == 7:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == COL_FOLDER:
                    cell.setToolTip(folder)
                self.setItem(r, c, cell)
            btn = QPushButton("📁  Mở thư mục")
            btn.setObjectName("sec")
            exists = os.path.isdir(folder)
            btn.setEnabled(exists)
            btn.setToolTip(folder if exists else "Chưa có thư mục này trên máy (hồ sơ chưa xuất file nào).")
            btn.clicked.connect(lambda _=False, f=folder: widgets.open_folder(f))
            self.setCellWidget(r, COL_OPEN, btn)


def _declared(rec):
    return bool(str(rec.get("tkNo") or "").strip())


def _month_of(rec):
    d = str(rec.get("docDate") or "")
    return d[:7] if len(d) >= 7 and d[4] == "-" else ""


class CustomerView(QWidget):
    """Theo khách hàng: bấm một khách để xem các tờ khai đã khai và thư mục của từng hồ sơ."""

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.keys = core, store, []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 0)
        self.list = QListWidget()
        self.list.setFixedWidth(220)
        self.list.currentRowChanged.connect(self.show_customer)
        lay.addWidget(self.list)
        right = QVBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("h2")
        self.title.setWordWrap(True)
        right.addWidget(self.title)
        self.all_box = QCheckBox("Hiện cả hồ sơ chưa khai tờ khai")
        self.all_box.toggled.connect(lambda _v: self.show_customer(self.list.currentRow()))
        right.addWidget(self.all_box)
        self.table = RecordTable(core, store, show_customer=False, compact=True)
        right.addWidget(self.table, 1)
        self.empty = QLabel("")
        self.empty.setObjectName("hint")
        self.empty.setWordWrap(True)
        right.addWidget(self.empty)
        lay.addLayout(right, 1)

    def records_of(self, key):
        recs = [r for r in self.store.records if r.get("customer") == key]
        return sorted(recs, key=lambda r: str(r.get("docDate") or ""), reverse=True)

    def refresh(self):
        keep = self.keys[self.list.currentRow()] if 0 <= self.list.currentRow() < len(self.keys) else None
        self.keys = list(self.core.PROFILES)
        self.list.blockSignals(True)
        self.list.clear()
        for k in self.keys:
            n = sum(1 for r in self.records_of(k) if _declared(r))
            self.list.addItem(f"{self.core.PROFILES[k].get('label') or k}  ·  {n} tờ khai đã khai")
        self.list.blockSignals(False)
        self.list.setCurrentRow(self.keys.index(keep) if keep in self.keys else 0)

    def show_customer(self, row):
        if not (0 <= row < len(self.keys)):
            return
        key = self.keys[row]
        recs = self.records_of(key)
        shown = recs if self.all_box.isChecked() else [r for r in recs if _declared(r)]
        label = self.core.PROFILES[key].get("label") or key
        self.title.setText(f"{label} — {sum(1 for r in recs if _declared(r))} tờ khai đã khai" + (f" · {len(recs)} hồ sơ" if self.all_box.isChecked() else ""))
        self.table.set_records(shown)
        self.empty.setText("" if shown else (f"Khách {label} chưa có tờ khai nào được ghi nhận." + ("" if self.all_box.isChecked() else " Tích “Hiện cả hồ sơ chưa khai tờ khai” để xem các hồ sơ khác.")))


class MonthView(QWidget):
    """Theo tháng: mặc định hiện hồ sơ của tháng hiện tại; chuyển sang tháng khác bằng ô chọn hoặc mũi tên."""

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        self.current = datetime.date.today().strftime("%Y-%m")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 0)
        bar = QHBoxLayout()
        self.prev = QPushButton("◀")
        self.prev.setObjectName("sec")
        self.next = QPushButton("▶")
        self.next.setObjectName("sec")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(190)
        self.prev.clicked.connect(lambda: self.step(1))   # danh sách xếp mới -> cũ, nên "trước" là chỉ số lớn hơn
        self.next.clicked.connect(lambda: self.step(-1))
        self.combo.currentIndexChanged.connect(self.show_month)
        for w in (self.prev, self.combo, self.next):
            bar.addWidget(w)
        self.summary = QLabel("")
        self.summary.setObjectName("h2")
        bar.addSpacing(16)
        bar.addWidget(self.summary, 1)
        lay.addLayout(bar)
        self.table = RecordTable(core, store, show_customer=True)
        lay.addWidget(self.table, 1)
        self.empty = QLabel("")
        self.empty.setObjectName("hint")
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)

    def months(self):
        found = {_month_of(r) for r in self.store.records} - {""}
        found.add(datetime.date.today().strftime("%Y-%m"))
        return sorted(found, reverse=True)

    def refresh(self, month=None):
        keep = month or self.combo.currentData() or self.current  # lần đầu: tháng hiện tại
        months = self.months()
        self.combo.blockSignals(True)
        self.combo.clear()
        for m in months:
            self.combo.addItem(f"Tháng {m[5:7]}/{m[:4]}", m)
        self.combo.setCurrentIndex(months.index(keep) if keep in months else months.index(self.current))
        self.combo.blockSignals(False)
        self.show_month()

    def step(self, d):
        i = self.combo.currentIndex() + d
        if 0 <= i < self.combo.count():
            self.combo.setCurrentIndex(i)

    def show_month(self, _i=None):
        m = self.combo.currentData()
        recs = sorted((r for r in self.store.records if _month_of(r) == m), key=lambda r: str(r.get("docDate") or ""), reverse=True)
        self.prev.setEnabled(self.combo.currentIndex() < self.combo.count() - 1)
        self.next.setEnabled(self.combo.currentIndex() > 0)
        total = sum(float(r.get("totalAmount") or 0) for r in recs)
        self.summary.setText(f"{len(recs)} hồ sơ · {sum(1 for r in recs if _declared(r))} đã khai tờ khai · {widgets.fmt_num(total)} VNĐ" if recs else "")
        self.table.set_records(recs)
        self.empty.setText("" if recs else f"Tháng {m[5:7]}/{m[:4]} chưa có hồ sơ nào." + (" Chọn tháng khác ở ô phía trên." if len(self.months()) > 1 else ""))


class CatalogPage(_Page):
    """Danh mục: hồ sơ theo tháng, hồ sơ theo khách hàng, thư viện cân nặng, danh mục ERP."""

    def __init__(self, core, store):
        super().__init__()
        self.store = store
        t, h = _head("Danh mục", "Xem hồ sơ đã làm theo tháng hoặc theo khách hàng (kèm thư mục trên máy), và tra cứu định mức cân nặng, mã hàng ERP.")
        self.lay.addWidget(t)
        self.lay.addWidget(h)
        self.search = self.search_box("🔍  Gõ để lọc theo tên hoặc mã…", lambda _t: self.refresh_tables())
        self.tabs = QTabWidget()
        self.by_month = MonthView(core, store)
        self.by_customer = CustomerView(core, store)
        self.weights = _table(["STT", "Tên hàng hóa & quy cách", "Cân thực tế (g)", "Định mức (kg/cái)"], 1)
        self.erp = _table(["STT", "Mã SP / TM", "Tên sản phẩm", "Mô tả"], 2)
        self.tabs.addTab(self.by_month, "Hồ sơ theo tháng")
        self.tabs.addTab(self.by_customer, "Hồ sơ theo khách hàng")
        self.tabs.addTab(self.weights, "Thư viện cân nặng")
        self.tabs.addTab(self.erp, "Danh mục ERP (mã TM)")
        self.tabs.currentChanged.connect(self.on_tab)
        self.lay.addWidget(self.search)
        self.lay.addWidget(self.tabs, 1)
        self.on_tab(0)

    def on_tab(self, i):
        self.search.setVisible(i >= 2)  # ô lọc chỉ dùng cho cân nặng / ERP
        self.refresh_tabs()

    def refresh_tables(self):
        q = self.search.text().lower().strip()
        w = [(n, it) for n, it in self.store.weights_db.items() if not q or q in n.lower()]
        _fill(self.weights, [[i, n, it.get("g", ""), it.get("kg", "")] for i, (n, it) in enumerate(w, 1)], right=(2, 3))
        e = [x for x in self.store.erp_catalog if not q or q in f"{x.get('ma_sp','')} {x.get('ten_sp','')}".lower()]
        _fill(self.erp, [[i, x.get("ma_sp", ""), x.get("ten_sp", ""), x.get("mota", "")] for i, x in enumerate(e, 1)])
        self.tabs.setTabText(2, f"Thư viện cân nặng ({len(w)})")
        self.tabs.setTabText(3, f"Danh mục ERP ({len(e)})")

    def refresh_tabs(self):
        i = self.tabs.currentIndex()
        if i == 0:
            self.by_month.refresh()
        elif i == 1:
            self.by_customer.refresh()
        else:
            self.refresh_tables()

    def refresh(self):
        self.refresh_tabs()
        self.refresh_tables()  # đủ số lượng trên nhãn tab


class CustomerForm(QWidget):
    """Biểu mẫu thông tin khách (dùng cho sửa và thêm mới)."""

    def __init__(self, core, with_hint=False):
        super().__init__()
        self.core = core
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignLeft)
        self.edits = {}
        for key, label in core.CUSTOMER_FIELDS:
            e = QLineEdit()
            self.edits[key] = e
            form.addRow(label, e)

    def load(self, prof):
        for k, e in self.edits.items():
            e.setText(str((prof or {}).get(k) or ""))

    def values(self):
        return {k: e.text() for k, e in self.edits.items()}

    def set_enabled(self, on):
        for e in self.edits.values():
            e.setEnabled(on)


class NewCustomerDialog(QDialog):
    def __init__(self, core, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.key = None
        self.setWindowTitle("Thêm khách hàng mới")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        hint = QLabel("Nhập thông tin hành chính của khách. Khách mới chưa có danh mục hàng nên phần mềm chưa tự đọc được PO; "
                      "bạn thêm dòng hàng bằng tay (định mức được nhớ cho lần sau).")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.form = CustomerForm(core)
        lay.addWidget(self.form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Lưu khách hàng")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def save(self):
        try:
            self.key = self.store.add_customer(self.form.values())
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được", str(e))
            return
        self.accept()


class CustomersPage(_Page):
    changed = Signal()

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.keys = core, store, []
        t, h = _head("Khách hàng", "Chọn một khách để xem và sửa thông tin (tên, mã số thuế, địa chỉ…). Thông tin được lưu và in lên các chứng từ.")
        self.lay.addWidget(t)
        self.lay.addWidget(h)
        self.table = _table(["Tên gọi", "Tên công ty", "Mã số thuế", "Địa chỉ", "Loại"], 1)
        self.table.setMaximumHeight(220)
        self.table.itemSelectionChanged.connect(self.on_select)
        self.lay.addWidget(self.table)
        box = QGroupBox("Thông tin khách hàng")
        bl = QVBoxLayout(box)
        self.form = CustomerForm(core)
        bl.addWidget(self.form)
        row = QHBoxLayout()
        self.save_btn = QPushButton("💾  Lưu thay đổi")
        self.save_btn.clicked.connect(self.save)
        self.add_btn = QPushButton("➕  Thêm khách hàng mới")
        self.add_btn.setObjectName("sec")
        self.add_btn.clicked.connect(self.add)
        row.addWidget(self.save_btn)
        row.addWidget(self.add_btn)
        row.addStretch(1)
        bl.addLayout(row)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        bl.addWidget(self.msg)
        self.lay.addWidget(box)
        self.lay.addStretch(1)
        self.form.set_enabled(False)
        self.save_btn.setEnabled(False)

    def refresh(self, select=None):
        c = self.core
        self.keys = list(c.PROFILES)
        rows = [[p.get("label", k), p.get("name", ""), p.get("mst", ""), p.get("addr", ""), "Có sẵn" if k in c.BUILTIN_CUSTOMERS else "Đã học / thêm mới"]
                for k, p in c.PROFILES.items()]
        self.table.blockSignals(True)
        _fill(self.table, rows)
        self.table.blockSignals(False)
        if select in self.keys:
            self.table.selectRow(self.keys.index(select))
        self.on_select()

    def current_key(self):
        rows = self.table.selectionModel().selectedRows()
        return self.keys[rows[0].row()] if rows else None

    def on_select(self):
        key = self.current_key()
        self.form.set_enabled(bool(key))
        self.save_btn.setEnabled(bool(key))
        self.form.load(self.core.PROFILES.get(key) if key else None)

    def save(self):
        key = self.current_key()
        if not key:
            return
        try:
            self.store.update_customer(key, self.form.values())
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được", str(e))
            return
        self.msg.setText("✅  Đã lưu thông tin khách hàng. Các chứng từ xuất từ giờ sẽ dùng thông tin này.")
        self.refresh(select=key)
        self.changed.emit()

    def add(self):
        dlg = NewCustomerDialog(self.core, self.store, self)
        if dlg.exec():
            self.msg.setText("✅  Đã thêm khách hàng mới.")
            self.refresh(select=dlg.key)
            self.changed.emit()


class SettingsPage(_Page):
    data_changed = Signal()
    company_changed = Signal()

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store = core, store
        self.lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("page")
        scroll.setWidget(body)
        self.lay.addWidget(scroll)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)
        t, h = _head("Cài đặt", "Thông tin công ty được in lên hóa đơn, phiếu xuất kho, invoice, đề nghị thanh toán, tờ khai… Sửa ở đây là áp dụng cho các chứng từ xuất từ lần sau.")
        lay.addWidget(t)
        lay.addWidget(h)

        box = QGroupBox("Thông tin công ty của bạn")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignLeft)
        self.company = {}
        for key, label in core.COMPANY_FIELDS:
            e = QLineEdit()
            self.company[key] = e
            form.addRow(label, e)
        lay.addWidget(box)
        row = QHBoxLayout()
        self.save_btn = QPushButton("💾  Lưu thông tin công ty")
        self.save_btn.clicked.connect(self.save_company)
        self.reset_btn = QPushButton("↩  Điền lại thông tin mặc định")
        self.reset_btn.setObjectName("sec")
        self.reset_btn.clicked.connect(self.fill_defaults)
        row.addWidget(self.save_btn)
        row.addWidget(self.reset_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.company_msg = QLabel("")
        self.company_msg.setObjectName("hint")
        self.company_msg.setWordWrap(True)
        lay.addWidget(self.company_msg)

        ubox = QGroupBox("Người dùng máy này")
        ul = QVBoxLayout(ubox)
        uh = QLabel("Nhập tên của bạn (đúng như tên ghi ở ô “Nhân viên phụ trách” trong mục Khách hàng). Hồ sơ bạn làm sẽ ghi tên bạn; "
                    "chọn khách do người khác phụ trách thì phần mềm hỏi lại cho chắc. Tên này chỉ lưu trên máy này.")
        uh.setObjectName("hint")
        uh.setWordWrap(True)
        ul.addWidget(uh)
        urow = QHBoxLayout()
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("Ví dụ: Nguyễn Văn A")
        self.user_edit.setText(self.store.user_name())
        ub = QPushButton("💾  Lưu tên")
        ub.clicked.connect(self.save_user)
        urow.addWidget(self.user_edit, 1)
        urow.addWidget(ub)
        ul.addLayout(urow)
        self.user_msg = QLabel("")
        self.user_msg.setObjectName("hint")
        ul.addWidget(self.user_msg)
        lay.addWidget(ubox)

        dbox = QGroupBox("Nơi lưu dữ liệu (dùng chung nhiều máy)")
        dl = QVBoxLayout(dbox)
        tip = QLabel("Nhiều máy cùng dùng phần mềm: mỗi máy chọn CÙNG một thư mục này (ổ dùng chung, OneDrive, Google Drive...). "
                     "Không cần mạng LAN hay máy chủ. Thông tin cơ bản của hồ sơ và khách hàng đọc từ thư mục này; "
                     "muốn xem chi tiết thì mở thư mục hồ sơ.")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        dl.addWidget(tip)
        self.path = QLabel()
        self.path.setWordWrap(True)
        self.path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        dl.addWidget(self.path)
        drow = QHBoxLayout()
        b1 = QPushButton("📂  Đổi thư mục lưu dữ liệu…")
        b1.setObjectName("sec")
        b1.clicked.connect(self.change_dir)
        b2 = QPushButton("📁  Mở thư mục dữ liệu")
        b2.setObjectName("sec")
        b2.clicked.connect(lambda: widgets.open_folder(self.store.base_dir))
        drow.addWidget(b1)
        drow.addWidget(b2)
        drow.addStretch(1)
        dl.addLayout(drow)
        tip = QLabel("Mẹo: nên đặt thư mục dữ liệu ở nơi cố định (ví dụ D:\\HongThien hoặc ổ mạng dùng chung), tránh thư mục Downloads vì dễ bị dọn nhầm.")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        dl.addWidget(tip)
        lay.addWidget(dbox)

        lbox = QGroupBox("Dữ liệu học (định mức từng mặt hàng)")
        ll = QVBoxLayout(lbox)
        ll.addWidget(QLabel("Nạp file dữ liệu học (.json) do người hỗ trợ cung cấp: số lượng mỗi kiện, kg mỗi cái của từng mặt hàng. "
                            "Định mức bạn đã tự nhập được giữ nguyên, không bị ghi đè."))
        ll.itemAt(0).widget().setWordWrap(True)
        lrow = QHBoxLayout()
        lb = QPushButton("📥  Nạp dữ liệu học…")
        lb.setObjectName("sec")
        lb.clicked.connect(self.import_learned)
        lrow.addWidget(lb)
        lrow.addStretch(1)
        ll.addLayout(lrow)
        self.learn_msg = QLabel("")
        self.learn_msg.setObjectName("hint")
        self.learn_msg.setWordWrap(True)
        ll.addWidget(self.learn_msg)
        lay.addWidget(lbox)

        obox = QGroupBox("Đọc ảnh scan (OCR)")
        ol = QVBoxLayout(obox)
        self.ocr = QLabel("Đang kiểm tra…")
        self.ocr.setWordWrap(True)
        ol.addWidget(self.ocr)
        lay.addWidget(obox)
        lay.addStretch(1)
        self.load_company()
        self.refresh()

    # --- thông tin công ty
    def load_company(self):
        info = self.store.company_info()
        for k, e in self.company.items():
            e.setText(str(info.get(k, "")))

    def fill_defaults(self):
        for k, e in self.company.items():
            e.setText(str(self.core.COMPANY_DEFAULTS.get(k, "")))
        self.company_msg.setText("Đã điền lại thông tin mặc định. Bấm “Lưu thông tin công ty” để áp dụng.")

    def save_company(self):
        try:
            self.store.set_company({k: e.text() for k, e in self.company.items()})
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được", str(e))
            return
        self.company_msg.setText("✅  Đã lưu thông tin công ty. Các chứng từ xuất từ giờ sẽ dùng thông tin này.")
        self.company_changed.emit()

    # --- dữ liệu / OCR
    def refresh(self):
        self.path.setText(f"Thư mục dữ liệu hiện tại: {self.store.base_dir}")
        self.show_ocr()

    def show_ocr(self):
        """Kiểm tra OCR phải chạy chương trình Tesseract nên làm ở nền; trang hiện ngay, kết quả điền sau."""
        if self.core._OCR_OK is not None:
            self.set_ocr(self.core._OCR_OK)
            return
        self.ocr.setText("Đang kiểm tra…")
        widgets.run_job(self, self.core.ocr_available, self.set_ocr)

    def set_ocr(self, ok):
        self.ocr.setText("✅  Đọc ảnh scan (OCR): sẵn sàng." if ok else
                         "⚠  Đọc ảnh scan (OCR): chưa dùng được. Hãy để thư mục Tesseract-OCR cạnh file .exe. PDF có sẵn chữ và file Excel vẫn đọc bình thường.")

    def import_learned(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Chọn file dữ liệu học", "", "Dữ liệu học (*.json)")
        if not path:
            return
        import json
        try:
            with open(path, encoding="utf-8") as f:
                res = self.store.import_learned(json.load(f))
        except (ValueError, OSError) as e:  # json lỗi cũng là ValueError
            widgets.warn(self, "Chưa nạp được dữ liệu học", str(e))
            return
        kh = f" Đã thêm khách hàng “{res['khach']}”." if res.get("khach") else ""
        self.learn_msg.setText(f"✅ {kh} Đã thêm {res['them']} mặt hàng; bỏ qua {res['bo_qua']} mặt hàng đã có định mức.")
        if res.get("khach"):
            self.data_changed.emit()

    def save_user(self):
        self.store.set_user_name(self.user_edit.text())
        self.user_msg.setText(f"✅  Đã lưu: máy này là “{self.store.user_name() or '(chưa đặt tên)'}”.")

    def change_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu dữ liệu")
        if not d:
            return
        self.store.change_base_dir(d)
        self.load_company()
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã đổi thư mục dữ liệu", f"Phần mềm sẽ lưu và đọc dữ liệu tại:\n{self.store.base_dir}")

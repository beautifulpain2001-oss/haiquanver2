"""Trang Danh mục: hồ sơ theo tháng, theo khách, thư viện cân nặng, danh mục ERP."""

import datetime

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QPushButton, QTabWidget, QVBoxLayout, QWidget

from .. import widgets
from ._base import _Page, _big_table, _head
from .records import RecordTable, _declared, _month_of


class CustomerView(QWidget):
    """Theo khách hàng: bấm một khách để xem các tờ khai đã khai và thư mục của từng hồ sơ."""

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.keys, self.entries = core, store, [], []
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
        return [r for r in self.entries if (r.get("customer") or "dir:" + r.get("_dir", "")) == key]

    def refresh(self):
        keep = self.keys[self.list.currentRow()] if 0 <= self.list.currentRow() < len(self.keys) else None
        self.entries = self.store.declaration_entries()  # cùng nguồn với trang 'Tờ khai đang có': quét thư mục thật
        self.keys = list(self.core.PROFILES) + sorted({"dir:" + r["_dir"] for r in self.entries if not r.get("customer")})
        self.list.blockSignals(True)
        self.list.clear()
        for k in self.keys:
            n = sum(1 for r in self.records_of(k) if _declared(r))
            self.list.addItem(f"{self.label_of(k)}  ·  {n} tờ khai đã khai")
        self.list.blockSignals(False)
        self.list.setCurrentRow(self.keys.index(keep) if keep in self.keys else 0)

    def label_of(self, key):
        if key.startswith("dir:"):
            return key[4:]
        return self.core.PROFILES[key].get("label") or key

    def show_customer(self, row):
        if not (0 <= row < len(self.keys)):
            return
        key = self.keys[row]
        recs = self.records_of(key)
        shown = recs if self.all_box.isChecked() else [r for r in recs if _declared(r)]
        label = self.label_of(key)
        self.title.setText(f"{label} — {sum(1 for r in recs if _declared(r))} tờ khai đã khai" + (f" · {len(recs)} thư mục" if self.all_box.isChecked() else ""))
        self.table.set_records(shown)
        self.empty.setText("" if shown else (f"Khách {label} chưa có tờ khai nào được ghi nhận." + ("" if self.all_box.isChecked() else " Tích “Hiện cả hồ sơ chưa khai tờ khai” để xem các hồ sơ khác.")))


class MonthView(QWidget):
    """Theo tháng: mặc định hiện hồ sơ của tháng hiện tại; chuyển sang tháng khác bằng ô chọn hoặc mũi tên."""

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.entries = core, store, []
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
        found = {_month_of(r) for r in self.entries} - {""}
        found.add(datetime.date.today().strftime("%Y-%m"))
        return sorted(found, reverse=True)

    def refresh(self, month=None):
        keep = month or self.combo.currentData() or self.current  # lần đầu: tháng hiện tại
        self.entries = self.store.declaration_entries()  # quét thư mục thật, cùng nguồn với 'Tờ khai đang có'
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
        recs = sorted((r for r in self.entries if _month_of(r) == m), key=lambda r: str(r.get("docDate") or ""), reverse=True)
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
        self.weights = _big_table(["STT", "Tên hàng hóa & quy cách", "Cân thực tế (g)", "Định mức (kg/cái)"], [60, 400, 150, 150], 1, right=(2, 3))
        self.erp = _big_table(["STT", "Mã SP / TM", "Tên sản phẩm", "Mô tả"], [60, 180, 400, 300], 2)
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
        self.weights.model().set_rows([[k, n, it.get("g", ""), it.get("kg", "")] for k, (n, it) in enumerate(w, 1)])
        e = [x for x in self.store.erp_catalog if not q or q in f"{x.get('ma_sp','')} {x.get('ten_sp','')}".lower()]
        self.erp.model().set_rows([[k, x.get("ma_sp", ""), x.get("ten_sp", ""), x.get("mota", "")] for k, x in enumerate(e, 1)])
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
        self.refresh_tables()  # bảng lớn dùng model ảo: cập nhật tức thì, đủ số lượng trên nhãn tab

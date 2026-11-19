"""Bảng quản lý kg & kiện theo khách: ĐVT, SL/kiện, kg/chiếc của từng mã hàng và bì mỗi dòng. Đây là nguồn chuẩn của số khai."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from . import widgets

COLS = [("code", "Mã hàng"), ("name", "Tên hàng hóa & quy cách"), ("unit", "ĐVT"), ("div", "SL/kiện"), ("kg", "kg/chiếc"), ("khoa", "🔒 Khóa (sửa tay)")]
NUM = ("div", "kg")
DOI = QColor("#FEF3C7")   # ô vừa đổi, chưa lưu
LECH = QColor("#FEE2E2")  # các nơi lưu đang ghi số khác nhau: lưu bảng là đồng bộ lại


def _fmt(v):
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return str(v or "")
    return "" if f == 0 else f"{f:g}"


class DinhMucDialog(QDialog):
    """Chọn khách → sửa trực tiếp ĐVT, SL/kiện, kg/chiếc từng mã và bì mỗi dòng → Lưu. Sửa tay một ô thì dòng đó tự KHÓA:
    học Invoice / ERP về sau không ghi đè. Nút "Nạp Invoice đúng" lấy số chia trong công thức Số kiện (=ROUNDUP(F14/300,0) -> 300)."""

    def __init__(self, core, store, key=None, parent=None):
        super().__init__(parent)
        self.core, self.store = core, store
        self.key, self.rows, self.dirty, self._filling = None, [], False, False
        self.setWindowTitle("Kg & kiện theo khách")
        self.resize(1100, 720)
        lay = QVBoxLayout(self)
        hint = QLabel("Bảng chuẩn của từng khách: số ở đây được dùng khi đọc PO, tra mặt hàng và xuất chứng từ. Sửa trực tiếp trong ô rồi bấm Lưu. "
                      "Ô nào bạn sửa tay thì dòng đó được 🔒 khóa: học Invoice hay ERP sau này không ghi đè. "
                      "“Nạp Invoice đúng” đọc SL/kiện từ công thức cột Số kiện (=ROUNDUP(F14/300,0) → 300), không chia ngược.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        top = QHBoxLayout()
        top.addWidget(QLabel("Khách:"))
        self.cust = QComboBox()
        self.cust.setMinimumWidth(260)
        self.cust.setAccessibleName("Chọn khách")
        for k, label in core_customers(store):
            self.cust.addItem(label, k)
        top.addWidget(self.cust)
        top.addSpacing(16)
        top.addWidget(QLabel("Bì mỗi dòng (kg):"))
        self.bi = QLineEdit()
        self.bi.setMaximumWidth(80)
        self.bi.setAccessibleName("Bì mỗi dòng (kg)")
        self.bi.setToolTip("Cả bì = tịnh + số này, cho mỗi dòng hàng (ô bì ở bước xuất lấy số này làm mặc định).")
        self.bi.textEdited.connect(lambda _t: self._set_dirty())
        top.addWidget(self.bi)
        top.addSpacing(16)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Lọc theo mã hoặc tên…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        top.addWidget(self.search, 1)
        lay.addLayout(top)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemChanged.connect(self.on_cell)
        lay.addWidget(self.table, 1)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        bar = QHBoxLayout()
        self.inv_btn = QPushButton("📥  Nạp Invoice đúng…")
        self.inv_btn.setObjectName("sec")
        self.inv_btn.setToolTip("Chọn file Invoice Excel đúng của khách: SL/kiện, kg/chiếc, ĐVT của các dòng CHƯA khóa được lấy theo invoice (bạn xem lại rồi bấm Lưu).")
        self.inv_btn.clicked.connect(lambda: self.load_invoice())
        add = QPushButton("➕  Thêm mã")
        add.setObjectName("sec")
        add.clicked.connect(self.add_row)
        dele = QPushButton("🗑  Xóa dòng đã chọn")
        dele.setObjectName("dng")
        dele.clicked.connect(self.delete_rows)
        close = QPushButton("Đóng")
        close.setObjectName("sec")
        close.clicked.connect(self.reject)
        self.save_btn = QPushButton("💾  Lưu bảng kg && kiện")
        self.save_btn.clicked.connect(self.save)
        for b in (self.inv_btn, add, dele):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(close)
        bar.addWidget(self.save_btn)
        lay.addLayout(bar)
        self.cust.currentIndexChanged.connect(self.on_customer)
        i = self.cust.findData(key) if key else -1
        if i >= 0:
            self.cust.setCurrentIndex(i)
        self.on_customer()

    # ---- nạp / hiển thị ------------------------------------------------------------------------------------------
    def _set_dirty(self, on=True):
        self.dirty = on
        self.save_btn.setText("💾  Lưu bảng kg && kiện" + (" *" if on else ""))

    def on_customer(self, _i=None):
        k = self.cust.currentData()
        if k == self.key:
            return
        if self.dirty and self.key and not widgets.ask(self, "Chưa lưu", "Bảng của khách đang mở có chỗ sửa chưa lưu. Bỏ các chỗ sửa đó?"):
            self.cust.blockSignals(True)
            self.cust.setCurrentIndex(self.cust.findData(self.key))
            self.cust.blockSignals(False)
            return
        self.load(k)

    def load(self, key):
        self.key = key
        self.rows = []
        if key:
            for r in self.store.dinh_muc_rows(key):
                self.rows.append({**r, "_orig": {"code": r["code"], "name": r["name"]}})
        custom = bool(key) and key not in self.core.BUILTIN_CUSTOMERS
        self.bi.setText((_fmt(self.store.dinh_muc_bi(key)) or "0") if key else "")
        self.bi.setEnabled(custom)
        if not custom:
            self.bi.setToolTip("Khách có sẵn: bì nhập ở ô bì của bước xuất.")
        self.fill()
        self._set_dirty(False)
        lech = sum(1 for r in self.rows if r.get("lech"))
        self.say(f"{len(self.rows)} mã hàng." + (f" ⚠ {lech} mã đang lưu số khác nhau ở các nơi (ô tô đỏ): bấm Lưu để thống nhất theo số đang hiện." if lech else ""), None)

    def fill(self):
        self._filling = True
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            for c, (f, _) in enumerate(COLS):
                if f == "khoa":
                    cell = QTableWidgetItem("")
                    cell.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    cell.setCheckState(Qt.Checked if row.get("khoa") else Qt.Unchecked)
                else:
                    cell = QTableWidgetItem(_fmt(row.get(f)) if f in NUM else str(row.get(f) or ""))
                    if f in NUM:
                        cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if f in row.get("_doi", ()):
                        cell.setBackground(QBrush(DOI))
                    elif row.get("lech") and f in NUM:
                        cell.setBackground(QBrush(LECH))
                        cell.setToolTip("Các nơi lưu (danh mục khách, bộ nhớ định mức, Data tổng) đang ghi số khác nhau; số đang hiện là số phần mềm dùng. Lưu để thống nhất.")
                self.table.setItem(r, c, cell)
        self._filling = False
        self.apply_filter()

    def apply_filter(self, _t=None):
        q = self.search.text().strip().lower()
        for r, row in enumerate(self.rows):
            self.table.setRowHidden(r, bool(q) and q not in f"{row.get('code', '')} {row.get('name', '')}".lower())

    def say(self, text, ok):
        self.msg.setText(text)
        self.msg.setStyleSheet("" if ok is None else f"color: {'#03543F' if ok else '#9B1C1C'}; font-weight: 600;")

    # ---- sửa ----------------------------------------------------------------------------------------------------
    def on_cell(self, cell):
        if self._filling:
            return
        r, c = cell.row(), cell.column()
        if not (0 <= r < len(self.rows)):
            return
        f, row = COLS[c][0], self.rows[r]
        if f == "khoa":
            row["khoa"] = cell.checkState() == Qt.Checked
        else:
            text = cell.text().strip()
            if f in NUM:
                try:
                    v = float(text.replace(",", ".") or 0)
                except ValueError:
                    self.say(f"⚠ {COLS[c][1]} phải là số (dòng {r + 1}).", False)
                    return
                if abs(v - float(row.get(f) or 0)) < 1e-12:
                    return
                row[f] = v
            else:
                if text == str(row.get(f) or ""):
                    return
                row[f] = text
            row.setdefault("_doi", set()).add(f)
            if f in ("unit", "div", "kg") and not row.get("khoa"):  # sửa tay: khóa để học Invoice / ERP không ghi đè
                row["khoa"] = True
            self.fill()
        self._set_dirty()

    def add_row(self):
        self.rows.append({"code": "", "name": "", "unit": "", "div": 0, "kg": 0, "khoa": True, "_orig": None, "_doi": {"code", "name"}})
        self.search.clear()
        self.fill()
        self.table.scrollToBottom()
        self.table.setCurrentCell(len(self.rows) - 1, 0)
        self.table.editItem(self.table.item(len(self.rows) - 1, 0))
        self._set_dirty()

    def delete_rows(self):
        idx = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not idx:
            self.say("⚠ Chọn dòng cần xóa trước.", False)
            return
        if not widgets.ask(self, "Xóa mã hàng", f"Xóa {len(idx)} mã hàng khỏi danh mục của khách này (khi bấm Lưu)?"):
            return
        for i in idx:
            self.rows.pop(i)
        self.fill()
        self._set_dirty()

    def load_invoice(self, paths=None):
        if not self.key:
            return
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, "Chọn Invoice Excel đúng của khách", "", "Excel (*.xlsx *.xlsm)")
        if not paths:
            return
        inv, errs = self.store.dinh_muc_tu_invoice(list(paths))
        if not inv:
            self.say("⚠ Không đọc được dòng hàng nào từ invoice. " + " ".join(errs), False)
            return
        res = self.core.dinh_muc_ap_invoice(self.rows, inv)
        self.fill()
        if res["doi"] or res["them"]:
            self._set_dirty()
        name = {"div": "SL/kiện", "kg": "kg/chiếc", "unit": "ĐVT"}
        parts = [f"Theo invoice: đổi {len(res['doi'])} ô (tô vàng)" + (f", thêm {len(res['them'])} mã mới" if res["them"] else "") + ". Xem lại rồi bấm Lưu."]
        if res["giu"]:
            parts.append(f"Giữ nguyên {len(res['giu'])} ô của dòng đã khóa: " + "; ".join(f"{m} {name[f]} {_fmt(o) or o} (invoice {_fmt(n) or n})" for m, f, o, n in res["giu"][:6])
                         + (" …" if len(res["giu"]) > 6 else "") + ". Bỏ tích Khóa rồi nạp lại nếu muốn lấy số invoice.")
        if errs:
            parts.append("⚠ " + " ".join(errs))
        self.say(" ".join(parts), True)

    def save(self):
        if not self.key:
            return
        try:
            res = self.store.set_dinh_muc(self.key, self.rows, self.bi.text() if self.bi.isEnabled() else None)
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được", str(e))
            return
        self.dirty = False
        self.load(self.key)
        self.say(f"✅ Đã lưu: sửa {res['sua']}, thêm {res['them']}, xóa {res['xoa']} mã. Từ giờ đọc PO, tra mặt hàng và xuất chứng từ dùng số này.", True)

    def reject(self):
        if self.dirty and not widgets.ask(self, "Chưa lưu", "Có chỗ sửa chưa lưu. Đóng và bỏ các chỗ sửa đó?"):
            return
        super().reject()


def core_customers(store):
    return store.dinh_muc_customers()

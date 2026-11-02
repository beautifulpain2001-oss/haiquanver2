"""Hộp thoại thêm / sửa một dòng hàng."""

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from . import widgets

FIELDS = [
    ("po", "Số PO của dòng"), ("ma_sp", "Mã hàng"), ("ten_sp", "Tên hàng hóa"), ("hs", "Mã HS"), ("unit", "Đơn vị tính"),
    ("qty", "Số lượng"), ("price", "Đơn giá (VNĐ)"), ("div", "Số lượng mỗi kiện"), ("kg", "Trọng lượng mỗi chiếc (kg)"),
]
BEST_FIELDS = [("inquiry", "Inquiry No (Số đơn đặt hàng trên phiếu giao)"), ("customsNo", "Customs No (ghi chú phiếu giao)")]


class ItemDialog(QDialog):
    """Sửa một dòng. Bấm Lưu: kiểm tra số, tính kiện/tịnh/cả bì và NHỚ định mức cho lần sau."""

    def __init__(self, lot, idx=None, parent=None):
        super().__init__(parent)
        self.lot, self.idx = lot, idx
        self.setWindowTitle("Sửa dòng hàng" if idx is not None else "Thêm dòng hàng")
        self.setMinimumWidth(520)
        cur = dict(lot.items[idx]) if idx is not None else lot.new_item_values()
        lay = QVBoxLayout(self)
        hint = QLabel("Số lượng mỗi kiện và trọng lượng mỗi chiếc chỉ cần nhập một lần: phần mềm sẽ nhớ cho các lần sau.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        self.edits = {}
        for key, label in FIELDS + (BEST_FIELDS if lot.is_best else []):
            e = QLineEdit(str(cur.get(key, "") if cur.get(key) is not None else ""))
            self.edits[key] = e
            form.addRow(label, e)
        lay.addLayout(form)
        self.edits["ma_sp"].editingFinished.connect(self.autofill)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Lưu dòng hàng")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def autofill(self):
        """Gõ mã hàng đã có trong danh mục thì tự điền tên, HS, đơn giá, định mức."""
        hit = self.lot.core.lot_lookup_code(self.lot.store, self.lot.customer, self.edits["ma_sp"].text())
        if hit:
            for k, v in hit.items():
                self.edits[k].setText(str(v))

    def values(self):
        return {k: e.text() for k, e in self.edits.items()}

    def save(self):
        try:
            self.lot.save_item(self.values(), self.idx)
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được dòng hàng", str(e))
            return
        self.accept()


class LookupDialog(QDialog):
    """Tra mặt hàng của khách để thêm dòng: gõ mã / tên / quy cách / gam, chọn, nhập số lượng, Enter để thêm. Thêm liên tiếp nhiều dòng không phải mở lại."""

    COLS = ["Mã hàng", "Tên hàng hóa & quy cách", "Đơn giá", "SL/kiện", "kg/chiếc"]

    def __init__(self, lot, parent=None):
        super().__init__(parent)
        self.lot, self.hits, self.added = lot, [], 0
        self.setWindowTitle("Tra mặt hàng để thêm dòng")
        self.resize(880, 560)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Gõ mã, tên hoặc quy cách, ví dụ: 467 250g   hoặc   38*5*315   hoặc   43,7g")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Tra mặt hàng")
        lay.addWidget(self.search)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        self.empty = QLabel("")
        self.empty.setObjectName("banner_info")
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số lượng:"))
        self.qty = QLineEdit()
        self.qty.setPlaceholderText("VD 1000")
        self.qty.setMaximumWidth(130)
        self.qty.setAccessibleName("Số lượng")
        row.addWidget(self.qty)
        row.addWidget(QLabel("Số PO:"))
        self.po = QComboBox()
        self.po.setEditable(True)
        pos = [x for x in dict.fromkeys(str(it.get("po") or "") for it in lot.items) if x] or [x for x in str(lot.form.get("po", "")).split(" + ") if x]
        self.po.addItems(pos)
        if pos:
            self.po.setCurrentText(pos[-1])
        self.po.setMinimumWidth(200)
        row.addWidget(self.po)
        row.addStretch(1)
        self.add_btn = QPushButton("➕  Thêm vào lô")
        self.add_btn.setDefault(True)
        self.add_btn.clicked.connect(self.add)
        close = QPushButton("Xong")
        close.setObjectName("sec")
        close.clicked.connect(self.accept)
        row.addWidget(self.add_btn)
        row.addWidget(close)
        lay.addLayout(row)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.run_search)
        self.search.textChanged.connect(lambda _t: self._timer.start())
        self.search.installEventFilter(self)  # mũi tên lên/xuống chọn dòng ngay trong ô tìm
        self.table.doubleClicked.connect(lambda _i: self.add())
        self.qty.returnPressed.connect(self.add)
        self.search.returnPressed.connect(lambda: self.qty.setFocus())  # Enter ở ô tìm: sang ô số lượng; Enter ở ô số lượng: thêm
        self.run_search()
        self.search.setFocus()

    def eventFilter(self, obj, ev):
        if obj is self.search and ev.type() == QEvent.KeyPress and ev.key() in (Qt.Key_Down, Qt.Key_Up) and self.table.rowCount():
            r = self.table.currentRow()
            r = (r + (1 if ev.key() == Qt.Key_Down else -1)) % self.table.rowCount() if r >= 0 else 0
            self.table.selectRow(r)
            return True
        return super().eventFilter(obj, ev)

    def run_search(self):
        q = self.search.text().strip()
        self.hits = self.lot.search_items(q)
        self.table.setRowCount(len(self.hits))
        for r, h in enumerate(self.hits):
            for c, v in enumerate((h["ma_sp"], h["ten_sp"], widgets.fmt_num(h["price"]), f"{float(h['div'] or 0):g}", f"{float(h['kg'] or 0):g}")):
                cell = QTableWidgetItem(str(v))
                if c >= 2:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, cell)
        if self.hits:
            self.table.selectRow(0)
            self.empty.setText(f"{len(self.hits)} mặt hàng khớp" + (f" “{q}”." if q else " (gõ để lọc)."))
        else:
            self.empty.setText(f"Không thấy mặt hàng nào khớp “{q}”. Thử bớt từ khóa, hoặc gõ quy cách như 38*5*467. Mặt hàng mới thì đóng hộp này và bấm “Thêm dòng trống”.")

    def add(self):
        r = self.table.currentRow()
        if not (0 <= r < len(self.hits)):
            self.say("⚠ Chọn một mặt hàng trong bảng trước.", False)
            return
        try:
            qty = float(self.qty.text().replace(",", "").strip() or 0)
        except ValueError:
            qty = 0
        if qty <= 0:
            self.say("⚠ Nhập số lượng lớn hơn 0 rồi bấm Thêm (hoặc Enter).", False)
            self.qty.setFocus()
            return
        try:
            self.lot.add_from_catalog(self.hits[r], qty, self.po.currentText().strip())
        except ValueError as e:
            self.say(f"⚠ {e}", False)
            return
        self.added += 1
        self.say(f"✅ Đã thêm: {self.hits[r]['ten_sp']} × {qty:g}  (lô có {len(self.lot.items)} dòng). Tra tiếp mặt hàng khác hoặc bấm Xong.", True)
        self.qty.clear()
        self.search.selectAll()
        self.search.setFocus()

    def say(self, text, ok):
        self.msg.setText(text)
        self.msg.setStyleSheet(f"color: {'#03543F' if ok else '#9B1C1C'}; font-weight: 600;")

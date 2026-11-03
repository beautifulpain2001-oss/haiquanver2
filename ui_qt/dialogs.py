"""Hộp thoại thêm / sửa một dòng hàng."""

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QGridLayout, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
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


class LearnCustomerDialog(QDialog):
    """Thêm khách mới từ chứng từ mẫu (hóa đơn/PXK XML, Invoice Excel, PO mẫu): máy đọc thông tin và mã hàng, bạn soát lại rồi mới lưu."""

    FIELDS = [("key", "Mã khách (không dấu)"), ("label", "Tên ngắn hiển thị"), ("name", "Tên công ty khách"), ("mst", "Mã số thuế"),
              ("addr", "Địa chỉ"), ("addrKho", "Địa chỉ kho nhận"), ("emails", "Email nhận hóa đơn"), ("unit", "Đơn vị tính mặc định"),
              ("driver", "Lái xe"), ("xe", "Biển xe"), ("symbol", "Ký hiệu PXK"), ("veViec", "Về việc (PXK)"), ("tare", "Bì / dòng hàng (kg)"),
              ("sample_po", "Số PO trong file mẫu"), ("po_pattern", "Mẫu nhận dạng số PO"), ("docSet", "Bộ mẫu (chuan / best)"),
              ("payDays", "Hạn thanh toán (ngày)"), ("nameCn", "Tên khách tiếng Trung"), ("deliveryPlace", "Điểm giao hàng"),
              ("buyerContact", "Người liên hệ bên mua"), ("sellerContact", "Người liên hệ bên bán")]
    COLS = [("code", "Mã hàng"), ("name", "Tên hàng"), ("unit", "ĐVT"), ("price", "Đơn giá"), ("div", "SL/kiện"), ("kg", "kg/chiếc"), ("hs", "Mã HS")]

    def __init__(self, core, store, paths, parent=None, draft=None):
        super().__init__(parent)
        self.core, self.store, self.key = core, store, None
        self.draft = draft or core.learn_customer_from_documents(list(paths))
        prof = self.draft["profile"]
        key = core.customer_key_from_name(prof.get("name", ""), set(core.PROFILES) | set(store.custom_profiles))
        self.setWindowTitle("Thêm khách mới từ chứng từ mẫu")
        self.resize(980, 760)
        lay = QVBoxLayout(self)
        head = QLabel(f"Đã đọc {len(paths)} file: {', '.join(__import__('os').path.basename(p) for p in paths)}. "
                      "Kiểm tra và sửa các ô bên dưới; chưa có gì được lưu cho đến khi bấm “Lưu khách hàng mới”.")
        head.setWordWrap(True)
        head.setObjectName("hint")
        lay.addWidget(head)
        if self.draft["errors"]:
            err = QLabel("⚠ " + "\n⚠ ".join(self.draft["errors"]))
            err.setObjectName("banner_warn")
            err.setWordWrap(True)
            lay.addWidget(err)
        doc_set = "best" if "BEST PACIFIC" in core.strip_accents_upper(prof.get("name", "")) else "chuan"
        init = {"key": key, "label": key.capitalize(), "name": prof.get("name", ""), "mst": prof.get("mst", ""), "addr": prof.get("addr", ""),
                "addrKho": prof.get("addrKho", ""), "emails": prof.get("emails", ""), "unit": prof.get("unit", "cái"), "driver": prof.get("driver", ""),
                "xe": prof.get("xe", ""), "symbol": prof.get("symbol", "6C26NAA"), "veViec": "xuất kho bán hàng cho",
                "tare": str(self.draft.get("tare") or "0.0"), "sample_po": self.draft.get("sample_po", ""),
                "po_pattern": core.infer_po_pattern(self.draft.get("sample_po", "")), "docSet": doc_set, "payDays": "60" if doc_set == "best" else "30",
                "nameCn": "", "deliveryPlace": core.short_place(prof.get("addr", "")), "buyerContact": "", "sellerContact": ""}
        grid = QGridLayout()
        self.edits = {}
        for i, (k, label) in enumerate(self.FIELDS):
            r, c = divmod(i, 2)
            grid.addWidget(QLabel(label + ":"), r, c * 2)
            e = QLineEdit(str(init.get(k, "")))
            self.edits[k] = e
            grid.addWidget(e, r, c * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        self.edits["sample_po"].textChanged.connect(lambda t: self.edits["po_pattern"].setText(core.infer_po_pattern(t)))
        self.items_label = QLabel("")
        self.items_label.setObjectName("h2")
        lay.addWidget(self.items_label)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels([c[1] for c in self.COLS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        dele = QPushButton("🗑  Xóa dòng đã chọn")
        dele.setObjectName("dng")
        dele.clicked.connect(self.delete_rows)
        test = QPushButton("🔍  Thử đọc PO mẫu")
        test.setObjectName("sec")
        test.clicked.connect(self.try_po)
        self.test_msg = QLabel("")
        self.test_msg.setWordWrap(True)
        row.addWidget(dele)
        row.addWidget(test)
        row.addWidget(self.test_msg, 1)
        save = QPushButton("💾  Lưu khách hàng mới")
        save.clicked.connect(self.save)
        cancel = QPushButton("Hủy")
        cancel.setObjectName("sec")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        self.refresh_items()

    def refresh_items(self):
        items = self.draft["items"]
        self.items_label.setText(f"Mã hàng / định mức học được ({len(items)} dòng) — chọn dòng sai rồi bấm Xóa")
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            for c, (k, _) in enumerate(self.COLS):
                self.table.setItem(r, c, QTableWidgetItem(str(it.get(k, "") if it.get(k) is not None else "")))

    def delete_rows(self):
        for idx in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.draft["items"].pop(idx)
        self.refresh_items()

    def collect(self):
        out = {k: e.text().strip() for k, e in self.edits.items() if k not in ("key", "sample_po")}
        try:
            out["tare"] = float(out.get("tare") or 0.0)
        except ValueError:
            out["tare"] = 0.0
        try:
            out["payDays"] = int(float(out.get("payDays") or 0)) or ""
        except ValueError:
            out["payDays"] = ""
        if out.get("docSet") == "best" and not out["tare"]:
            out["tare"] = self.core.BEST_DOCSET_DEFAULTS["tare"]
        return out

    def try_po(self):
        if not self.draft["po_text"]:
            self.test_msg.setText("Chưa nạp PO mẫu (PDF/Excel/ảnh/txt) nên chưa thử đọc được.")
            return
        prof = self.core.build_custom_profile("tmp", self.collect())
        po_no, _, lines = self.core.parse_generic_po_text(self.draft["po_text"], prof, self.draft["items"])
        self.test_msg.setText(f"Thử đọc PO mẫu: số PO = {po_no or '(không thấy)'}, {len(lines)} dòng hàng khớp.")

    def save(self):
        try:
            self.key = self.store.save_learned_customer(self.edits["key"].text(), self.collect(), self.draft["items"])
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được", str(e))
            return
        self.accept()

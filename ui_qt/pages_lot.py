"""Trang "Làm chứng từ": 5 bước ① Chọn khách hàng → ② Nạp file PO → ③ Kiểm tra dòng hàng → ④ Thông tin chuyến hàng → ⑤ Xuất & lưu."""

import html

from PySide6.QtCore import Qt, QTimer, Signal
from shiboken6 import isValid
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import theme, widgets
from .dialogs import ItemDialog, LookupDialog, PickNumbersDialog
from .po_viewer import PoViewer
from .state import Lot

STEPS = ["① Chọn khách hàng", "② Nạp file PO", "③ Kiểm tra dòng hàng", "④ Thông tin chuyến & xuất hồ sơ"]
def _label(text, name=None, wrap=False):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def _inner(layout_cls=QVBoxLayout, margins=(28, 24, 28, 24), spacing=12):
    w = QWidget()
    w.setObjectName("inner")
    lay = layout_cls(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return w, lay


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


# --------------------------------------------------------------------------- ① chọn khách
KIND = {"shirai": "PO dạng Excel", "kodi": "PO dạng PDF hoặc ảnh scan", "tesa": "PO PDF nhiều trang"}


class CustomerStep(QWidget):
    changed = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.lot = lot
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)
        lay.addWidget(_label("Làm chứng từ cho khách hàng nào?", "h2"))
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        lay.addLayout(self.grid)
        self.cards = {}
        self.build_cards()
        self.info = QFrame()
        self.info.setObjectName("textcard")
        il = QVBoxLayout(self.info)
        il.setContentsMargins(16, 12, 16, 12)
        il.addWidget(_label("Thông tin khách hàng", "h2"))
        self.info_text = QLabel()
        self.info_text.setWordWrap(True)
        self.info_text.setTextFormat(Qt.RichText)
        il.addWidget(self.info_text)
        il.addWidget(_label("Cần sửa tên, mã số thuế, địa chỉ: vào mục “Khách hàng” ở thanh bên trái.", "hint", wrap=True))
        lay.addWidget(self.info)
        lay.addStretch(1)
        self.refresh()

    @property
    def customer(self):
        return self.lot.customer

    def build_cards(self):
        for b in self.cards.values():
            self.grid.removeWidget(b)
            b.deleteLater()
        self.cards = {}
        for i, (key, prof) in enumerate(self.lot.core.PROFILES.items()):
            owner = self.lot.store.customer_owner(key)
            b = QPushButton(f"{prof.get('label') or key}\n{KIND.get(key, 'Khách đã học')}" + (f" · {owner} phụ trách" if owner else ""))
            b.setObjectName("cust")
            b.setCheckable(True)
            b.setMinimumHeight(64)
            b.clicked.connect(lambda _=False, k=key: self.pick(k))
            self.cards[key] = b
            self.grid.addWidget(b, i // 3, i % 3)

    def refresh(self):
        profiles = self.lot.core.PROFILES
        if set(self.cards) != set(profiles) or any(not b.text().startswith(str(profiles[k].get("label") or k)) for k, b in self.cards.items()):
            self.build_cards()  # khách mới thêm hoặc đổi tên gọi ở mục Khách hàng
        c = self.lot.customer
        for k, b in self.cards.items():
            b.setChecked(k == c)
        self.info.setVisible(bool(c))
        if c:
            p = profiles[c]
            rows = [("Tên công ty", p.get("name")), ("Mã số thuế", p.get("mst")), ("Địa chỉ", p.get("addr")),
                    ("Kho nhận hàng", p.get("addrKho")), ("Lái xe", p.get("driver")), ("Biển số xe", p.get("xe"))]
            self.info_text.setText("".join(f'<p style="margin:2px 0"><b>{html.escape(k)}:</b> {html.escape(str(v or "(chưa nhập)"))}</p>' for k, v in rows))

    def pick(self, key):
        if key != self.lot.customer and self.lot.items and not widgets.ask(
                self, "Đổi khách hàng", "Đổi khách sẽ bỏ các dòng hàng đang làm. Bạn có chắc không?"):
            self.refresh()
            return
        other = self.lot.store.foreign_owner(key)
        if other and key != self.lot.customer and not widgets.ask(
                self, "Khách do người khác phụ trách", f"Khách này do {other} phụ trách. Bạn vẫn muốn làm chứng từ cho khách này?"):
            self.refresh()
            return
        self.lot.select_customer(key)
        self.refresh()
        self.changed.emit()


# --------------------------------------------------------------------------- ② nạp PO
PO_FILTER = "File PO (*.pdf *.xlsx *.xls *.png *.jpg *.jpeg *.tif *.tiff *.txt)"


class PoStep(QWidget):
    changed = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.setAcceptDrops(True)
        self.lot = lot
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)
        self.who = _label("", "h2", wrap=True)
        lay.addWidget(self.who)
        lay.addWidget(_label("Chọn file PO của khách", "h2"))
        row = QHBoxLayout()
        self.drop = QPushButton("📂  Bấm để chọn file PO (hoặc kéo thả file vào đây)")
        self.drop.setObjectName("drop")
        self.drop.clicked.connect(lambda: self.choose_file(False))
        row.addWidget(self.drop, 1)
        self.add_po = QPushButton("➕  Thêm PO khác vào lô này")
        self.add_po.setObjectName("sec")
        self.add_po.clicked.connect(lambda: self.choose_file(True))
        row.addWidget(self.add_po)
        lay.addLayout(row)
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedHeight(10)
        self.busy.hide()
        lay.addWidget(self.busy)
        self.status = _label("", "hint", wrap=True)
        lay.addWidget(self.status)
        self.dates_box = QGroupBox("Chọn ngày giao để làm invoice và khai hải quan")
        dl = QVBoxLayout(self.dates_box)
        dl.addWidget(_label("Tích cả các ngày = một invoice, một tờ khai cho cả PO. Chỉ tích một ngày = invoice và tờ khai riêng cho ngày đó; "
                            "ngày còn lại làm sau bằng cách nạp lại PO và chọn ngày đó.", "hint", wrap=True))
        self.dates_row = QHBoxLayout()
        dl.addLayout(self.dates_row)
        self.date_checks = {}
        lay.addWidget(self.dates_box)
        lay.addWidget(_label("Không có file PO? Bấm “Tiếp tục” rồi thêm dòng hàng bằng tay ở bước ③.", "hint", wrap=True))
        lay.addStretch(1)
        self.refresh()

    def refresh(self):
        c = self.lot.customer
        self.who.setText(f"Khách hàng: {self.lot.profile.get('label') or c} — {self.lot.profile.get('name', '')}" if c else "Chưa chọn khách hàng. Bấm “Quay lại” để chọn.")
        self.drop.setEnabled(bool(c) and not self.busy.isVisible())
        self.add_po.setVisible(self.lot.multi_po)
        self.refresh_dates()
        if not self.status.text() and c:
            n = len(self.lot.items)
            self.set_status(f"Lô đang có {n} dòng hàng." if n else "Chọn file PO để phần mềm tự đọc các dòng hàng.", ok=None)

    def choose_file(self, append):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file PO", "", PO_FILTER)
        if path:
            self.load_file(path, append)

    def load_file(self, path, append=False):
        if not self.lot.customer:
            widgets.warn(self, "Chưa chọn khách", "Hãy chọn khách hàng ở bước ① trước khi nạp file PO.")
            return
        self.busy.show()
        self.drop.setEnabled(False)
        self.add_po.setEnabled(False)
        self.set_status("Đang đọc PO… file scan có thể mất vài chục giây, vui lòng chờ.", ok=None)
        self.busy.setRange(0, 0)  # chưa biết tiến độ: thanh chạy; khi có số trang/dòng thì chuyển sang phần trăm
        widgets.run_job(self, lambda report: self.lot.read_po(path, append, report), self.on_loaded, self.on_failed, self.on_progress)

    def on_progress(self, text, frac):
        if self.busy.maximum() == 0:
            self.busy.setRange(0, 100)
        self.busy.setValue(int(max(0.0, min(1.0, frac)) * 100))
        self.set_status(f"{text}  ({int(frac * 100)}%)", ok=None)

    def _idle(self):
        self.busy.hide()
        self.drop.setEnabled(bool(self.lot.customer))
        self.add_po.setEnabled(True)

    def on_loaded(self, res):
        self._idle()
        if self.lot.apply_po(res):
            self.set_status(res["msg"] + " Bấm “Tiếp tục” để kiểm tra các dòng hàng.", ok=True)
        else:
            self.set_status(res["msg"] or "Không đọc được file PO.", ok=False)
        self.refresh()
        self.changed.emit()

    def on_failed(self, msg):
        self._idle()
        self.set_status(f"Không đọc được file: {msg}", ok=False)

    def set_status(self, text, ok):
        color = {True: theme.OK, False: theme.WARN, None: theme.MUTED}[ok]
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(text)

    def refresh_dates(self):
        """Dựng các ô tích ngày giao (chỉ khi PO có nhiều ngày giao)."""
        sched = self.lot.schedules or {}
        self.dates_box.setVisible(len(sched) > 1)
        if list(self.date_checks) == list(sched) and all(self.date_checks[k].isChecked() == (k in self.lot.selected_dates) for k in sched):
            return
        for cb in self.date_checks.values():
            self.dates_row.removeWidget(cb)
            cb.deleteLater()
        self.date_checks = {}
        for k, v in sched.items():
            cb = QCheckBox(f"{k}  ({len(v['items'])} dòng)")
            cb.setChecked(k in self.lot.selected_dates)
            cb.toggled.connect(lambda _on, key=k: self.on_date_toggled())
            self.date_checks[k] = cb
            self.dates_row.addWidget(cb)
        self.dates_row.addStretch(1)

    def on_date_toggled(self):
        keys = [k for k, cb in self.date_checks.items() if cb.isChecked()]
        try:
            self.lot.set_dates(keys)
        except ValueError as e:
            widgets.warn(self, "Chọn ngày giao", str(e))
            self.refresh_dates()  # khôi phục các ô tích theo lô đang làm
            return
        n = len(self.lot.items)
        self.set_status(f"Invoice này gồm {n} dòng của ngày giao: {', '.join(self.lot.selected_dates)}.", ok=True)
        self.changed.emit()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.load_file(urls[0], append=False)


# --------------------------------------------------------------------------- ② dòng hàng
COLS = ["STT", "Đọc PO", "Số PO", "Mã hàng", "Tên hàng hóa & quy cách", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "SL/kiện",
        "kg/chiếc", "Số kiện", "KL tịnh", "KL cả bì", "Lưu ý"]
C_STT, C_READ, C_PO, C_CODE, C_NAME, C_UNIT, C_QTY, C_NOTE = 0, 1, 2, 3, 4, 5, 6, 14
STATUS_BG = {"bad": "#FDE8E8", "check": "#FDF6B2", "hand": "#E1EFFE"}
STATUS_FG = {"ok": "#03543F", "check": "#92400E", "bad": "#9B1C1C", "hand": "#1E429F"}


class ItemsStep(QWidget):
    changed = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.lot = lot
        self.filter = "all"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        # Kết quả đọc PO: một câu rõ ràng ngay đầu bước, màu + biểu tượng + chữ (không chỉ dựa vào màu)
        self.banner = QLabel("")
        self.banner.setWordWrap(True)
        self.banner.hide()
        lay.addWidget(self.banner)
        bar = QHBoxLayout()
        self.lookup_btn = QPushButton("🔎  Tra mã để thêm dòng")
        self.lookup_btn.setToolTip("Gõ mã, tên hoặc quy cách (VD 467 250g) rồi chọn mặt hàng và nhập số lượng. Ctrl+F")
        self.lookup_btn.clicked.connect(self.lookup)
        bar.addWidget(self.lookup_btn)
        for text, fn in (("➕  Thêm dòng trống", self.add), ("✏  Sửa dòng", self.edit), ("🎯  Chọn số đúng từ PO", self.pick), ("🗑  Xóa dòng", self.delete), ("🔄  Tính lại bì", self.recalc)):
            b = QPushButton(text)
            b.setObjectName("dng" if "Xóa" in text else "sec")  # nút xóa màu đỏ để khỏi bấm nhầm
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        self.view_btn = QPushButton("📄  Xem PO")
        self.view_btn.setObjectName("sec")
        self.view_btn.setToolTip("Mở khung xem file PO cạnh bảng để so số liệu. Chọn dòng thì nhảy tới đúng trang.")
        self.view_btn.clicked.connect(self.toggle_viewer)
        self.next_btn = QPushButton("⏭  Dòng cần xem tiếp")
        self.next_btn.setObjectName("sec")
        self.next_btn.setToolTip("Nhảy tới dòng chưa đọc được / phải suy ra. F3")
        self.next_btn.clicked.connect(self.goto_next)
        lay.addLayout(bar)
        # lọc nhanh theo trạng thái đọc
        self.chips = QHBoxLayout()
        self.chip_btns = {}
        for key, text in (("all", "Tất cả"), ("bad", "❌ Chưa đọc được"), ("check", "🟡 Cần kiểm tra"), ("ok", "✅ Đọc đủ")):
            b = QPushButton(text)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.set_filter(k))
            self.chips.addWidget(b)
            self.chip_btns[key] = b
        self.chips.addStretch(1)
        self.chips.addWidget(self.next_btn)
        self.chips.addWidget(self.view_btn)
        self.chip_wrap = QWidget()
        self.chip_wrap.setLayout(self.chips)
        self.chips.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.chip_wrap)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(C_NAME, QHeaderView.Interactive)
        self.table.setColumnWidth(C_NAME, 260)
        hh.setStretchLastSection(True)
        self.table.setColumnHidden(C_STT, True)  # STT: không cần để soát số liệu
        self.table.doubleClicked.connect(lambda _i: self.edit())
        self.viewer = PoViewer(lot.core)
        self.viewer.closed.connect(self.hide_viewer)
        self.viewer.hide()
        self.viewer_closed_by_user = False
        self.split = QSplitter(Qt.Horizontal)
        self.split.addWidget(self.table)
        self.split.addWidget(self.viewer)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        self.split.setChildrenCollapsible(False)
        lay.addWidget(self.split, 1)
        self.table.itemSelectionChanged.connect(self.follow_selection)
        self.empty = _label("Chưa có dòng hàng. Quay lại bước ② để nạp file PO, hoặc bấm “Tra mã để thêm dòng”.", "hint", wrap=True)
        lay.addWidget(self.empty)
        self.summary = _label("", "h2")
        lay.addWidget(self.summary)
        for key, fn in (("F3", self.goto_next), ("Ctrl+F", self.lookup)):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

    # ---- khung xem PO -----------------------------------------------------------
    def po_file_of(self, idx):
        it = self.lot.items[idx] if idx is not None and 0 <= idx < len(self.lot.items) else {}
        path = it.get("po_file") or (self.lot.po_files[-1] if self.lot.po_files else "")
        return path, max(0, int(it.get("page") or 1) - 1), it.get("box") or self.estimate_box(idx, path)

    def estimate_box(self, idx, path):
        """Dòng chưa có vị trí trên PO (lô đọc từ bản cũ hoặc mở lại từ hồ sơ đã lưu): đo lại đường kẻ của trang đó rồi lấy theo thứ tự dòng."""
        if idx is None or not path or not path.lower().endswith(".pdf") or not self.lot.core.po_scan:
            return None
        items = self.lot.items
        page = items[idx].get("page")
        if not page or items[idx].get("read") is None:
            return None
        same = [i for i, x in enumerate(items) if x.get("page") == page and (x.get("po_file") or path) == path]
        if idx not in same:
            return None
        key = (path, page)
        cache = self.__dict__.setdefault("_box_cache", {})
        if key not in cache:
            try:
                cache[key] = self.lot.core.po_scan.page_row_boxes(self.lot.core, path, page - 1)
            except Exception:  # noqa: BLE001 - không đo được thì thôi, vẫn xem được trang
                cache[key] = []
        boxes = cache[key]
        k = same.index(idx)
        return boxes[k] if k < len(boxes) else None

    def toggle_viewer(self):
        if not self.viewer.isHidden():
            self.hide_viewer()
        else:
            self.viewer_closed_by_user = False
            self.show_viewer()

    def refresh_labels(self):
        """Đổi nhãn trạng thái giữa dạng đầy đủ và dạng biểu tượng khi bật/tắt khung xem PO (giữ nguyên dòng đang chọn)."""
        sel = self.selected()
        self.refresh()
        if sel is not None and sel < self.table.rowCount():
            self.table.selectRow(sel)

    def layout_columns(self):
        """Mở khung xem PO thì bớt các cột định mức/trọng lượng để bảng vẫn thấy đủ mã, tên, SL, giá, thành tiền và Lưu ý."""
        compact = not self.viewer.isHidden()
        for c in list(range(9, 14)) + [C_CODE]:
            self.table.setColumnHidden(c, compact)
        self.table.setColumnWidth(C_NAME, 200 if compact else 260)

    def show_viewer(self):
        self.viewer.show()
        self.layout_columns()
        self.refresh_labels()
        self.split.setSizes([max(520, self.width() * 58 // 100), max(360, self.width() * 42 // 100)])
        path, page, box = self.po_file_of(self.selected() if self.selected() is not None else (self.lot.attention_rows() or [0])[0])
        self.viewer.show_page(path, page, box)
        self.view_btn.setText(" Ẩn khung xem PO")

    def hide_viewer(self):
        self.viewer_closed_by_user = True
        self.viewer.hide()
        self.layout_columns()
        self.refresh_labels()
        self.view_btn.setText(" Xem PO")

    def follow_selection(self):
        if not self.viewer.isHidden() and self.selected() is not None:
            path, page, box = self.po_file_of(self.selected())
            if path != self.viewer.file or page != self.viewer.page or box != self.viewer.box:
                self.viewer.show_page(path, page, box)

    def set_filter(self, key):
        self.filter = key
        self.apply_filter()

    def apply_filter(self):
        for k, b in self.chip_btns.items():
            b.setChecked(k == self.filter)
        for r, it in enumerate(self.lot.items):
            code = self.lot.row_status(it)[0]
            self.table.setRowHidden(r, not (self.filter == "all" or code == self.filter or (self.filter == "check" and code == "hand" and False)))

    def refresh(self):
        lot, core = self.lot, self.lot.core
        lot.normalize()
        self.table.setRowCount(len(lot.items))
        warn_rows = 0
        for r, it in enumerate(lot.items):
            issues = lot.row_issues(it)
            code, label, note = lot.row_status(it)
            if code in ("bad", "check", "hand") and code != "hand":
                issues = ([note] if note else []) + [x for x in issues if code != "bad"]
            warn_rows += bool(issues) or code in ("bad", "check")
            if not self.viewer.isHidden() and label:
                label = label.split(" ")[0]  # khung xem PO đang mở: chỉ hiện biểu tượng trạng thái cho bảng gọn
            vals = [it.get("stt"), label, it.get("po", ""), it.get("ma_sp", ""), it.get("ten_sp", ""), it.get("unit", ""),
                    widgets.fmt_num(it.get("qty")), widgets.fmt_num(it.get("price")), widgets.fmt_num(it.get("amount")),
                    f"{float(it.get('div') or 0):g}", f"{float(it.get('kg') or 0):g}", f"{float(it.get('kien') or 0):g}",
                    widgets.fmt_num(it.get("net"), 2), widgets.fmt_num(it.get("gross"), 2), "; ".join(issues)]
            for c, v in enumerate(vals):
                cell = QTableWidgetItem("" if v is None else str(v))
                if 6 <= c <= 13:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if code in STATUS_BG:
                    cell.setBackground(QColor(STATUS_BG[code]))
                elif issues:
                    cell.setBackground(QColor("#FEF3C7"))
                if c == C_READ and code:
                    cell.setForeground(QColor(STATUS_FG[code]))
                    f = cell.font()
                    f.setBold(True)
                    cell.setFont(f)
                    cell.setToolTip(core.READ_LABELS.get(it.get("read"), "") + (f": {note}" if note else ""))
                if c == C_NOTE and issues:
                    cell.setToolTip("; ".join(issues))
                self.table.setItem(r, c, cell)
        # Cột Số PO chỉ cần khi lô có nhiều PO; ĐVT ít khi cần soát; cột "Đọc PO" chỉ khi PO được đọc có kiểm tra từng dòng
        self.table.setColumnHidden(C_PO, len({str(x.get("po") or "") for x in lot.items}) <= 1)
        self.table.setColumnHidden(C_UNIT, True)
        has_read = lot.has_read_info()
        self.table.setColumnHidden(C_READ, not has_read)
        self.chip_wrap.setVisible(has_read or bool(self.po_file_of(None)[0]))
        if has_read:
            n = lot.read_counts()
            self.chip_btns["bad"].setText(f"❌ Chưa đọc được ({n['bad']})")
            self.chip_btns["check"].setText(f"🟡 Cần kiểm tra ({n['check']})")
            self.chip_btns["ok"].setText(f"✅ Đọc đủ ({n['ok'] + n['hand']})")
            self.chip_btns["all"].setText(f"Tất cả ({len(lot.items)})")
        else:
            self.filter = "all"
        for b in self.chip_btns.values():
            b.setVisible(has_read)
        self.next_btn.setVisible(has_read)
        self.next_btn.setEnabled(bool(lot.attention_rows()))
        self.apply_filter()
        self.show_banner()
        po_path = self.po_file_of(None)[0]
        self.view_btn.setVisible(bool(po_path))
        if has_read and lot.attention_rows() and not self.viewer_closed_by_user and self.viewer.can_view(po_path) and self.viewer.isHidden():
            self.show_viewer()  # có dòng cần soát: mở sẵn PO cạnh bảng
        self.layout_columns()
        self.empty.setVisible(not lot.items)
        if lot.items:
            t = core.lot_totals(lot.record())
            self.summary.setText(f"{len(lot.items)} dòng · SL {widgets.fmt_num(t['qty'])} · Thành tiền {widgets.fmt_num(t['amount'])} VNĐ · "
                                 f"Tịnh {widgets.fmt_num(t['net'], 2)} kg · Cả bì {widgets.fmt_num(t['gross'], 2)} kg"
                                 + (f"   ⚠ {warn_rows} dòng cần xem (có nền màu)" if warn_rows else "   ✅ Các dòng đều đủ thông tin"))
        else:
            self.summary.setText("")

    def show_banner(self):
        lot = self.lot
        if not lot.has_read_info():
            self.banner.hide()
            return
        n = lot.read_counts()
        rep = getattr(lot, "read_text", "") or ""
        if n["bad"]:
            bad = [str(i) for i, it in enumerate(lot.items, 1) if it.get("read") == "loi"]
            self.banner.setObjectName("banner_bad")
            self.banner.setText(f"❌  Chưa đọc được {n['bad']}/{len(lot.items)} dòng (dòng {', '.join(bad)}). Bấm đúp vào dòng tô đỏ để nhập tay, hoặc ⏭ để nhảy tới dòng đó.")
        elif n["check"]:
            chk = [str(i) for i, it in enumerate(lot.items, 1) if it.get("read") == "suy_ra"]
            self.banner.setObjectName("banner_warn")
            self.banner.setText(f"🟡  Đọc đủ {len(lot.items)} dòng nhưng dòng {', '.join(chk)} máy phải suy ra từ ô khác của PO: hãy so lại với PO." + (f"  {rep}" if rep else ""))
        else:
            self.banner.setObjectName("banner_ok")
            self.banner.setText(f"✅  Đã đọc đủ {len(lot.items)}/{len(lot.items)} dòng." + (f"  {rep}" if rep else ""))
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)
        self.banner.show()

    def goto_next(self):
        rows = self.lot.attention_rows()
        if not rows:
            return
        cur = self.selected()
        nxt = next((r for r in rows if cur is None or r > cur), rows[0])
        if self.table.isRowHidden(nxt):
            self.set_filter("all")
        self.table.selectRow(nxt)
        self.table.scrollToItem(self.table.item(nxt, C_NAME))
        self.table.setFocus()

    def lookup(self):
        dlg = LookupDialog(self.lot, self)
        dlg.exec()
        if dlg.added:
            self.refresh()
            self.changed.emit()

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def add(self):
        if ItemDialog(self.lot, None, self).exec():
            self.refresh()
            self.changed.emit()

    def edit(self):
        idx = self.selected()
        if idx is None:
            widgets.warn(self, "Sửa dòng hàng", "Hãy bấm chọn một dòng trên bảng trước.")
            return
        if ItemDialog(self.lot, idx, self).exec():
            self.refresh()
            self.changed.emit()

    def pick(self):
        idx = self.selected()
        if idx is None:
            widgets.warn(self, "Chọn số đúng từ PO", "Hãy bấm chọn dòng máy đọc sai trên bảng trước.")
            return
        if self.lot.pick_info(idx) is None:
            widgets.warn(self, "Chọn số đúng từ PO", "Dòng này không có dòng PO gốc đi kèm (thêm bằng tay hoặc PO đọc theo cách khác). Dùng “Sửa dòng” để gõ số đúng.")
            return
        dlg = PickNumbersDialog(self.lot, idx, self)
        if dlg.exec():
            self.refresh()
            self.changed.emit()
            widgets.info(self, "Đã lưu", dlg.message)

    def delete(self):
        idx = self.selected()
        if idx is None:
            widgets.warn(self, "Xóa dòng hàng", "Hãy bấm chọn một dòng trên bảng trước.")
            return
        self.lot.delete_item(idx)
        self.refresh()
        self.changed.emit()

    def recalc(self):
        self.lot.recalc()
        self.refresh()


# --------------------------------------------------------------------------- ③ thông tin chuyến hàng
class InfoStep(QWidget):
    changed = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.lot = lot
        self.edits = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 12, 16)
        lay.setSpacing(12)
        self.groups = {}
        spec = [
            ("doc", "Chứng từ", [("po", "Số PO"), ("po_date", "Ngày PO (dd/mm/yyyy)"), ("doc_date", "Ngày chứng từ (yyyy-mm-dd)"),
                                 ("pxk", "Số PXK (phiếu xuất kho)"), ("hd", "Số hóa đơn VAT"), ("tk", "Số tờ khai hải quan")]),
            ("ship", "Vận chuyển", [("xe", "Biển số xe"), ("driver", "Họ tên lái xe"), ("ldd", "Số lệnh điều động"), ("tare", "Bì cộng thêm mỗi dòng (kg, vd 0.02; hoặc % như 0.08%)")]),
            ("pay", "Thanh toán và giao hàng", [("pay_days", "Hạn thanh toán (số ngày)"), ("delivery", "Ngày giao phiếu giao hàng (yyyy-mm-dd, để trống = ngày chứng từ + 1)")]),
        ]
        for gkey, title, fields in spec:
            box = QGroupBox(title)
            form = QFormLayout(box)
            form.setLabelAlignment(Qt.AlignLeft)
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setVerticalSpacing(10)
            form.setContentsMargins(14, 18, 14, 12)
            for key, label in fields:
                e = QLineEdit()
                e.textEdited.connect(lambda text, k=key: self.on_edit(k, text))
                self.edits[key] = e
                form.addRow(label, e)
            self.groups[gkey] = box
            lay.addWidget(box)
        self.edits["tare"].editingFinished.connect(self.lot.recalc)
        self.skip_h = QCheckBox("Invoice Kodi: không lấy cột Thành Tiền")
        self.skip_h.toggled.connect(lambda v: setattr(self.lot, "skip_h", v))
        lay.addWidget(self.skip_h)
        lay.addStretch(1)

    def on_edit(self, key, text):
        if key == "pxk":
            self.lot.pxk_touched, self.lot.pxk_auto = True, False
        self.lot.form[key] = text
        self.lot.saved = False
        self.mark_missing()
        self.changed.emit()

    def mark_missing(self):
        """Ô số PXK / hóa đơn còn trống: viền cam và gợi ý ngay tại ô (không đợi tới lúc xuất mới báo)."""
        need = {"pxk": "Chưa có số PXK: Invoice sẽ dùng số tạm", "hd": "Chưa có số hóa đơn VAT"}
        for k, hint in need.items():
            e = self.edits[k]
            empty = not str(self.lot.form.get(k, "")).strip() and (k == "pxk" or self.lot.is_best)
            e.setProperty("warn", bool(empty))
            e.setPlaceholderText(hint if empty else "")
            if k == "pxk":
                e.setToolTip("Tự điền = số phiếu xuất kho lớn nhất đã có + 1. Sửa lại nếu khác." if self.lot.pxk_auto else "")
            e.style().unpolish(e)
            e.style().polish(e)

    def refresh(self):
        self.lot.fill_vehicle_defaults()
        self.lot.fill_next_pxk()
        for k, e in self.edits.items():
            e.setText(str(self.lot.form.get(k, "")))
        self.groups["pay"].setVisible(self.lot.is_best)
        self.skip_h.setVisible(self.lot.customer == "kodi")
        self.skip_h.setChecked(self.lot.skip_h)
        self.mark_missing()


# --------------------------------------------------------------------------- ④ xuất & lưu
EXPORTS = [("VAT", "Hóa đơn VAT (Bkav)"), ("PKL", "Invoice / Packing List"), ("PXK", "Phiếu xuất kho (Bkav)"),
           ("DNTT", "Đề nghị thanh toán"), ("PLX", "Phụ lục X"), ("BBGH", "Biên bản bàn giao"), ("BEST", "Mẫu riêng của Best"), ("DSH", "Danh sách hàng ECUS (dsh)")]


def _lines_html(lines):
    """Mỗi mục một đoạn, tự xuống dòng khi dài; không cắt chữ."""
    return "".join(f'<p style="margin:3px 0">{html.escape(t)}</p>' for t in lines)


def _text_card(parent_layout):
    """Khung trắng chứa văn bản nhiều dòng, cao theo nội dung (không thanh cuộn riêng)."""
    card = QFrame()
    card.setObjectName("textcard")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 8, 12, 8)
    lb = QLabel()
    lb.setTextFormat(Qt.RichText)
    lb.setWordWrap(True)
    lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(lb)
    parent_layout.addWidget(card)
    return lb


class ExportStep(QWidget):
    saved = Signal()
    new_lot = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.lot = lot
        self.check_lines, self.done_lines = [], []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)  # cả trang cuộn được khi có nhiều cảnh báo
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # chữ tự xuống dòng nên không cần cuộn ngang
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setObjectName("inner")
        scroll.setWidget(content)
        outer.addWidget(scroll)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 16, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(_label("Kiểm tra trước khi xuất", "h2"))
        self.checks = _text_card(lay)
        self.big = QPushButton("📦  Xuất trọn bộ chứng từ")
        self.big.setToolTip("Mỗi chứng từ một file Excel riêng, cùng thư mục hồ sơ")
        self.big.setObjectName("big")
        self.big.clicked.connect(lambda: self.do_export("ALL"))
        lay.addWidget(self.big)
        self.one = QGroupBox("Hoặc chỉ xuất một file")
        g = QGridLayout(self.one)
        self.btns = {}
        for i, (mode, text) in enumerate(EXPORTS):
            b = QPushButton(text)
            b.setObjectName("sec")
            b.clicked.connect(lambda _=False, m=mode: self.do_export(m))
            self.btns[mode] = b
            g.addWidget(b, i // 2, i % 2)
        lay.addWidget(self.one)
        lay.addWidget(_label("File đã xuất", "h2"))
        self.done = _text_card(lay)
        row = QHBoxLayout()
        self.open_btn = QPushButton("📁  Mở thư mục chứa file")
        self.open_btn.setObjectName("sec")
        self.open_btn.clicked.connect(self.open_dir)
        self.save_btn = QPushButton("💾  Lưu hồ sơ")
        self.save_btn.clicked.connect(self.do_save)
        self.new_btn = QPushButton("🆕  Làm lô mới")
        self.new_btn.setObjectName("sec")
        self.new_btn.clicked.connect(self.on_new)
        for b in (self.open_btn, self.save_btn, self.new_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.msg = _label("", "hint", wrap=True)
        lay.addWidget(self.msg)
        lay.addStretch(1)

    def refresh(self, keep_msg=False):
        errors, warns = self.lot.validate()
        self.check_lines = ["❌  " + t for t in errors] + ["⚠  " + t for t in warns]
        if not errors and not warns:
            self.check_lines = ["✅  Mọi thứ khớp, sẵn sàng xuất."]
        self.checks.setText(_lines_html(self.check_lines))
        ok = not errors
        self.big.setEnabled(ok)
        self.one.setEnabled(ok)
        self.btns["BEST"].setVisible(self.lot.is_best)
        self.btns["PLX"].setVisible(self.lot.customer in ("tesa", "kodi", "shirai") or bool(self.lot.customer and self.lot.profile.get("customs")))
        self.save_btn.setEnabled(ok)
        self.open_btn.setEnabled(ok)
        self.done_lines = [f"✅  {f['label']}: {f['name']}  ({f['time']})" for f in self.lot.files] or ["Chưa xuất file nào."]
        self.done.setText(_lines_html(self.done_lines))
        if not keep_msg:
            self.msg.setText("Hồ sơ đã được lưu." if self.lot.saved else "")

    def do_export(self, mode):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = self.lot.export(mode)
        except ValueError as e:
            widgets.warn(self, "Chưa xuất được", str(e))
            return
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Lỗi khi xuất file", f"{e}\n\nChi tiết đã ghi vào LOI_PHAN_MEM.txt cạnh phần mềm.")
            raise
        finally:
            QApplication.restoreOverrideCursor()
        n = len(res["files"])
        extra = f" Kèm {res['dsh']}." if res["dsh"] else ""
        if mode == "ALL":
            extra += (" Kiểm tra chéo: đạt." if not res["problems"] else f" Kiểm tra chéo còn {len(res['problems'])} điểm cần xem (xem trong file KiemTraCheo).")
        self.refresh(keep_msg=True)
        self.msg.setText(f"Đã xuất {n} file vào thư mục hồ sơ.{extra}")
        self.show_result()

    def show_result(self):
        """Cuộn xuống để người dùng thấy ngay danh sách file đã xuất và thông báo (sau khi bố cục cập nhật)."""
        def down():
            if not isValid(self.scroll):  # cửa sổ có thể đã đóng trong lúc chờ
                return
            bar = self.scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        QTimer.singleShot(0, down)
        QTimer.singleShot(60, down)  # lần nữa sau khi bố cục tính xong chiều cao mới

    def open_dir(self):
        widgets.open_folder(self.lot.folder())

    def do_save(self):
        rec = self.lot.save()
        self.refresh(keep_msg=True)
        self.msg.setText(f"Đã lưu hồ sơ PO {rec['poNumber'] or '(chưa có số)'}. Xem lại ở mục “Hồ sơ đã lưu”.")
        self.show_result()
        self.saved.emit()

    def on_new(self):
        if self.lot.items and not self.lot.saved and not widgets.ask(self, "Làm lô mới", "Lô này chưa lưu hồ sơ. Bỏ lô này và làm lô mới?"):
            return
        self.new_lot.emit()


class FinishStep(QWidget):
    """Bước ④: thông tin chuyến hàng (trái) và xuất & lưu hồ sơ (phải) trên cùng một màn hình, gõ số xong thấy ngay kiểm tra."""

    def __init__(self, info, export):
        super().__init__()
        self.setObjectName("inner")
        self.info, self.export = info, export
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(info, 4)
        lay.addWidget(export, 6)
        info.changed.connect(lambda: export.refresh(keep_msg=True))

    def refresh(self):
        self.info.refresh()
        self.export.refresh()


# --------------------------------------------------------------------------- trang chứa 4 bước
class LotPage(QWidget):
    saved = Signal()

    def __init__(self, core, store):
        super().__init__()
        self.setObjectName("page")
        self.lot = Lot(core, store)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        self.bar = StepBar()
        lay.addWidget(self.bar)
        self.stack = QStackedWidget()
        card = QFrame()
        card.setObjectName("card")
        QVBoxLayout(card).addWidget(self.stack)
        lay.addWidget(card, 1)
        self.step1 = CustomerStep(self.lot)
        self.step2 = PoStep(self.lot)
        self.step3 = ItemsStep(self.lot)
        self.step4 = InfoStep(self.lot)
        self.step5 = ExportStep(self.lot)
        self.finish = FinishStep(self.step4, self.step5)
        self.steps = [self.step1, self.step2, self.step3, self.finish]
        for s in self.steps:
            self.stack.addWidget(s)
        self.step1.changed.connect(self.refresh_buttons)
        self.step2.changed.connect(self.refresh_buttons)
        self.step2.changed.connect(lambda: setattr(self.step3, "viewer_closed_by_user", False))  # PO mới: mở lại khung xem nếu có dòng cần soát
        self.step5.saved.connect(self.saved)
        self.step5.new_lot.connect(self.start_new)
        nav = QHBoxLayout()
        self.back = QPushButton("← Quay lại")
        self.back.setObjectName("sec")
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
        step = self.steps[idx]
        if hasattr(step, "refresh"):
            step.refresh()
        self.refresh_buttons()

    def refresh_buttons(self):
        idx = self.bar.current
        self.back.setEnabled(idx > 0)
        # Bước ① phải chọn khách rồi mới đi tiếp
        self.next.setEnabled(idx < len(STEPS) - 1 and (idx > 0 or self.lot.customer is not None))

    def start_new(self):
        self.lot.reset(None)
        self.go(0)

    def open_record(self, rec):
        """Nạp hồ sơ đã lưu để làm tiếp, mở ở bước ③ để soát lại dòng hàng."""
        self.lot.load_record(rec)
        self.go(2)

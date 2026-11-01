"""Trang "Làm chứng từ": 4 bước ① Chọn khách & nạp PO → ② Kiểm tra dòng hàng → ③ Thông tin chuyến hàng → ④ Xuất & lưu."""

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import theme, widgets
from .dialogs import ItemDialog
from .state import Lot

STEPS = ["① Chọn khách & nạp PO", "② Kiểm tra dòng hàng", "③ Thông tin chuyến hàng", "④ Xuất & lưu hồ sơ"]
PO_FILTER = "File PO (*.pdf *.xlsx *.xls *.png *.jpg *.jpeg *.tif *.tiff *.txt)"


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


# --------------------------------------------------------------------------- ① khách + PO
class CustomerStep(QWidget):
    changed = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.setAcceptDrops(True)
        self.lot = lot
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(12)
        lay.addWidget(_label("Khách hàng nào?", "h2"))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = {}
        core = lot.core
        for i, (key, prof) in enumerate(core.PROFILES.items()):
            kind = {"shirai": "PO dạng Excel", "kodi": "PO dạng PDF hoặc ảnh scan", "tesa": "PO PDF nhiều trang"}.get(key, "Khách đã học")
            b = QPushButton(f"{prof.get('label') or key}\n{kind}")
            b.setObjectName("cust")
            b.setCheckable(True)
            b.setMinimumHeight(64)
            b.clicked.connect(lambda _=False, k=key: self.pick(k))
            self.cards[key] = b
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)

        lay.addWidget(_label("File PO của khách", "h2"))
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
        self.busy.setFixedHeight(8)
        self.busy.hide()
        lay.addWidget(self.busy)
        self.status = _label("", "hint", wrap=True)
        lay.addWidget(self.status)

        sched = QHBoxLayout()
        self.sched_lbl = _label("Đợt giao hàng:")
        self.sched = QComboBox()
        self.sched.currentTextChanged.connect(self.on_schedule)
        sched.addWidget(self.sched_lbl)
        sched.addWidget(self.sched)
        sched.addStretch(1)
        lay.addLayout(sched)
        lay.addStretch(1)
        self.refresh()

    @property
    def customer(self):
        return self.lot.customer

    def refresh(self):
        c = self.lot.customer
        for k, b in self.cards.items():
            b.setChecked(k == c)
        self.drop.setEnabled(bool(c))
        self.add_po.setVisible(self.lot.multi_po)
        has = bool(self.lot.schedules)
        self.sched_lbl.setVisible(has)
        self.sched.setVisible(has)
        if has:
            self.sched.blockSignals(True)
            self.sched.clear()
            self.sched.addItems(list(self.lot.schedules))
            self.sched.setCurrentText(self.lot.schedule_key)
            self.sched.blockSignals(False)
        if not c:
            self.status.setText("Chọn khách hàng trước, rồi chọn file PO.")

    def pick(self, key):
        if key != self.lot.customer and self.lot.items and not widgets.ask(
                self, "Đổi khách hàng", "Đổi khách sẽ bỏ các dòng hàng đang làm. Bạn có chắc không?"):
            self.refresh()
            return
        self.lot.select_customer(key)
        self.set_status("", ok=None)
        self.refresh()
        self.changed.emit()

    def choose_file(self, append):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file PO", "", PO_FILTER)
        if path:
            self.load_file(path, append)

    def load_file(self, path, append=False):
        if not self.lot.customer:
            widgets.warn(self, "Chưa chọn khách", "Hãy chọn khách hàng trước khi nạp file PO.")
            return
        self.busy.show()
        self.drop.setEnabled(False)
        self.add_po.setEnabled(False)
        self.set_status("Đang đọc PO… file scan có thể mất vài chục giây, vui lòng chờ.", ok=None)
        widgets.run_job(self, lambda: self.lot.read_po(path, append), self.on_loaded, self.on_failed)

    def _idle(self):
        self.busy.hide()
        self.drop.setEnabled(bool(self.lot.customer))
        self.add_po.setEnabled(True)

    def on_loaded(self, res):
        self._idle()
        if self.lot.apply_po(res):
            self.set_status(res["msg"] + " Hãy kiểm tra lại ở bước ②.", ok=True)
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

    def on_schedule(self, key):
        self.lot.select_schedule(key)
        self.changed.emit()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.load_file(urls[0], append=False)


# --------------------------------------------------------------------------- ② dòng hàng
COLS = ["STT", "Số PO", "Mã hàng", "Tên hàng hóa & quy cách", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "SL/kiện",
        "kg/chiếc", "Số kiện", "KL tịnh", "KL cả bì", "Lưu ý"]


class ItemsStep(QWidget):
    changed = Signal()

    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.lot = lot
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        bar = QHBoxLayout()
        for text, fn in (("➕  Thêm dòng", self.add), ("✏  Sửa dòng", self.edit), ("🗑  Xóa dòng", self.delete), ("🔄  Tính lại bì / trọng lượng", self.recalc)):
            b = QPushButton(text)
            b.setObjectName("sec")
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 210)
        self.table.setColumnHidden(0, True)  # STT: không cần để soát số liệu
        self.table.doubleClicked.connect(lambda _i: self.edit())
        lay.addWidget(self.table, 1)
        self.empty = _label("Chưa có dòng hàng. Quay lại bước ① để nạp file PO, hoặc bấm “Thêm dòng”.", "hint", wrap=True)
        lay.addWidget(self.empty)
        self.summary = _label("", "h2")
        lay.addWidget(self.summary)

    def refresh(self):
        lot, core = self.lot, self.lot.core
        lot.normalize()
        self.table.setRowCount(len(lot.items))
        warn_rows = 0
        for r, it in enumerate(lot.items):
            issues = lot.row_issues(it)
            warn_rows += bool(issues)
            vals = [it.get("stt"), it.get("po", ""), it.get("ma_sp", ""), it.get("ten_sp", ""), it.get("unit", ""),
                    widgets.fmt_num(it.get("qty")), widgets.fmt_num(it.get("price")), widgets.fmt_num(it.get("amount")),
                    f"{float(it.get('div') or 0):g}", f"{float(it.get('kg') or 0):g}", f"{float(it.get('kien') or 0):g}",
                    widgets.fmt_num(it.get("net"), 2), widgets.fmt_num(it.get("gross"), 2), "; ".join(issues)]
            for c, v in enumerate(vals):
                cell = QTableWidgetItem("" if v is None else str(v))
                if c in (5, 6, 7, 8, 9, 10, 11, 12):
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if issues:
                    cell.setBackground(QColor("#FEF3C7"))
                self.table.setItem(r, c, cell)
        # Cột Số PO chỉ cần khi lô có nhiều PO; ĐVT ít khi cần soát: ẩn để bảng vừa màn hình
        self.table.setColumnHidden(1, len({str(x.get("po") or "") for x in lot.items}) <= 1)
        self.table.setColumnHidden(4, True)
        self.empty.setVisible(not lot.items)
        if lot.items:
            t = core.lot_totals(lot.record())
            self.summary.setText(f"{len(lot.items)} dòng · SL {widgets.fmt_num(t['qty'])} · Thành tiền {widgets.fmt_num(t['amount'])} VNĐ · "
                                 f"Tịnh {widgets.fmt_num(t['net'], 2)} kg · Cả bì {widgets.fmt_num(t['gross'], 2)} kg"
                                 + (f"   ⚠ {warn_rows} dòng cần xem (tô vàng)" if warn_rows else "   ✅ Các dòng đều đủ thông tin"))
        else:
            self.summary.setText("")

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
    def __init__(self, lot: Lot):
        super().__init__()
        self.setObjectName("inner")
        self.lot = lot
        self.edits = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(14)
        self.groups = {}
        spec = [
            ("doc", "Chứng từ", [("po", "Số PO"), ("po_date", "Ngày PO (dd/mm/yyyy)"), ("doc_date", "Ngày chứng từ (yyyy-mm-dd)"),
                                 ("pxk", "Số PXK (phiếu xuất kho)"), ("hd", "Số hóa đơn VAT"), ("tk", "Số tờ khai hải quan")]),
            ("ship", "Vận chuyển", [("xe", "Biển số xe"), ("driver", "Họ tên lái xe"), ("ldd", "Số lệnh điều động"), ("tare", "Bì cộng thêm mỗi dòng (kg)")]),
            ("pay", "Thanh toán và giao hàng", [("pay_days", "Hạn thanh toán (số ngày)"), ("delivery", "Ngày giao phiếu giao hàng (yyyy-mm-dd, để trống = ngày chứng từ + 1)")]),
        ]
        for gkey, title, fields in spec:
            box = QGroupBox(title)
            form = QFormLayout(box)
            form.setLabelAlignment(Qt.AlignLeft)
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
        self.lot.form[key] = text
        self.lot.saved = False

    def refresh(self):
        for k, e in self.edits.items():
            e.setText(str(self.lot.form.get(k, "")))
        self.groups["pay"].setVisible(self.lot.is_best)
        self.skip_h.setVisible(self.lot.customer == "kodi")
        self.skip_h.setChecked(self.lot.skip_h)


# --------------------------------------------------------------------------- ④ xuất & lưu
EXPORTS = [("VAT", "Hóa đơn VAT (Bkav)"), ("PKL", "Invoice / Packing List"), ("PXK", "Phiếu xuất kho (Bkav)"),
           ("DNTT", "Đề nghị thanh toán"), ("PLX", "Phụ lục X"), ("BEST", "Mẫu riêng của Best"), ("DSH", "Danh sách hàng ECUS (dsh)")]


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
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(10)
        lay.addWidget(_label("Kiểm tra trước khi xuất", "h2"))
        self.checks = _text_card(lay)
        self.big = QPushButton("📦  Xuất trọn bộ chứng từ (mỗi chứng từ một file)")
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
            g.addWidget(b, i // 3, i % 3)
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
        self.step2 = ItemsStep(self.lot)
        self.step3 = InfoStep(self.lot)
        self.step4 = ExportStep(self.lot)
        self.steps = [self.step1, self.step2, self.step3, self.step4]
        for s in self.steps:
            self.stack.addWidget(s)
        self.step1.changed.connect(self.refresh_buttons)
        self.step4.saved.connect(self.saved)
        self.step4.new_lot.connect(self.start_new)
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
        """Nạp hồ sơ đã lưu để làm tiếp, mở ở bước ② để soát lại dòng hàng."""
        self.lot.load_record(rec)
        self.go(1)

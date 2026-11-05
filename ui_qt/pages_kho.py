"""Kho mẫu chung: mẫu Word/Excel dùng lại giữa các khách (đặt tên <LOẠI>_<Khách>_<số>, VD PLX_Arizon_01). Có xem mẫu ngay trong phần mềm."""

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import widgets

LOAI_TEXT = {"PLX": "Phụ lục X", "BBGH": "Biên bản giao nhận", "PO": "Đơn đặt hàng", "BDC": "Bảng đối chiếu hàng hóa", "DNTT": "Đề nghị thanh toán",
             "DCCN": "Đối chiếu công nợ", "KHAC": "Khác"}


def loai_text(code):
    return LOAI_TEXT.get(code, code)


def ext_text(ext):
    return "Word" if ext == "docx" else "Excel"


class TemplatePreview(QWidget):
    """Xem một file mẫu: Word hiện chữ theo thứ tự trang (dòng bảng nối bằng ' | '), Excel hiện lưới trang đầu. Ô {{...}} được báo ở dòng chú thích."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.caption = QLabel("Chọn một mẫu để xem.")
        self.caption.setObjectName("hint")
        self.caption.setWordWrap(True)
        lay.addWidget(self.caption)
        self.stack = QStackedWidget()
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.grid = QTableWidget(0, 0)
        self.grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.stack.addWidget(self.text)
        self.stack.addWidget(self.grid)
        lay.addWidget(self.stack, 1)

    def show_template(self, core, ext, data, tokens=(), unknown=()):
        import mau_rieng
        try:
            pv = mau_rieng.preview(ext, data)
        except Exception as e:  # noqa: BLE001 - file mẫu hỏng: báo ngay trong khung xem
            self.caption.setText(f"Không xem được mẫu: {e}")
            return
        if pv["kind"] == "text":
            self.text.setPlainText(pv["text"])
            self.stack.setCurrentIndex(0)
        else:
            rows = pv["rows"]
            self.grid.setRowCount(len(rows))
            self.grid.setColumnCount(max((len(r) for r in rows), default=0))
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    self.grid.setItem(r, c, QTableWidgetItem(v))
            self.stack.setCurrentIndex(1)
        note = f"Ô thay thế nhận ra: {', '.join('{{' + t + '}}' for t in tokens) or 'không có'}."
        if unknown:
            note += f"  Ô lạ (sẽ để nguyên): {', '.join('{{' + u + '}}' for u in unknown)}."
        self.caption.setText(note)

    def clear(self):
        self.text.clear()
        self.grid.setRowCount(0)
        self.caption.setText("Chọn một mẫu để xem.")


def add_template_to_kho(parent, store, khach_label, path=None):
    """Hỏi loại chứng từ rồi nạp file mẫu vào kho. Trả tên mẫu trong kho hoặc None (hủy/lỗi)."""
    import kho_mau
    if not path:
        path, _ = QFileDialog.getOpenFileName(parent, "Chọn file Word/Excel mẫu", "", "Mẫu (*.docx *.xlsx)")
    if not path:
        return None
    names = [f"{code} — {text}" for code, text in kho_mau.LOAI.items()]
    pick, ok = QInputDialog.getItem(parent, "Loại chứng từ", "Mẫu này là chứng từ gì?", names, 0, False)
    if not ok:
        return None
    try:
        name, known, unknown = store.kho_add(path, pick.split(" — ")[0], khach_label)
    except ValueError as e:
        widgets.warn(parent, "Chưa nạp được mẫu", str(e))
        return None
    return name


class KhoPicker(QWidget):
    """Danh sách mẫu trong kho để chọn (tích chọn) kèm khung xem mẫu; dùng khi tạo khách mới (bước chọn chứng từ riêng)."""

    def __init__(self, core, store, khach_label=lambda: ""):
        super().__init__()
        self.core, self.store, self.khach_label = core, store, khach_label
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.list = QListWidget()
        self.list.setMaximumHeight(150)
        self.list.currentRowChanged.connect(self.on_row)
        top.addWidget(self.list, 1)
        self.preview = TemplatePreview()
        top.addWidget(self.preview, 2)
        lay.addLayout(top)
        row = QHBoxLayout()
        self.add_btn = QPushButton("📎  Nạp file mẫu Word/Excel mới…")
        self.add_btn.setObjectName("sec")
        self.add_btn.clicked.connect(self.add_new)
        row.addWidget(self.add_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.items = []
        self.refresh()

    def refresh(self, check=()):
        checked = set(check) | set(self.selected())
        self.items = self.store.kho_list()
        self.list.blockSignals(True)
        self.list.clear()
        for it in self.items:
            li = QListWidgetItem(f"{os.path.splitext(it['file'])[0]}  —  {loai_text(it['loai'])}, {ext_text(it['ext'])}")
            li.setFlags(li.flags() | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if it["file"] in checked else Qt.Unchecked)
            self.list.addItem(li)
        self.list.blockSignals(False)
        self.preview.clear()

    def selected(self):
        return [self.items[i]["file"] for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.Checked] if self.items else []

    def on_row(self, i):
        if 0 <= i < len(self.items):
            it = self.items[i]
            self.preview.show_template(self.core, it["ext"], self.store.kho_read(it["file"]), it["tokens"], it["unknown"])

    def add_new(self, path=None):
        name = add_template_to_kho(self, self.store, self.khach_label(), path)
        if name:
            self.refresh(check=[name])


class MauPage(QWidget):
    """Tab "Kho mẫu": mọi mẫu Word/Excel dùng chung, xem từng mẫu, nạp mẫu mới, xóa, dùng cho một khách."""

    changed = None

    def __init__(self, core, store):
        super().__init__()
        self.setObjectName("page")
        self.core, self.store, self.items = core, store, []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(10)
        t = QLabel("Kho mẫu chung")
        t.setObjectName("title")
        h = QLabel("Mẫu Word/Excel dùng lại cho nhiều khách. Tên mẫu theo quy ước LOẠI_Khách_số (VD PLX_Arizon_01). Khách mới chọn mẫu trong kho "
                   "hoặc nạp file mẫu riêng; bấm vào một mẫu để xem nội dung.")
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(h)
        split = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Mẫu", "Loại", "Khách nguồn", "Định dạng", "Số ô"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select)
        split.addWidget(self.table)
        self.preview = TemplatePreview()
        split.addWidget(self.preview)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        lay.addWidget(split, 1)
        row = QHBoxLayout()
        self.add_btn = QPushButton("📎  Nạp mẫu mới vào kho…")
        self.add_btn.clicked.connect(self.add_new)
        self.use_btn = QPushButton("👥  Dùng mẫu này cho khách…")
        self.use_btn.setObjectName("sec")
        self.use_btn.clicked.connect(self.use_for_customer)
        self.open_btn = QPushButton("📂  Mở bằng Word/Excel")
        self.open_btn.setObjectName("sec")
        self.open_btn.clicked.connect(self.open_file)
        self.del_btn = QPushButton("🗑  Xóa khỏi kho")
        self.del_btn.setObjectName("dng")
        self.del_btn.clicked.connect(self.remove)
        for b in (self.add_btn, self.use_btn, self.open_btn, self.del_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.on_select()

    def refresh(self, select=None):
        self.items = self.store.kho_list()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items))
        for r, it in enumerate(self.items):
            for c, v in enumerate([os.path.splitext(it["file"])[0], loai_text(it["loai"]), it["khach"], ext_text(it["ext"]), len(it["tokens"])]):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self.table.blockSignals(False)
        names = [it["file"] for it in self.items]
        if select in names:
            self.table.selectRow(names.index(select))
        self.on_select()

    def current(self):
        rows = self.table.selectionModel().selectedRows()
        return self.items[rows[0].row()] if rows and rows[0].row() < len(self.items) else None

    def on_select(self):
        it = self.current()
        for b in (self.use_btn, self.open_btn, self.del_btn):
            b.setEnabled(bool(it))
        if it:
            self.preview.show_template(self.core, it["ext"], self.store.kho_read(it["file"]), it["tokens"], it["unknown"])
        else:
            self.preview.clear()

    def add_new(self, path=None):
        name = add_template_to_kho(self, self.store, "Chung", path if isinstance(path, str) else None)
        if name:
            self.msg.setText(f"✅  Đã nạp mẫu “{name}” vào kho.")
            self.refresh(select=name)

    def use_for_customer(self, key=None):
        it = self.current()
        if not it:
            return
        custom = [k for k in self.core.PROFILES if k not in self.core.BUILTIN_CUSTOMERS]
        if not custom:
            widgets.warn(self, "Chưa có khách", "Chưa có khách nào đã học / thêm mới để dùng mẫu này.")
            return
        if not isinstance(key, str):
            labels = [f"{self.core.PROFILES[k].get('label') or k} — {self.core.PROFILES[k].get('name', '')}" for k in custom]
            pick, ok = QInputDialog.getItem(self, "Dùng mẫu cho khách", f"Dùng “{os.path.splitext(it['file'])[0]}” cho khách nào?", labels, 0, False)
            if not ok:
                return
            key = custom[labels.index(pick)]
        try:
            name, _known, _unknown = self.store.kho_borrow(key, it["file"])
        except ValueError as e:
            widgets.warn(self, "Chưa dùng được mẫu", str(e))
            return
        self.msg.setText(f"✅  Khách “{self.core.PROFILES[key].get('label') or key}” đã có mẫu “{name}”: nằm trong bộ chứng từ và có nút xuất riêng ở bước xuất.")

    def open_file(self):
        it = self.current()
        if it:
            QDesktopServices.openUrl(QUrl.fromLocalFile(it["path"]))

    def remove(self):
        it = self.current()
        if it and widgets.ask(self, "Xóa mẫu", f"Xóa “{os.path.splitext(it['file'])[0]}” khỏi kho? Khách đã dùng mẫu này vẫn giữ bản của họ."):
            self.store.kho_remove(it["file"])
            self.msg.setText("Đã xóa khỏi kho.")
            self.refresh()

"""Các trang ngoài luồng làm chứng từ: Hồ sơ đã lưu, Danh mục, Khách hàng, Cài đặt."""

import datetime
import os
import re

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton, QVBoxLayout, QWidget,
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


class AddFilesDialog(QDialog):
    """Kênh thêm file vào hồ sơ (kể cả hồ sơ cũ): chọn khách + ngày + file. PDF Bkav đặt tên theo số phiếu xuất kho,
    tờ khai giữ tên; Excel, PO gốc và file khác đều nằm thẳng trong thư mục ngày."""

    def __init__(self, core, store, parent=None):
        super().__init__(parent)
        self.core, self.store, self.paths, self.plan, self.added = core, store, [], [], 0
        self.setWindowTitle("Thêm file vào hồ sơ")
        self.resize(980, 620)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chọn khách và ngày của tờ khai, rồi chọn file. Phần mềm tự đặt tên PDF theo số phiếu xuất kho (PXK 247, HĐ 247, Invoice 247), "
                             "để tờ khai giữ nguyên tên và xếp vào đúng thư mục. File gốc của bạn không bị xóa."))
        lay.itemAt(0).widget().setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(QLabel("Khách hàng:"))
        self.cust = QComboBox()
        self.cust.setEditable(True)
        names = [p.get("label", k) for k, p in core.PROFILES.items()]
        root = store.customs_root()
        try:
            names += [d for d in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, d)) and not d.startswith("_") and d.upper() not in ("HAI_QUAN", "MAU_CHUNG_TU")]
        except OSError:
            pass
        self.cust.addItems(list(dict.fromkeys(names)))
        self.cust.currentTextChanged.connect(lambda _t: self.rebuild())
        row.addWidget(self.cust, 1)
        row.addWidget(QLabel("Ngày:"))
        self.day = QDateEdit(QDate.currentDate())
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd/MM/yyyy")
        self.day.dateChanged.connect(lambda _d: self.rebuild())
        row.addWidget(self.day)
        row.addWidget(QLabel("Số phiếu xuất kho:"))
        self.pxk = QLineEdit()
        self.pxk.setPlaceholderText("tự nhận từ file")
        self.pxk.setMaximumWidth(130)
        self.pxk.editingFinished.connect(self.rebuild)
        row.addWidget(self.pxk)
        lay.addLayout(row)
        brow = QHBoxLayout()
        b1 = QPushButton("📄  Chọn file…")
        b1.clicked.connect(self.pick_files)
        b2 = QPushButton("📁  Chọn cả thư mục…")
        b2.setObjectName("sec")
        b2.clicked.connect(self.pick_folder)
        brow.addWidget(b1)
        brow.addWidget(b2)
        brow.addStretch(1)
        lay.addLayout(brow)
        self.table = _table(["Tên file gốc", "Nhận biết", "Tên mới", "Vào đâu", "Ghi chú"], 2)
        lay.addWidget(self.table, 1)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        bb = QDialogButtonBox()
        self.ok = bb.addButton("Thêm vào hồ sơ", QDialogButtonBox.AcceptRole)
        self.ok.setEnabled(False)
        bb.addButton("Đóng", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.add)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    KIND = {"PXK": "Phiếu xuất kho (PDF)", "HD": "Hóa đơn Bkav (PDF)", "IV": "Invoice (scan)", "PO": "PO", "DSH": "DSH hải quan", "TK": "Tờ khai",
            "XLS_IV": "Invoice (Excel)", "XLS_DCCN": "Đối chiếu công nợ (Excel)", "XLS": "Excel", "": "Chưa nhận ra"}

    def pick_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Chọn file cần thêm vào hồ sơ", "", "Tất cả (*.*)")
        if fs:
            self.paths = list(dict.fromkeys(self.paths + fs))
            self.rebuild()

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa file của một tờ khai")
        if d:
            fs = []
            for dp, _ds, names in os.walk(d):
                fs += [os.path.join(dp, n) for n in sorted(names) if not n.startswith((".", "~$"))]
            self.paths = list(dict.fromkeys(self.paths + fs))
            self.rebuild()

    def day_iso(self):
        return self.day.date().toString("yyyy-MM-dd")

    def cust_name(self):
        return re.sub(r'[\\/:*?"<>|]+', "_", self.cust.currentText()).strip(" .")

    def rebuild(self):
        self.plan = []
        if self.paths and self.cust_name():
            no, self.plan = self.core.plan_add_files(self.store.customs_root(), self.cust_name(), self.day_iso(), self.paths, self.pxk.text())
            if no and not self.pxk.text().strip():
                self.pxk.setPlaceholderText(f"đang dùng {no}")
            self.msg.setText(f"Số phiếu xuất kho dùng để đặt tên: {no or '(chưa biết)'}.  Thư mục đích: {self.dest_folder()}")
        else:
            self.msg.setText("")
        _fill(self.table, [[os.path.basename(p["src"]), self.KIND.get(p["kind"], ""), p["new_name"],
                            "Phần mềm tạo" if p["area"] == "tao" else "Bên ngoài", p["note"]] for p in self.plan])
        self.ok.setEnabled(bool(self.plan))

    def dest_folder(self):
        d = self.day_iso()
        return os.path.join(self.store.customs_root(), self.cust_name(), f"{d[:4]}_Thang_{d[5:7]}", d)

    def add(self):
        try:
            done = self.core.apply_add_files(self.plan)
        except OSError as e:
            widgets.warn(self, "Chưa thêm được", f"{e}\nCó thể file đang mở hoặc OneDrive chưa tải xong. Hãy đóng file rồi thử lại.")
            return
        self.added += len(done)
        self.msg.setText(f"✅  Đã thêm {len(done)} file vào {self.dest_folder()}")
        self.paths, self.plan = [], []
        _fill(self.table, [])
        self.ok.setEnabled(False)


class DeclarationsPage(_Page):
    """Tờ khai đang có trong thư mục HAI_QUAN (quét thật trên ổ đĩa/OneDrive) và nút mở thẳng thư mục của từng tờ khai."""

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.shown = core, store, []
        self.lay.addWidget(_head("Tờ khai đang có", "")[0])
        self.lay.addWidget(_head("", "Danh sách lấy từ thư mục HAI_QUAN. Bấm “Mở thư mục” (hoặc bấm đúp dòng) để vào thẳng thư mục tờ khai và xem chi tiết.")[1])
        self.search = self.search_box("🔍  Tìm theo khách, số tờ khai, số PO, ngày…", lambda _t: self.refresh())
        self.lay.addWidget(self.search)
        brow = QHBoxLayout()
        self.reorg_btn = QPushButton("🗂️  Sắp xếp lại thư mục cũ…")
        self.reorg_btn.setObjectName("sec")
        self.reorg_btn.setToolTip("Đưa thư mục khách cũ về kiểu thống nhất <Khách>/<năm>_Thang_<tháng>/<ngày>. Có xem trước và hoàn tác được.")
        self.reorg_btn.clicked.connect(self.reorganize)
        self.undo_btn = QPushButton("↩  Hoàn tác lần sắp xếp gần nhất")
        self.undo_btn.setObjectName("ghost")
        self.undo_btn.clicked.connect(self.undo_reorganize)
        self.add_btn = QPushButton("➕  Thêm file vào hồ sơ…")
        self.add_btn.setToolTip("Chọn khách + ngày rồi thêm file (cả hồ sơ cũ). PDF Bkav tự đặt tên theo số phiếu xuất kho.")
        self.add_btn.clicked.connect(self.add_files)
        brow.addWidget(self.add_btn)
        brow.addWidget(self.reorg_btn)
        brow.addWidget(self.undo_btn)
        brow.addStretch(1)
        self.lay.addLayout(brow)
        self.table = _table(["Khách", "Ngày", "Số tờ khai", "Số PO", "Tình trạng (đọc từ tên file trong thư mục)", "Người làm", "Mở"], 4)
        self.table.doubleClicked.connect(lambda _i: self.open_current())
        self.lay.addWidget(self.table, 1)

    def refresh(self):
        q = self.search.text().lower().strip()
        self.shown = []
        rows = []
        for o in self.store.declaration_folders():
            r = o["record"] or {}
            vals = [o["label"], r.get("docDate") or o["day"], o.get("tk") or r.get("tkNo") or "Chưa khai", r.get("poNumber", ""), o.get("status", ""),
                    r.get("workedBy", "")]
            if q and q not in " ".join(str(v) for v in vals).lower():
                continue
            self.shown.append(o)
            rows.append(vals)
        _fill(self.table, rows)
        self.table.setColumnWidth(6, 150)
        for i, o in enumerate(self.shown):
            tip = ("Do phần mềm tạo: " + (", ".join(o.get("prepared", [])) or "(chưa có)") + "\nFile bên ngoài: " + (", ".join(o.get("other", [])) or "(chưa có)")
                   + ("\nCòn thiếu: " + ", ".join(o["missing"]) if o.get("missing") else ""))
            self.table.item(i, 4).setToolTip(tip)
        for i, o in enumerate(self.shown):
            btn = QPushButton("📁  Mở thư mục")
            btn.setObjectName("sec")
            ok = os.path.isdir(o["path"])
            btn.setEnabled(ok)
            btn.setToolTip(o["path"])
            btn.clicked.connect(lambda _=False, f=o["path"]: widgets.open_folder(f))
            self.table.setCellWidget(i, 6, btn)

    def add_files(self):
        dlg = AddFilesDialog(self.core, self.store, self)
        dlg.exec()
        if dlg.added:
            self.refresh()

    def reorganize(self):
        plan = self.store.plan_reorganize()
        if not plan:
            widgets.info(self, "Sắp xếp lại thư mục", "Các thư mục đã theo đúng kiểu thống nhất, không cần sắp xếp.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Xem trước: sắp xếp lại thư mục")
        dlg.resize(1000, 560)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Sẽ DI CHUYỂN {len(plan)} mục (chưa làm gì cho đến khi bấm Đồng ý). Dòng ghi “kiểm tra lại” là ngày đoán theo ngày sửa file."))
        tb = _table(["Khách", "Từ", "Sang", "Ngày", "Lấy ngày từ"], 1)
        root = self.store.customs_root()
        _fill(tb, [[o["customer"], os.path.relpath(o["src"], root), os.path.relpath(o["dst"], root), o["date"], o["nguon"]] for o in plan])
        tb.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(tb, 1)
        bb = QDialogButtonBox()
        ok = bb.addButton("Đồng ý, di chuyển", QDialogButtonBox.AcceptRole)
        bb.addButton("Hủy", QDialogButtonBox.RejectRole)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if not dlg.exec():
            return
        try:
            n, _log = self.store.apply_reorganize(plan)
        except OSError as e:
            widgets.warn(self, "Chưa sắp xếp được", f"{e}\nCó thể file đang mở hoặc OneDrive chưa tải xong. Hãy đóng file rồi thử lại.")
            self.refresh()
            return
        widgets.info(self, "Đã sắp xếp", f"Đã di chuyển {n} mục. Nếu chưa ưng, bấm “Hoàn tác lần sắp xếp gần nhất”.")
        self.refresh()

    def undo_reorganize(self):
        try:
            n = self.store.undo_reorganize()
        except (ValueError, OSError) as e:
            widgets.warn(self, "Chưa hoàn tác được", str(e))
            return
        widgets.info(self, "Đã hoàn tác", f"Đã đưa {n} mục về chỗ cũ.")
        self.refresh()

    def open_current(self):
        rows = self.table.selectionModel().selectedRows()
        if rows and os.path.isdir(self.shown[rows[0].row()]["path"]):
            widgets.open_folder(self.shown[rows[0].row()]["path"])


class DataTongModel(QAbstractTableModel):
    """Bảng data tổng (hàng nghìn dòng): model ảo, sửa được ô kg/chiếc và SL/kiện."""
    COLS = ["Khách", "Tên sản phẩm", "Mã hàng", "Mã ERP", "kg/chiếc", "Nguồn kg", "SL/kiện", "Nguồn kiện", "Cập nhật", "Người/máy"]
    SRC = {"erp": "file ERP", "invoice": "invoice cũ", "tay": "đã xác nhận", "": ""}
    EDIT = {4: ("kg", "kg_nguon"), 6: ("kien", "kien_nguon")}

    def __init__(self, on_edit):
        super().__init__()
        self.items, self.on_edit = [], on_edit

    def set_items(self, items):
        self.beginResetModel()
        self.items = items
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLS)

    def _val(self, x, c):
        return (x.get("khach"), x.get("ten"), x.get("ma_hang"), x.get("ma_erp"), x.get("kg") or "", self.SRC.get(x.get("kg_nguon", ""), ""),
                x.get("kien") or "", self.SRC.get(x.get("kien_nguon", ""), ""), x.get("cap_nhat"), x.get("may"))[c]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            v = self._val(self.items[index.row()], index.column())
            return "" if v is None else str(v)
        if role == Qt.TextAlignmentRole and index.column() in self.EDIT:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ToolTipRole and index.column() == 1:
            return str(self.items[index.row()].get("ten_kh") or "") or None
        return None

    def flags(self, index):
        f = super().flags(index)
        return f | Qt.ItemIsEditable if index.column() in self.EDIT else f

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole or index.column() not in self.EDIT:
            return False
        try:
            val = float(str(value).replace(",", ".") or 0)
        except ValueError:
            self.on_edit(None, None, None)  # báo giá trị sai
            return False
        key, _src = self.EDIT[index.column()]
        self.on_edit(self.items[index.row()], key, val)
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.columnCount() - 1))
        return True

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        return self.COLS[section] if role == Qt.DisplayRole and orientation == Qt.Horizontal else None


class DataTongPage(_Page):
    """Data tổng: tên sản phẩm, kg/chiếc, SL/kiện của mọi khách. Lưu ở HAI_QUAN/DATA_TONG.json, ngang hàng thư mục tên khách, chỉ đọc/ghi ở đó."""

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.shown = core, store, []
        self.lay.addWidget(_head("Data tổng", "")[0])
        self.info = _head("", "")[1]
        self.lay.addWidget(self.info)
        row = QHBoxLayout()
        b1 = QPushButton("📥  Nạp file ERP (Excel)…")
        b1.clicked.connect(self.import_erp)
        b1b = QPushButton("🔗  Nạp mã sản phẩm theo khách…")
        b1b.setObjectName("sec")
        b1b.clicked.connect(self.import_mapping)
        b2 = QPushButton("🧾  Học từ invoice cũ…")
        b2.setObjectName("sec")
        b2.clicked.connect(self.import_invoices)
        b3 = QPushButton("📊  Xuất ra Excel…")
        b3.setObjectName("sec")
        b3.clicked.connect(self.export_excel)
        b4 = QPushButton("📁  Mở thư mục chứa file")
        b4.setObjectName("sec")
        b4.clicked.connect(lambda: widgets.open_folder(os.path.dirname(self.store.dt_path())))
        for b in (b1, b1b, b2, b3, b4):
            row.addWidget(b)
        row.addStretch(1)
        self.lay.addLayout(row)
        frow = QHBoxLayout()
        self.cust = QComboBox()
        self.cust.currentIndexChanged.connect(lambda _i: self.refresh(keep_combo=True))
        frow.addWidget(QLabel("Khách:"))
        frow.addWidget(self.cust)
        self.search = self.search_box("🔍  Tìm theo tên sản phẩm, mã…", lambda _t: self.refresh(keep_combo=True))
        frow.addWidget(self.search, 1)
        self.lay.addLayout(frow)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        self.lay.addWidget(self.msg)
        self.model = DataTongModel(self.on_cell_edit)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(30)
        hh = self.table.horizontalHeader()
        for c, w in enumerate([130, 380, 130, 150, 90, 100, 90, 110, 130, 100]):
            hh.setSectionResizeMode(c, QHeaderView.Interactive)
            self.table.setColumnWidth(c, w)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.lay.addWidget(self.table, 1)

    def refresh(self, keep_combo=False):
        if not keep_combo:
            cur = self.cust.currentText()
            names = sorted({str(x.get("khach") or "") for x in self.store.data_tong if x.get("khach")}, key=str.casefold)
            self.cust.blockSignals(True)
            self.cust.clear()
            self.cust.addItem("Tất cả")
            self.cust.addItems(names)
            if cur in ["Tất cả"] + names:
                self.cust.setCurrentText(cur)
            self.cust.blockSignals(False)
        q = self.search.text().lower().strip()
        want = self.cust.currentText()
        self.shown = [x for x in self.store.data_tong if (want in ("", "Tất cả") or x.get("khach") == want)
                      and (not q or q in f"{x.get('ten', '')} {x.get('ma_hang', '')} {x.get('ma_erp', '')} {x.get('ma_kh', '')} {x.get('ten_kh', '')}".lower())]
        self.model.set_items(self.shown)
        self.info.setText(f"File dùng chung: {self.store.dt_path()}\nCó {len(self.store.data_tong):,} sản phẩm (đang hiện {len(self.shown):,}). kg/chiếc đọc từ file ERP hoặc invoice cũ; "
                          "SL/kiện đọc từ invoice cũ. Sửa trực tiếp ô kg/chiếc hoặc SL/kiện (bấm đúp) để cập nhật; mọi máy cùng dùng.")
        if not self.msg.text().startswith("✅"):
            self.msg.setText("")

    def on_cell_edit(self, x, key, val):
        if x is None:
            widgets.warn(self, "Giá trị không đúng", "Hãy nhập một số.")
            return
        x[key] = val if key == "kg" else int(round(val))
        x[key + "_nguon"] = "tay"
        now = datetime.datetime.now()
        x["ts"], x["cap_nhat"], x["may"] = now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%d/%m/%Y %H:%M"), self.store.user_name()
        self.store.dt_save()

    def _busy(self, text, fn, done):
        self.msg.setText("⏳  " + text)
        widgets.run_job(self, fn, done, lambda m: (self.msg.setText(""), widgets.warn(self, "Chưa nạp được", str(m))))

    def import_erp(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file ERP (Excel)", "", "Excel (*.xlsx *.xlsm)")
        if not path:
            return

        def done(res):
            self.msg.setText(f"✅  Nạp xong: thêm {res['them']:,} sản phẩm, cập nhật {res['cap_nhat']:,}, bỏ qua {res['bo_qua']:,} dòng (không có khách hoặc cân nặng).")
            self.refresh()
        self._busy("Đang nạp file ERP (khoảng vài giây)…", lambda: self.store.dt_import_erp(path), done)

    def import_mapping(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file mã sản phẩm theo khách hàng (Excel)", "", "Excel (*.xlsx *.xlsm)")
        if not path:
            return

        def done(res):
            self.msg.setText(f"✅  Nạp xong: thêm {res['them']:,} sản phẩm, gắn mã/tên theo khách cho {res['cap_nhat']:,} sản phẩm, bỏ qua {res['bo_qua']:,} dòng.")
            self.refresh()
        self._busy("Đang nạp mã sản phẩm theo khách…", lambda: self.store.dt_import_mapping(path), done)

    def import_invoices(self):
        keys = [k for k in self.core.PROFILES]
        dlg = QDialog(self)
        dlg.setWindowTitle("Học từ invoice cũ")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Chọn khách của các invoice sẽ nạp:"))
        combo = QComboBox()
        for k in keys:
            combo.addItem(str(self.core.PROFILES[k].get("label") or k), k)
        lay.addWidget(combo)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        key = combo.currentData()
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn các invoice cũ (Excel)", "", "Excel (*.xlsx *.xlsm)")
        if not paths:
            return

        def done(res):
            err = ("  Lỗi: " + "; ".join(res["loi"])) if res["loi"] else ""
            self.msg.setText(f"✅  Đã đọc {res['file']} file: thêm {res['them']} sản phẩm, cập nhật {res['cap_nhat']}.{err}")
            self.refresh()
        self._busy("Đang đọc invoice…", lambda: self.store.dt_import_invoices(paths, key), done)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Lưu data tổng ra Excel", "DATA_TONG.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data tổng"
        ws.append(DataTongModel.COLS)
        for x in self.shown:
            ws.append([x.get("khach"), x.get("ten"), x.get("ma_hang"), x.get("ma_erp"), x.get("kg"), DataTongModel.SRC.get(x.get("kg_nguon", ""), ""), x.get("kien"),
                       DataTongModel.SRC.get(x.get("kien_nguon", ""), ""), x.get("cap_nhat"), x.get("may")])
        wb.save(path)
        self.msg.setText(f"✅  Đã lưu {len(self.shown):,} dòng ra {path}")


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
        b3 = QPushButton("📊  Xuất sổ theo dõi ra Excel…")
        b3.setObjectName("sec")
        b3.clicked.connect(self.export_log)
        row.addWidget(b1)
        row.addWidget(b2)
        row.addWidget(b3)
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

    def export_log(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Lưu sổ theo dõi hồ sơ", "So_Theo_Doi_Ho_So.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            out = self.core.export_master_log(self.store, path)
        except OSError as e:
            widgets.warn(self, "Chưa xuất được", f"{e}\nCó thể file đang mở trong Excel.")
            return
        widgets.info(self, "Xuất sổ theo dõi", f"Đã lưu sổ theo dõi {len(self.store.records)} hồ sơ tại:\n{out}")

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
        return rec.get("_path") or self.store.get_record_folder_path(rec)

    def set_records(self, recs):
        self.recs = list(recs)
        self.setRowCount(len(self.recs))
        for r, rec in enumerate(self.recs):
            folder = self.folder_of(rec)
            label = rec.get("_label") or self.core.PROFILES.get(rec.get("customer", ""), {}).get("label", rec.get("customer", ""))
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


class RowsModel(QAbstractTableModel):
    """Bảng chỉ đọc nhiều dòng (hàng nghìn): chỉ vẽ dòng đang nhìn thấy nên mở tức thì, khác QTableWidget phải tạo ô cho từng dòng."""

    def __init__(self, headers, right=()):
        super().__init__()
        self.headers, self.right, self.rows = list(headers), set(right), []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            v = self.rows[index.row()][index.column()]
            return "" if v is None else str(v)
        if role == Qt.TextAlignmentRole and index.column() in self.right:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None


def _big_table(headers, widths, stretch_col, right=()):
    """QTableView + RowsModel với độ rộng cột cố định (không đo nội dung từng ô)."""
    v = QTableView()
    v.setModel(RowsModel(headers, right))
    v.setSelectionBehavior(QAbstractItemView.SelectRows)
    v.setSelectionMode(QAbstractItemView.SingleSelection)
    v.setEditTriggers(QAbstractItemView.NoEditTriggers)
    v.verticalHeader().hide()
    v.verticalHeader().setDefaultSectionSize(30)
    v.setAlternatingRowColors(True)
    hh = v.horizontalHeader()
    for c, w in enumerate(widths):
        hh.setSectionResizeMode(c, QHeaderView.Interactive)
        v.setColumnWidth(c, w)
    hh.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    return v


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


class CustomerForm(QWidget):
    """Biểu mẫu thông tin khách (dùng cho sửa và thêm mới)."""

    def __init__(self, core, with_hint=False):
        super().__init__()
        self.core = core
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)  # nhãn dài nằm trên ô nhập: không đẩy ô nhập ra khỏi khung
        self.edits = {}
        for key, label in core.CUSTOMER_FIELDS:
            e = QLineEdit()
            self.edits[key] = e
            lab = QLabel(label)
            lab.setWordWrap(True)  # nhãn dài tự xuống dòng, không làm khung rộng ra
            form.addRow(lab, e)

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
    """Danh sách khách bên trái (tìm kiếm), chi tiết bên phải: thông tin pháp lý & giao hàng, lưu ý đặc thù, mẫu chứng từ gắn kèm, tạo bộ hồ sơ."""
    changed = Signal()
    make_lot = Signal(str)

    CARD = "QFrame#card{background:white;border:1px solid #E2E8F0;border-radius:10px}"
    FLAT = ("QLineEdit{border:1px solid transparent;background:transparent;font-weight:600;font-size:13px;padding:3px}"
            "QLineEdit:focus{border:1px solid #93C5FD;background:white}")
    CHIP = "background:#F1F5F9;color:#475569;border-radius:4px;padding:1px 6px;font-family:monospace;font-size:11px"

    def __init__(self, core, store):
        super().__init__()
        self.core, self.store, self.keys = core, store, []
        top = QHBoxLayout()
        tv = QVBoxLayout()
        t, h = _head("Quản lý khách hàng & Cấu hình hồ sơ hải quan", "Tìm kiếm, cập nhật thông tin pháp lý, địa chỉ giao nhận và cấu hình mẫu chứng từ riêng cho từng khách hàng.")
        tv.addWidget(t)
        tv.addWidget(h)
        top.addLayout(tv, 1)
        self.learn_btn = QPushButton("📚  Học khách mới…")
        self.learn_btn.setObjectName("sec")
        self.learn_btn.setToolTip("Chọn Invoice và 2 file Bkav (PO mẫu tùy chọn) của khách mới: máy đọc thông tin và mã hàng, bạn soát lại rồi lưu.")
        self.learn_btn.clicked.connect(self.learn)
        self.add_btn = QPushButton("➕  Thêm khách hàng mới")
        self.add_btn.clicked.connect(self.add)
        top.addWidget(self.learn_btn, 0, Qt.AlignTop)
        top.addWidget(self.add_btn, 0, Qt.AlignTop)
        self.lay.addLayout(top)
        body = QHBoxLayout()
        body.setSpacing(14)
        self.lay.addLayout(body, 1)
        # ---- trái: tìm kiếm + bảng
        left = QFrame()
        left.setObjectName("card")
        left.setStyleSheet(self.CARD)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(12, 12, 12, 12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Tìm theo tên, mã, MST...")
        self.search.textChanged.connect(self.apply_filter)
        lv.addWidget(self.search)
        self.table = _table(["Mã KH", "Tên Doanh Nghiệp / KCN", "Mã Số Thuế", "Mẫu gắn kèm"], 1)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        self.table.setStyleSheet("QTableWidget{border:none;font-size:13px}QTableWidget::item{border-bottom:1px solid #E2E8F0;padding:6px}"
                                 "QTableWidget::item:selected{background:#DBEAFE;color:#0F172A}"
                                 "QHeaderView::section{background:#F1F5F9;color:#1E293B;font-weight:700;padding:8px;border:none;border-bottom:1px solid #E2E8F0}")
        self.table.itemSelectionChanged.connect(self.on_select)
        lv.addWidget(self.table, 1)
        body.addWidget(left, 62)
        # ---- phải: chi tiết
        self.form = CustomerForm(core)  # giữ các ô nhập (form.edits); đặt vào đúng chỗ của thẻ chi tiết bên dưới
        ed = self.form.edits
        right = QFrame()
        right.setObjectName("card")
        right.setStyleSheet(self.CARD)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 12)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(16, 14, 16, 8)
        iv.setSpacing(8)
        cap = QLabel("CHI TIẾT KHÁCH HÀNG")
        cap.setStyleSheet("color:#64748B;font-weight:700;font-size:11px")
        iv.addWidget(cap)
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size:16px;font-weight:700;color:#0F172A")
        iv.addWidget(self.title)

        def sec(text):
            lab = QLabel(text)
            lab.setStyleSheet("font-weight:700;margin-top:8px")
            iv.addWidget(lab)

        def row(label, key, chip=None):
            g = QHBoxLayout()
            lb = QLabel(label)
            lb.setFixedWidth(118)
            lb.setWordWrap(True)
            lb.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            lb.setStyleSheet("color:#475569;padding-top:4px")
            g.addWidget(lb)
            col = QVBoxLayout()
            col.setSpacing(2)
            ed[key].setStyleSheet(self.FLAT)
            col.addWidget(ed[key])
            if chip:
                c = QLabel(chip)
                c.setStyleSheet(self.CHIP)
                c.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
                col.addWidget(c, 0, Qt.AlignLeft)
            g.addLayout(col, 1)
            iv.addLayout(g)

        sec("1. Thông tin Pháp lý & Giao hàng")
        row("Tên KH", "name", "{{khach_ten}}")
        row("MST", "mst")
        row("Địa chỉ nhận hàng", "addrKho", "{{khach_dia_chi}}")
        sec("2. Lưu ý khi làm chứng từ")
        self.note_frame = QFrame()
        self.note_frame.setStyleSheet("QFrame{background:#FEF9C3;border:1px solid #FDE047;border-radius:8px}QLabel{border:none;color:#451A03}")
        nl = QHBoxLayout(self.note_frame)
        nl.setContentsMargins(10, 8, 10, 8)
        nl.addWidget(QLabel("⚠  Lưu ý đặc thù:"))
        ed["note"].setStyleSheet("QLineEdit{border:none;background:transparent;font-size:12px;color:#451A03}")
        ed["note"].setPlaceholderText("Ghi lưu ý khi làm chứng từ cho khách này (hiện nhắc ở bước xuất)")
        nl.addWidget(ed["note"], 1)
        iv.addWidget(self.note_frame)
        sec("3. Mẫu chứng từ gắn kèm")
        self.forms_box = QFrame()
        self.forms_box.setStyleSheet("QFrame#fb{border:1px solid #E2E8F0;border-radius:8px}QLabel{border:none;padding:5px}")
        self.forms_box.setObjectName("fb")
        self.forms_lay = QVBoxLayout(self.forms_box)
        self.forms_lay.setContentsMargins(6, 6, 6, 6)
        iv.addWidget(self.forms_box)
        # phần còn lại gập lại: các ô thông tin khác + công cụ
        self.more_btn = QToolButton()
        self.more_btn.setText("Thông tin khác và công cụ  ▸")
        self.more_btn.setCheckable(True)
        self.more_btn.setStyleSheet("QToolButton{border:none;color:#1E3A5F;font-weight:600;padding:6px 0}")
        self.more_btn.toggled.connect(self._toggle_more)
        iv.addWidget(self.more_btn)
        self.more = QWidget()
        mv = QVBoxLayout(self.more)
        mv.setContentsMargins(0, 0, 0, 0)
        fl = QFormLayout()
        fl.setRowWrapPolicy(QFormLayout.WrapAllRows)
        names = dict(core.CUSTOMER_FIELDS)
        for k in ed:
            if k not in ("name", "mst", "addrKho", "note"):
                lb = QLabel(names[k])
                lb.setWordWrap(True)
                fl.addRow(lb, ed[k])
        mv.addLayout(fl)
        grid = QGridLayout()
        self.export_btn = QPushButton("📤  Xuất file học")
        self.export_btn.setObjectName("sec")
        self.export_btn.setToolTip("Tạo file .json (hồ sơ khách, danh mục hàng, định mức, file mẫu chứng từ) để máy khác nạp ở Cài đặt → Nạp dữ liệu học.")
        self.export_btn.clicked.connect(self.export_learned)
        self.form_btn = QPushButton("📎  Thêm mẫu riêng…")
        self.form_btn.setObjectName("sec")
        self.form_btn.setToolTip("Nhập file Word/Excel chứng từ hoặc mẫu của khách: máy nhận ra chỗ đổi được, bạn quyết định chỗ nào thành ô, rồi mẫu được gắn cho khách.")
        self.form_btn.clicked.connect(self.add_form)
        self.tokens_btn = QPushButton("📝  Ô thay thế")
        self.tokens_btn.setObjectName("ghost")
        self.tokens_btn.clicked.connect(self.show_tokens)
        for i, b in enumerate((self.export_btn, self.form_btn, self.tokens_btn)):
            grid.addWidget(b, i // 2, i % 2)
        mv.addLayout(grid)
        self.more.setVisible(False)
        iv.addWidget(self.more)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        iv.addWidget(self.msg)
        iv.addStretch(1)
        sc.setWidget(inner)
        rv.addWidget(sc, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 0, 16, 0)
        self.make_btn = QPushButton("⊞  Tạo bộ hồ sơ cho khách hàng này")
        self.make_btn.clicked.connect(lambda: self.current_key() and self.make_lot.emit(self.current_key()))
        self.save_btn = QPushButton("Lưu thay đổi")
        self.save_btn.setObjectName("sec")
        self.save_btn.clicked.connect(self.save)
        bar.addWidget(self.make_btn, 1)
        bar.addWidget(self.save_btn)
        rv.addLayout(bar)
        body.addWidget(right, 38)
        self.form.set_enabled(False)
        self.save_btn.setEnabled(False)

    def _toggle_more(self, on):
        self.more.setVisible(on)
        self.more_btn.setText("Thông tin khác và công cụ  " + ("▾" if on else "▸"))

    def refresh(self, select=None):
        c = self.core
        self.keys = list(c.PROFILES)
        rows = [[p.get("label", k), p.get("name", ""), p.get("mst", ""), ", ".join(self.forms_of(k))] for k, p in c.PROFILES.items()]
        self.table.blockSignals(True)
        _fill(self.table, rows)
        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):
            self.table.setRowHeight(r, max(46, self.table.rowHeight(r)))
        self.table.blockSignals(False)
        if select in self.keys:
            self.table.selectRow(self.keys.index(select))
        self.apply_filter()
        self.on_select()

    def forms_of(self, key):
        """Tên các chứng từ làm thêm (mẫu có sẵn của phần mềm) và mẫu riêng (file Word/Excel) của khách."""
        prof = self.core.PROFILES.get(key) or {}
        return list(self.core.customer_extra_docs(prof)) + [n.rsplit(".", 1)[0] for n in prof.get("rieng") or []]

    def apply_filter(self, text=""):
        t = (text or self.search.text()).strip().lower()
        for r in range(self.table.rowCount()):
            self.table.setRowHidden(r, bool(t) and t not in " ".join(self.table.item(r, c).text().lower() for c in range(4)))

    def current_key(self):
        rows = self.table.selectionModel().selectedRows()
        return self.keys[rows[0].row()] if rows else None

    def on_select(self):
        key = self.current_key()
        custom = bool(key) and key not in self.core.BUILTIN_CUSTOMERS
        self.form.set_enabled(bool(key))
        self.save_btn.setEnabled(bool(key))
        self.make_btn.setEnabled(bool(key))
        self.export_btn.setEnabled(custom)
        self.form_btn.setEnabled(custom)
        self.form.load(self.core.PROFILES.get(key) if key else None)
        for e in self.form.edits.values():
            e.setCursorPosition(0)  # chữ dài hiện từ đầu, không trôi về cuối
        prof = self.core.PROFILES.get(key) or {}
        self.title.setText(prof.get("name", "") if key else "Chọn một khách ở danh sách bên trái")
        while self.forms_lay.count():
            w = self.forms_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        items = []
        for code in (self.core.customer_extra_docs(prof) if key else []):
            items.append(("X", "#059669", f"{code} (mẫu có sẵn của phần mềm)"))
        for n in (prof.get("rieng") or []) if key else []:
            word = n.lower().endswith(".docx")
            items.append(("W" if word else "X", "#2563EB" if word else "#059669", f"{n.rsplit('.', 1)[0]} ({'Word' if word else 'Excel'})"))
        for badge, color, text in items or [("", "", "Chưa có mẫu nào (thêm ở “Thông tin khác và công cụ → Thêm mẫu riêng”)")]:
            lab = QLabel((f"<span style='background:{color};color:white;font-weight:700'>&nbsp;{badge}&nbsp;</span>&nbsp; " if badge else "") + text)
            self.forms_lay.addWidget(lab)

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

    def learn(self, paths=None):
        if not paths:  # bước 1: nhập cùng lúc Invoice + 2 file Bkav (PO mẫu tùy chọn)
            from .dialogs import LearnFilesDialog
            dlg = LearnFilesDialog(self)
            if not dlg.exec():
                return
            paths = dlg.file_list()
        if not paths:
            return
        self.msg.setText("⏳  Đang đọc chứng từ mẫu… file scan có thể mất vài chục giây.")
        widgets.run_job(self, lambda: self.core.learn_customer_from_documents(list(paths)), lambda d, p=list(paths): self._learned(d, p),
                        lambda m: self.msg.setText(f"Không đọc được chứng từ mẫu: {m}"))

    def _learned(self, draft, paths):
        from .dialogs import LearnCustomerDialog
        self.msg.setText("")
        dlg = LearnCustomerDialog(self.core, self.store, paths, self, draft=draft)
        if dlg.exec():
            self.msg.setText(f"✅  Đã lưu khách “{dlg.key}”: nay có {len(self.store.custom_items.get(dlg.key, []))} mã hàng. Chọn khách này ở Làm chứng từ rồi nạp PO.")
            self.refresh(select=dlg.key)
            self.changed.emit()

    def export_learned(self, path=None):
        key = self.current_key()
        if not key:
            return
        try:
            data = self.store.export_learned(key)
        except ValueError as e:
            widgets.warn(self, "Chưa xuất được", str(e))
            return
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Lưu file dữ liệu học", f"dulieu_hoc_{key}.json", "Dữ liệu học (*.json)")
        if not path:
            return
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        self.msg.setText(f"✅  Đã xuất {len(data['khach_moi']['items'])} mặt hàng và {len(data['khach_moi']['mau'])} file mẫu ra: {path}. Máy khác: Cài đặt → Nạp dữ liệu học.")

    def add_form(self, path=None, names=None):
        """Thêm mẫu riêng cho khách: file nào cũng qua hộp thoại nhận diện chỗ đổi được, vào kho mẫu rồi dùng luôn cho khách này."""
        key = self.current_key()
        if not key:
            return
        if names is None:
            from .pages_kho import add_template_to_kho
            names = add_template_to_kho(self, self.store, self.core.PROFILES[key].get("label") or key, path)
        if not names:
            return
        done, bad = [], []
        for n in names:
            try:
                done.append(self.store.kho_borrow(key, n)[0])
            except ValueError as e:
                bad.append(f"{n}: {e}")
        if bad:
            widgets.warn(self, "Một số mẫu chưa thêm được cho khách", "\n".join(bad))
        if done:
            self.msg.setText(f"✅  Khách đã có {len(done)} mẫu riêng: {', '.join(done)}. Mẫu nằm trong bộ chứng từ và có nút xuất riêng ở bước xuất (cũng có trong tab Kho mẫu).")
            self.changed.emit()

    def show_tokens(self):
        import mau_rieng
        lines = ["Gõ các ô dưới đây vào file Word/Excel mẫu của khách, phần mềm sẽ điền số liệu của lô.\n", "Ô chung của cả lô:"]
        lines += [f"  {{{{{k}}}}}  —  {d}" for k, d in mau_rieng.TOKENS]
        lines += ["\nÔ theo dòng hàng (dòng Excel / dòng bảng Word / đoạn Word có chứa ô này được nhân lên cho mỗi mặt hàng):"]
        lines += [f"  {{{{{k}}}}}  —  {d}" for k, d in mau_rieng.ITEM_TOKENS]
        QMessageBox.information(self, "Các ô thay thế trong mẫu riêng", "\n".join(lines))

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

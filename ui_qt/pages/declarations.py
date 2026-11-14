"""Trang Tờ khai đang có: thư mục hồ sơ còn làm dở, thêm file vào hồ sơ."""

import os
import re

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from .. import widgets
from ._base import _Page, _fill, _head, _table


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

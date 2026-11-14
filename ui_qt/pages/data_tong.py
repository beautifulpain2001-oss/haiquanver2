"""Trang Data tổng: bảng dữ liệu hàng hóa, kg/chiếc, SL/kiện."""

import datetime
import os

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableView, QVBoxLayout,
)

from .. import widgets
from ._base import _Page, _head


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

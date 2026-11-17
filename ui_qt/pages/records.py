"""Trang Hồ sơ đã lưu: danh sách hồ sơ, bảng hồ sơ dùng chung cho Danh mục."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView, QPushButton, QTableWidget, QTableWidgetItem

from .. import widgets
from ._base import _Page, _fill, _head, _table


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
            facts = self.store.folder_facts(r)  # số HĐ, PXK, tờ khai đọc từ tên file trong thư mục thật nếu hồ sơ chưa ghi
            rows.append([label, r.get("docDate", ""), r.get("poNumber", ""), r.get("pxkNo") or facts.get("pxk") or "Chờ cấp", r.get("hdNo") or facts.get("hd") or "Chờ ký",
                         r.get("tkNo") or facts.get("tk") or "Chưa khai", widgets.fmt_num(r.get("totalAmount")),
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

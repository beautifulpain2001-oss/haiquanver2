"""Hộp thoại thêm / sửa một dòng hàng."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

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

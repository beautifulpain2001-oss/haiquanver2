"""Trang Cài đặt: thư mục dữ liệu, OCR, công ty, học dữ liệu khách."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import widgets
from ._base import _Page, _head


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

        vbox = QGroupBox("Lái xe và biển số xe")
        vl = QVBoxLayout(vbox)
        vh = QLabel("Mỗi lô hàng phần mềm chọn ngẫu nhiên 1 cặp trong danh sách này; mọi chứng từ của lô dùng cùng cặp đó "
                    "(lái xe nào thì đúng biển số xe đó). Khách nào cần cố định thì ghi lái xe và biển số ở mục Khách hàng. "
                    "Ở bước làm hồ sơ vẫn sửa tay được; gõ tên lái xe có trong danh sách thì biển số tự đổi theo.")
        vh.setObjectName("hint")
        vh.setWordWrap(True)
        vl.addWidget(vh)
        self.vtable = QTableWidget(0, 2)
        self.vtable.setHorizontalHeaderLabels(["Họ tên lái xe", "Biển số xe"])
        self.vtable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vtable.verticalHeader().setVisible(False)
        self.vtable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.vtable.setMinimumHeight(170)
        vl.addWidget(self.vtable)
        vrow = QHBoxLayout()
        add_b = QPushButton("➕  Thêm cặp")
        add_b.setObjectName("sec")
        add_b.clicked.connect(lambda: self.add_vehicle_row())
        del_b = QPushButton("🗑  Xóa dòng đang chọn")
        del_b.setObjectName("sec")
        del_b.clicked.connect(self.del_vehicle_rows)
        self.vsave_btn = QPushButton("💾  Lưu danh sách xe")
        self.vsave_btn.clicked.connect(self.save_vehicles)
        vrow.addWidget(self.vsave_btn)
        vrow.addWidget(add_b)
        vrow.addWidget(del_b)
        vrow.addStretch(1)
        vl.addLayout(vrow)
        self.vehicle_msg = QLabel("")
        self.vehicle_msg.setObjectName("hint")
        self.vehicle_msg.setWordWrap(True)
        vl.addWidget(self.vehicle_msg)
        lay.addWidget(vbox)

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
        self.load_vehicles()
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

    # --- cặp lái xe + biển số
    def add_vehicle_row(self, driver="", xe=""):
        r = self.vtable.rowCount()
        self.vtable.insertRow(r)
        self.vtable.setItem(r, 0, QTableWidgetItem(driver))
        self.vtable.setItem(r, 1, QTableWidgetItem(xe))
        if not driver and not xe:
            self.vtable.setCurrentCell(r, 0)
            self.vtable.editItem(self.vtable.item(r, 0))

    def load_vehicles(self):
        self.vtable.setRowCount(0)
        for p in self.store.vehicle_list():
            self.add_vehicle_row(p.get("driver", ""), p.get("xe", ""))

    def del_vehicle_rows(self):
        for r in sorted({i.row() for i in self.vtable.selectedIndexes()}, reverse=True):
            self.vtable.removeRow(r)

    def vehicle_rows(self):
        cell = lambda r, c: (self.vtable.item(r, c).text() if self.vtable.item(r, c) else "")
        return [{"driver": cell(r, 0), "xe": cell(r, 1)} for r in range(self.vtable.rowCount())]

    def save_vehicles(self):
        try:
            self.store.set_vehicles(self.vehicle_rows())
        except ValueError as e:
            widgets.warn(self, "Chưa lưu được", str(e))
            return
        self.load_vehicles()
        self.vehicle_msg.setText(f"✅  Đã lưu {self.vtable.rowCount()} cặp lái xe + biển số. Lô mới sẽ chọn ngẫu nhiên 1 cặp trong danh sách này.")

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
        self.load_vehicles()
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã đổi thư mục dữ liệu", f"Phần mềm sẽ lưu và đọc dữ liệu tại:\n{self.store.base_dir}")

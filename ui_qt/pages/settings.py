"""Trang Cài đặt: thư mục dữ liệu, OCR, công ty, học dữ liệu khách."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea,
    QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
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
                     "Không cần mạng LAN hay máy chủ. Khách hàng, bảng Kg & kiện, kho dữ liệu, cài đặt (lái xe, công ty) và hồ sơ "
                     "đều đọc/ghi ở đây; máy khác lưu thì máy này tự đọc lại sau vài giây. Hai máy sửa cùng lúc thì phần mềm GỘP theo mã hàng "
                     "(dòng 🔒 sửa tay được ưu tiên) và tự sao lưu trước khi ghi vào thư mục _SAO_LUU.")
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
        b3 = QPushButton("🗂  Mở thư mục sao lưu")
        b3.setObjectName("sec")
        b3.clicked.connect(self.open_backups)
        drow.addWidget(b1)
        drow.addWidget(b2)
        drow.addWidget(b3)
        drow.addStretch(1)
        dl.addLayout(drow)
        self.sync_info = QLabel("")
        self.sync_info.setObjectName("hint")
        self.sync_info.setWordWrap(True)
        dl.addWidget(self.sync_info)
        tip = QLabel("Mẹo: nên đặt thư mục dữ liệu ở nơi cố định (ví dụ D:\\HongThien hoặc ổ mạng dùng chung), tránh thư mục Downloads vì dễ bị dọn nhầm.")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        dl.addWidget(tip)
        lay.addWidget(dbox)

        kbox = QGroupBox("Mỗi khách một file dữ liệu")
        kl = QVBoxLayout(kbox)
        tip = QLabel("Cách lưu mới: dữ liệu riêng của khách nào (danh mục mã hàng, học, Kg & kiện, danh sách hồ sơ) nằm trong thư mục khách đó, "
                     "file HAI_QUAN/<Khách>/DU_LIEU_<MÃ>.json; chi tiết từng bộ hồ sơ ở thẻ 00_HO_SO.json trong thư mục lô. Chỉ phần dùng chung "
                     "(thông tin công ty, lái xe, ERP chung, định mức theo tên) nằm ở HAI_QUAN/_HE_THONG. Lưu khách nào chỉ ghi file khách đó. "
                     "TRƯỚC KHI CHUYỂN: cập nhật bản phần mềm này cho MỌI máy dùng chung thư mục (bản cũ không đọc được cách mới).")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        kl.addWidget(tip)
        self.kh_state = QLabel("")
        self.kh_state.setWordWrap(True)
        kl.addWidget(self.kh_state)
        krow = QHBoxLayout()
        self.kh_btn = QPushButton("🔀  Xem trước và chuyển sang mỗi khách một file…")
        self.kh_btn.setObjectName("sec")
        self.kh_btn.clicked.connect(self.chuyen_doi)
        self.kh_undo = QPushButton("↩  Hoàn tác chuyển đổi…")
        self.kh_undo.setObjectName("sec")
        self.kh_undo.clicked.connect(self.hoan_tac)
        krow.addWidget(self.kh_btn)
        krow.addWidget(self.kh_undo)
        krow.addStretch(1)
        kl.addLayout(krow)
        tip2 = QLabel("Sắp xếp lại dữ liệu (bấm khi cần): gộp file kiểu cũ do máy chưa cập nhật ghi lại, đưa file khách về đúng thư mục khách, "
                      "một khách một tên trong Kg & kiện, bỏ dòng Kg & kiện trùng. Số PXK trùng, cùng mã khác kg, dòng hàng lặp chỉ được BÁO để bạn tự sửa. "
                      "Có xem trước, sao lưu trước và hoàn tác.")
        tip2.setObjectName("hint")
        tip2.setWordWrap(True)
        kl.addWidget(tip2)
        srow = QHBoxLayout()
        self.sx_btn = QPushButton("🧹  Sắp xếp lại dữ liệu…")
        self.sx_btn.setObjectName("sec")
        self.sx_btn.clicked.connect(self.sap_xep)
        self.sx_undo = QPushButton("↩  Hoàn tác lần sắp xếp gần nhất…")
        self.sx_undo.setObjectName("sec")
        self.sx_undo.clicked.connect(self.sap_xep_hoan_tac)
        srow.addWidget(self.sx_btn)
        srow.addWidget(self.sx_undo)
        srow.addStretch(1)
        kl.addLayout(srow)
        lay.addWidget(kbox)

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
        bits = [f"Sao lưu tự động: {self.store.backup_count()} bản trong _SAO_LUU (tối đa 1 bản / 30 phút cho mỗi file)."]
        if self.store.last_sync:
            bits.append(f"Lần gần nhất đọc lại dữ liệu máy khác: {self.store.last_sync}.")
        if self.store.last_conflicts:
            bits.append(f"Đã gộp {self.store.last_conflicts} bản xung đột do OneDrive/Google Drive tạo.")
        self.sync_info.setText(" ".join(bits))
        self.show_kh_state()
        self.show_ocr()

    def show_kh_state(self):
        on = self.store.theo_khach()
        txt = "✅  Đang dùng cách lưu mỗi khách một file." if on else "Đang dùng cách lưu cũ (3 file chung cho mọi khách)."
        if not on and getattr(self.store, "orphan_files", 0):
            txt += f"  Đã đọc thêm {self.store.orphan_files} file khách có sẵn; bấm 'Xem trước và chuyển' để hoàn tất."
        self.kh_state.setText(txt)
        self.kh_btn.setEnabled(not on)
        self.kh_undo.setEnabled(on)
        self.sx_btn.setEnabled(on)
        self.sx_undo.setEnabled(on)

    def sap_xep(self):
        try:
            pv = self.store.sap_xep_xem_truoc()
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa xem trước được", str(e))
            return
        lines = ["Sẽ làm:"]
        lines.append(f"• Gộp {len(pv['file_cu'])} file kiểu cũ: {', '.join(pv['file_cu'])}" if pv["file_cu"] else "• Không có file kiểu cũ.")
        if pv["nhan_doi"]:
            lines.append(f"• Gộp {len(pv['nhan_doi'])} file khách bị nhân đôi: {', '.join(pv['nhan_doi'])}")
        if pv.get("file_la"):
            lines.append(f"• Cất {len(pv['file_la'])} file DU_LIEU của khách CHƯA có trong app (bản trước lỡ tạo) vào bản sao lưu; "
                         f"dữ liệu chuyển về dữ liệu chung, không mất.")
            if pv.get("thu_muc_trong"):
                lines.append(f"   Thư mục chỉ còn trống sau đó sẽ bỏ ({len(pv['thu_muc_trong'])}): {', '.join(pv['thu_muc_trong'][:20])}"
                             + (" …" if len(pv["thu_muc_trong"]) > 20 else ""))
            lines.append("   Thư mục khách có file khác (hồ sơ, chứng từ) giữ nguyên.")
        lines += [f"• Chuyển {a} → {b}" for a, b in pv["sai_cho"]]
        if pv["ten_goi"]:
            lines.append(f"• Một khách một tên ({pv['doi_ten']} dòng Kg & kiện đổi tên):")
            lines += [f"   {k}: {' / '.join(v)}" for k, v in list(pv["ten_goi"].items())[:15]]
        lines.append(f"• Bỏ {pv['dong_trung']} dòng Kg & kiện trùng (giữ dòng 🔒 / sửa tay / mới nhất, ô trống lấy từ dòng bỏ)." if pv["dong_trung"]
                     else "• Không có dòng Kg & kiện trùng.")
        bao = self._chua_co_lines(pv.get("chua_co"))
        if pv["pxk_trung"]:
            bao.append("Số PXK trùng giữa các bộ (đổi một bộ theo số Bkav):")
            bao += [f"   {x['pxk']}: {', '.join(x['ho_so'])}" for x in pv["pxk_trung"]]
        if pv["kg_lech"]:
            bao.append(f"{len(pv['kg_lech'])} mã có nhiều kg khác nhau (sửa ở bảng Kg & kiện):")
            bao += [f"   {x['khach']} {x['ma']}: {' / '.join(x['kg'])} kg" for x in pv["kg_lech"][:12]]
        if pv["dong_lap"]:
            bao.append(f"{len(pv['dong_lap'])} dòng hàng lặp trong hồ sơ (nhập thừa hay giao nhiều đợt?):")
            bao += [f"   {x['ho_so']} PO {x['po'] or '-'} {x['ma']}: {x['lan']} lần" for x in pv["dong_lap"][:12]]
        if bao:
            lines += ["", "⚠ Cần bạn tự xem (phần mềm KHÔNG tự sửa):"] + bao
        lines += ["", "Trước khi làm sẽ sao lưu mọi file dữ liệu vào _SAO_LUU/truoc_sap_xep_<giờ>. Sắp xếp ngay?"]
        box = QMessageBox(self)
        box.setWindowTitle("Sắp xếp lại dữ liệu")
        box.setText("\n".join(lines))
        yes = box.addButton("Sắp xếp ngay", QMessageBox.YesRole)
        box.addButton("Hủy", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return
        try:
            st = self.store.sap_xep_thuc_hien()
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa sắp xếp được", str(e))
            return
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã sắp xếp", f"Gộp {st['file_cu']} file cũ, {st['nhan_doi']} file nhân đôi; cất {st['file_la']} file khách chưa có trong app, bỏ {st['thu_muc_xoa']} thư mục trống; chuyển {st['sai_cho']} file về đúng thư mục; "
                                         f"đổi tên khách {st['doi_ten']} dòng; bỏ {st['dong_trung']} dòng trùng.\nBản sao lưu: {st['sao_luu']}")

    @staticmethod
    def _chua_co_lines(chua_co):
        """Tên khách có trong dữ liệu mà app chưa có: liệt kê để người dùng chọn thêm khách ở trang Khách hàng hoặc bỏ qua."""
        if not chua_co:
            return []
        items = sorted(chua_co.values(), key=lambda o: -(o["dong"] + o["ho_so"]))
        out = ["", f"ℹ {len(items)} tên khách có trong dữ liệu nhưng CHƯA có trong app: giữ ở dữ liệu chung (_HE_THONG), "
                   "không tạo thư mục. Muốn tách riêng thì thêm khách ở trang Khách hàng; không thì bỏ qua:"]
        out += [f"   {' / '.join(o['ten'][:3])}: {o['dong']} dòng Kg & kiện" + (f", {o['ho_so']} hồ sơ" if o["ho_so"] else "") for o in items[:25]]
        if len(items) > 25:
            out.append(f"   … và {len(items) - 25} tên khác")
        return out

    def sap_xep_hoan_tac(self):
        if not widgets.ask(self, "Hoàn tác sắp xếp", "Trả dữ liệu về như ngay trước lần sắp xếp gần nhất?\n\nThay đổi làm sau lần sắp xếp đó sẽ mất."):
            return
        try:
            d = self.store.sap_xep_hoan_tac()
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa hoàn tác được", str(e))
            return
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã hoàn tác", f"Đã lấy lại dữ liệu từ {d}.")

    def chuyen_doi(self):
        try:
            pv = self.store.chuyen_doi_xem_truoc()
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa xem trước được", f"Lỗi: {e}")
            return
        lines = [f"Sẽ tạo {len(pv['files']) - 1} file khách + 1 file dùng chung, {pv['ho_so']} hồ sơ:", ""]
        for r in pv["files"]:
            ten = f"  (gộp tên: {' / '.join(r['ten_goi'])})" if r["ten_goi"] else ""
            lines.append(f"• {r['ten']}: {r['file']} | {r['ma_hang']} mã, {r['data_tong']} dòng Kg & kiện, {r['ho_so']} hồ sơ{ten}")
        lines += self._chua_co_lines(pv.get("chua_co"))
        if pv.get("file_khach_co_san"):
            lines += ["", f"ℹ Đã có sẵn {len(pv['file_khach_co_san'])} file khách (chuyển dở dang trước đó). Dữ liệu trong đó đã được đọc vào phần mềm; "
                          "trước khi ghi lại, các file này được sao lưu vào _SAO_LUU."]
        if pv["pxk_trung"]:
            lines += ["", "⚠ Số PXK trùng giữa các bộ (cần đổi một bộ theo số Bkav, phần mềm KHÔNG tự đổi):"]
            lines += [f"   {x['pxk']}: {', '.join(x['ho_so'])}" for x in pv["pxk_trung"]]
        if pv["kg_lech"]:
            lines += ["", f"⚠ {len(pv['kg_lech'])} mã ghi 2 lần với kg khác nhau (giữ nguyên cả hai, kiểm tra ở Kho dữ liệu):"]
            lines += [f"   {x['khach']} {x['ma']}: {' / '.join(x['kg'])} kg" for x in pv["kg_lech"][:15]]
        if pv["ho_so_khong_thu_muc"]:
            lines += ["", f"{pv['ho_so_khong_thu_muc']} hồ sơ chưa có thư mục lô: giữ cả hồ sơ trong file khách."]
        lines += ["", f"Sao lưu trước khi chuyển: {', '.join(pv['file_cu'])}"
                  + (f" và {len(pv['ban_xung_dot'])} bản xung đột" if pv["ban_xung_dot"] else "") + " vào _SAO_LUU/truoc_chuyen_doi_<giờ>.",
                  "File cũ đổi tên thành *.DA_CHUYEN.json (không xóa). Số liệu chép nguyên, không tính lại.",
                  "", "Mọi máy dùng chung thư mục đã cập nhật bản phần mềm này chưa? Chuyển ngay?"]
        box = QMessageBox(self)
        box.setWindowTitle("Chuyển sang mỗi khách một file")
        box.setText("\n".join(lines))
        yes = box.addButton("Chuyển ngay", QMessageBox.YesRole)
        box.addButton("Hủy", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return
        try:
            res = self.store.chuyen_doi_thuc_hien()
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa chuyển được", str(e))
            return
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã chuyển", f"Đã tạo {res['files']} file khách, {res['ho_so']} hồ sơ, {res['data_tong']} dòng Kg & kiện.\n"
                                        f"Bản sao lưu: {res['sao_luu']}")

    def hoan_tac(self):
        if not widgets.ask(self, "Hoàn tác chuyển đổi", "Quay về cách lưu cũ (3 file chung) từ bản sao lưu trước khi chuyển?\n\n"
                                                        "Thay đổi làm SAU khi chuyển sẽ không có trong cách lưu cũ. File khách vẫn giữ trên đĩa."):
            return
        try:
            d = self.store.chuyen_doi_hoan_tac()
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa hoàn tác được", str(e))
            return
        self.refresh()
        self.data_changed.emit()
        widgets.info(self, "Đã hoàn tác", f"Đã lấy lại dữ liệu cũ từ {d}.")

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
        if "ma_sua" in res:
            self.learn_msg.setText(f"✅ Đã cập nhật ĐVT, SL/kiện, kg theo mã cho {res['ma_sua']} mặt hàng; thêm mới {res['ma_them']} mã chưa có.")
        else:
            self.learn_msg.setText(f"✅ {kh} Đã thêm {res['them']} mặt hàng; bỏ qua {res['bo_qua']} mặt hàng đã có định mức.")
        if res.get("khach") or "ma_sua" in res:
            self.data_changed.emit()

    def save_user(self):
        self.store.set_user_name(self.user_edit.text())
        self.user_msg.setText(f"✅  Đã lưu: máy này là “{self.store.user_name() or '(chưa đặt tên)'}”.")

    def open_backups(self):
        import os
        os.makedirs(self.store.backup_root(), exist_ok=True)
        widgets.open_folder(self.store.backup_root())

    def change_dir(self):
        import os
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu dữ liệu (thư mục chung của các máy)")
        if not d:
            return
        if os.path.normcase(os.path.abspath(d)) == os.path.normcase(os.path.abspath(self.store.base_dir)):
            return
        has = self.store.folder_has_data(d)
        box = QMessageBox(self)
        box.setWindowTitle("Mang dữ liệu sang thư mục mới?")
        if has:
            box.setText("Thư mục này ĐÃ CÓ dữ liệu phần mềm (máy khác đang dùng).\n\n"
                        "Gộp dữ liệu đang dùng trên máy này vào đó? Phần mềm chỉ THÊM phần còn thiếu (khách, mã hàng, hồ sơ, file hồ sơ); "
                        "chỗ trùng giữ bản trong thư mục chung, riêng dòng 🔒 sửa tay ở bảng Kg & kiện được ưu tiên. "
                        "Trước khi gộp sẽ sao lưu vào _SAO_LUU. Thư mục cũ trên máy này giữ nguyên.")
        else:
            box.setText("Thư mục này chưa có dữ liệu phần mềm.\n\n"
                        "Chép toàn bộ dữ liệu đang dùng trên máy này (khách, Kg & kiện, kho dữ liệu, cài đặt, hồ sơ, mẫu chứng từ) sang đó? "
                        "Thư mục cũ giữ nguyên.")
        yes = box.addButton("Gộp vào thư mục chung" if has else "Chép dữ liệu sang", QMessageBox.YesRole)
        no = box.addButton("Chỉ đổi thư mục, không mang theo", QMessageBox.NoRole)
        box.addButton("Hủy", QMessageBox.RejectRole)
        box.setDefaultButton(yes)
        box.exec()
        if box.clickedButton() not in (yes, no):
            return
        try:
            st = self.store.change_base_dir(d, mang_theo=box.clickedButton() is yes)
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa đổi được thư mục", f"Lỗi: {e}")
            return
        self.load_company()
        self.load_vehicles()
        self.refresh()
        self.data_changed.emit()
        more = ""
        if st.get("che_do") == "chep":
            more = f"\n\nĐã chép dữ liệu máy này sang ({st['ho_so']} hồ sơ, {st['file']} file hồ sơ/mẫu)."
        elif st.get("che_do") == "gop":
            more = (f"\n\nĐã gộp dữ liệu máy này vào thư mục chung: thêm {st['ho_so']} hồ sơ, chép {st['file']} file còn thiếu. "
                    f"Bản trước khi gộp đã sao lưu trong _SAO_LUU.")
        widgets.info(self, "Đã đổi thư mục dữ liệu", f"Phần mềm sẽ lưu và đọc dữ liệu tại:\n{self.store.base_dir}{more}")

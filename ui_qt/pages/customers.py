"""Trang Khách hàng: danh sách khách, thông tin và mẫu chứng từ của từng khách."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from .. import widgets
from ._base import _Page, _fill, _head, _table


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
            from ..dialogs import LearnFilesDialog
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
        from ..dialogs import LearnCustomerDialog
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
            from ..pages_kho import add_template_to_kho
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

"""Kho mẫu chung: mẫu Word/Excel dùng lại giữa các khách (đặt tên <LOẠI>_<Khách>_<số>, VD PLX_Arizon_01). Có xem mẫu ngay trong phần mềm."""

import os

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPen
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


# màu viền thẻ theo loại chứng từ (giống bảng băng chuyền mẫu)
CARD_COLOR = {"PLX": "#8B5CF6", "BBGH": "#10B981", "PO": "#3B82F6", "BDC": "#F59E0B", "DNTT": "#F43F5E", "DCCN": "#06B6D4", "KHAC": "#64748B"}


class CoverFlow(QWidget):
    """Băng chuyền 3D các mẫu chứng từ: thẻ giữa lớn, hai bên nghiêng nhỏ dần. Nút ❮ ❯, phím mũi tên, bấm thẻ bên cạnh, bánh xe chuột.
    `set_cards([{title, code, color, lines, foot}])`; phát `current_changed(index)` khi đổi thẻ."""

    current_changed = Signal(int)
    CARD_W, CARD_H = 230, 250

    def __init__(self):
        super().__init__()
        self.cards, self.index, self.pos = [], 0, 0.0
        self.setMinimumHeight(290)
        self.setFocusPolicy(Qt.StrongFocus)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(380)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._tick)
        self.left = QPushButton("❮", self)
        self.right = QPushButton("❯", self)
        for b, step in ((self.left, -1), (self.right, 1)):
            b.setObjectName("sec")
            b.setFixedSize(40, 40)
            b.setFocusPolicy(Qt.NoFocus)
            b.setAccessibleName("Mẫu trước" if step < 0 else "Mẫu sau")
            b.clicked.connect(lambda _=False, st=step: self.step(st))

    def set_cards(self, cards, index=0):
        self.cards = list(cards)
        self.index = max(0, min(index, len(self.cards) - 1)) if self.cards else 0
        self.pos = float(self.index)
        self.anim.stop()
        self.left.setEnabled(len(self.cards) > 1)
        self.right.setEnabled(len(self.cards) > 1)
        self.update()

    def set_current(self, i, animate=True):
        if not self.cards or not (0 <= i < len(self.cards)) or i == self.index and abs(self.pos - i) < 1e-6:
            return
        self.index = i
        self.anim.stop()
        if animate:
            self.anim.setStartValue(float(self.pos))
            self.anim.setEndValue(float(i))
            self.anim.start()
        else:
            self.pos = float(i)
            self.update()
        self.current_changed.emit(i)

    def step(self, d):
        if self.cards:
            self.set_current((self.index + d) % len(self.cards))

    def _tick(self, v):
        self.pos = float(v)
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        y = (self.height() - self.left.height()) // 2
        self.left.move(8, y)
        self.right.move(self.width() - self.right.width() - 8, y)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Left:
            self.step(-1)
        elif e.key() == Qt.Key_Right:
            self.step(1)
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        self.step(-1 if e.angleDelta().y() > 0 else 1)

    # --- hình học: thẻ càng xa tâm càng nhỏ, hẹp (giả nghiêng quanh trục dọc), mờ và lùi ra sau
    def _geom(self, off):
        a = abs(off)
        scale = 1.0 - 0.16 * min(a, 1) - 0.14 * max(0.0, min(a - 1, 1))
        squeeze = 1.0 - 0.18 * min(a, 1) - 0.10 * max(0.0, min(a - 1, 1))
        spread = min(self.width() * 0.26, 205)
        x = self.width() / 2 + (spread * min(a, 1) + spread * 0.5 * max(0.0, min(a - 1, 1))) * (1 if off > 0 else -1 if off < 0 else 0)
        opacity = 1.0 - 0.35 * min(a, 1) - 0.45 * max(0.0, min(a - 1, 1))
        return x, scale, squeeze, max(0.0, opacity)

    def _card_rect(self, off):
        x, scale, squeeze, _ = self._geom(off)
        w, h = self.CARD_W * scale * squeeze, self.CARD_H * scale
        return QRectF(x - w / 2, (self.height() - 22) / 2 - h / 2, w, h)

    def card_at(self, pt):
        order = sorted(range(len(self.cards)), key=lambda i: abs(i - self.pos))
        for i in order:  # gần tâm trước (nằm trên cùng)
            if self._card_rect(i - self.pos).contains(pt):
                return i
        return None

    def mousePressEvent(self, e):
        self.setFocus()
        i = self.card_at(e.position())
        if i is not None and i != self.index:
            self.set_current(i)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        if not self.cards:
            p.setPen(QColor("#64748B"))
            p.drawText(self.rect(), Qt.AlignCenter, "Kho chưa có mẫu nào. Bấm “Nạp mẫu mới vào kho”.")
            return
        for i in sorted(range(len(self.cards)), key=lambda i: -abs(i - self.pos)):  # xa vẽ trước, gần tâm vẽ sau
            off = i - self.pos
            if abs(off) > 2.6:
                continue
            x, scale, squeeze, opacity = self._geom(off)
            p.save()
            p.setOpacity(opacity)
            p.translate(x, (self.height() - 22) / 2)
            p.scale(scale * squeeze, scale)
            self._draw_card(p, self.cards[i], i, abs(off) < 0.5)
            p.restore()
        p.setOpacity(1)
        n, y = len(self.cards), self.height() - 9  # dấu chấm tròn bên dưới
        for i in range(n):
            on = i == self.index
            w = 22 if on else 7
            cx = self.width() / 2 + (i - (n - 1) / 2) * 14
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#4F46E5") if on else QColor("#CBD5E1"))
            p.drawRoundedRect(QRectF(cx - w / 2, y - 3.5, w, 7), 3.5, 3.5)

    def _draw_card(self, p, card, i, front):
        w, h = self.CARD_W, self.CARD_H
        body = QRectF(-w / 2, -h / 2, w, h)
        shadow = QPainterPath()
        shadow.addRoundedRect(body.translated(0, 5), 14, 14)
        p.fillPath(shadow, QColor(15, 23, 42, 55))
        path = QPainterPath()
        path.addRoundedRect(body, 14, 14)
        p.fillPath(path, QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#E2E8F0"), 1))
        p.drawPath(path)
        p.save()
        p.setClipPath(path)
        p.fillRect(QRectF(body.left(), body.top(), w, 7), QColor(card.get("color", "#64748B")))
        p.restore()
        f = QFont(self.font())
        f.setPointSizeF(8)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(card.get("color", "#64748B")))
        p.drawText(QRectF(body.left() + 14, body.top() + 16, w - 28, 16), Qt.AlignLeft | Qt.AlignVCenter, card.get("code", ""))
        f.setPointSizeF(11.5)
        p.setFont(f)
        p.setPen(QColor("#0F172A"))
        p.drawText(QRectF(body.left() + 14, body.top() + 36, w - 28, 48), Qt.AlignLeft | Qt.TextWordWrap, card.get("title", ""))
        p.setPen(QPen(QColor("#E2E8F0"), 1, Qt.DashLine))
        p.drawLine(body.left() + 14, body.top() + 92, body.right() - 14, body.top() + 92)
        f.setPointSizeF(8)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#64748B"))
        p.drawText(QRectF(body.left() + 14, body.top() + 98, w - 28, 14), Qt.AlignLeft, "Các ô dữ liệu trên mẫu:")
        p.setPen(QColor("#334155"))
        y = body.top() + 118
        for line in card.get("lines", [])[:5]:
            p.drawText(QRectF(body.left() + 14, y, w - 28, 14), Qt.AlignLeft | Qt.AlignVCenter, "• " + line)
            y += 17
        foot = QRectF(body.left() + 12, body.bottom() - 36, w - 24, 26)
        p.setPen(QPen(QColor("#E2E8F0"), 1))
        p.setBrush(QColor("#F8FAFC"))
        p.drawRoundedRect(foot, 8, 8)
        p.setPen(QColor("#64748B"))
        p.drawText(foot.adjusted(10, 0, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, card.get("foot", ""))
        p.setPen(QColor("#4F46E5"))
        p.drawText(foot.adjusted(10, 0, -10, 0), Qt.AlignRight | Qt.AlignVCenter, "Đang xem ●" if front else "Bấm để xem")


def kho_cards(items):
    """Nội dung thẻ băng chuyền cho các mẫu trong kho."""
    import mau_rieng
    desc = dict(mau_rieng.TOKENS) | dict(mau_rieng.ITEM_TOKENS)
    out = []
    for n, it in enumerate(items, 1):
        out.append({"code": f"{it['loai']} • {loai_text(it['loai']).upper()}", "title": f"{os.path.splitext(it['file'])[0]}", "color": CARD_COLOR.get(it["loai"], "#64748B"),
                    "lines": [desc.get(t, t) for t in it["tokens"][:5]] or ["(chưa có ô thay thế)"],
                    "foot": f"{ext_text(it['ext'])} · {len(it['tokens'])} ô"})
    return out


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
    """Chọn mẫu trong kho bằng băng chuyền 3D kèm khung xem mẫu; nút "Chọn mẫu này" tích/bỏ tích (dùng ở bước chọn chứng từ riêng khi tạo khách mới)."""

    def __init__(self, core, store, khach_label=lambda: ""):
        super().__init__()
        self.core, self.store, self.khach_label = core, store, khach_label
        self.chosen = set()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.flow = CoverFlow()
        self.flow.setMinimumHeight(270)
        self.flow.current_changed.connect(self.on_row)
        lay.addWidget(self.flow)
        row = QHBoxLayout()
        self.pick_btn = QPushButton("✔  Chọn mẫu này cho khách")
        self.pick_btn.clicked.connect(self.toggle_current)
        self.add_btn = QPushButton("📎  Nạp file mẫu Word/Excel mới…")
        self.add_btn.setObjectName("sec")
        self.add_btn.clicked.connect(self.add_new)
        row.addWidget(self.pick_btn)
        row.addWidget(self.add_btn)
        self.chosen_label = QLabel("")
        self.chosen_label.setObjectName("hint")
        self.chosen_label.setWordWrap(True)
        row.addWidget(self.chosen_label, 1)
        lay.addLayout(row)
        self.preview = TemplatePreview()
        self.preview.setMaximumHeight(180)
        lay.addWidget(self.preview)
        self.items = []
        self.refresh()

    def refresh(self, check=()):
        self.chosen |= set(check)
        self.items = self.store.kho_list()
        self.chosen &= {it["file"] for it in self.items}
        keep = self.flow.index if self.flow.cards else 0
        self.flow.set_cards(kho_cards(self.items), keep)
        self._sync()
        self.on_row(self.flow.index)

    def selected(self):
        return [it["file"] for it in self.items if it["file"] in self.chosen]

    def toggle(self, name):
        self.chosen ^= {name}
        self._sync()

    def toggle_current(self):
        if self.items:
            self.toggle(self.items[self.flow.index]["file"])

    def _sync(self):
        cur = self.items[self.flow.index]["file"] if self.items else ""
        self.pick_btn.setText("✖  Bỏ chọn mẫu này" if cur in self.chosen else "✔  Chọn mẫu này cho khách")
        self.pick_btn.setEnabled(bool(self.items))
        names = ", ".join(os.path.splitext(n)[0] for n in self.selected())
        self.chosen_label.setText(f"Đã chọn: {names}" if names else "Chưa chọn mẫu nào (có thể bỏ qua, thêm sau ở tab Kho mẫu).")

    def on_row(self, i):
        self._sync()
        if 0 <= i < len(self.items):
            it = self.items[i]
            self.preview.show_template(self.core, it["ext"], self.store.kho_read(it["file"]), it["tokens"], it["unknown"])
        else:
            self.preview.clear()

    def add_new(self, path=None):
        name = add_template_to_kho(self, self.store, self.khach_label(), path if isinstance(path, str) else None)
        if name:
            self.refresh(check=[name])
            self.flow.set_current([it["file"] for it in self.items].index(name), animate=False)
            self.on_row(self.flow.index)


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
        self.flow = CoverFlow()
        self.flow.current_changed.connect(self.on_flow)
        lay.addWidget(self.flow)
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
        self.flow.set_cards(kho_cards(self.items), names.index(select) if select in names else 0)
        if select in names:
            self.table.selectRow(names.index(select))
        self.on_select()

    def current(self):
        rows = self.table.selectionModel().selectedRows()
        return self.items[rows[0].row()] if rows and rows[0].row() < len(self.items) else None

    def on_flow(self, i):
        """Đổi thẻ băng chuyền thì chọn đúng dòng trong bảng (và ngược lại ở on_select)."""
        if 0 <= i < self.table.rowCount() and not (self.table.selectionModel().selectedRows() and self.table.selectionModel().selectedRows()[0].row() == i):
            self.table.selectRow(i)

    def on_select(self):
        it = self.current()
        if it and self.flow.cards and self.flow.index != self.items.index(it):
            self.flow.set_current(self.items.index(it))
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

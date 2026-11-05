"""Kho mẫu chung: mẫu Word/Excel dùng lại giữa các khách (đặt tên <LOẠI>_<Khách>_<số>, VD PLX_Arizon_01). Có xem mẫu ngay trong phần mềm."""

import os
import re

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QGraphicsDropShadowEffect, QPlainTextEdit,
    QPushButton, QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
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
        img = card.get("image")
        if img is not None and not img.isNull():  # thẻ có hình mẫu: tiêu đề một dòng, hình mẫu chiếm phần giữa (cắt theo chiều cao thẻ)
            p.drawText(QRectF(body.left() + 14, body.top() + 34, w - 28, 20), Qt.AlignLeft | Qt.AlignVCenter, card.get("title", ""))
            area = QRectF(body.left() + 12, body.top() + 60, w - 24, h - 60 - 46)
            sc = area.width() / img.width()
            p.save()
            p.setClipRect(area)
            p.setPen(QPen(QColor("#E2E8F0"), 1))
            p.fillRect(area, QColor("#FFFFFF"))
            p.drawImage(QRectF(area.left(), area.top(), area.width(), min(area.height(), img.height() * sc)), img,
                        QRectF(0, 0, img.width(), min(img.height(), area.height() / sc)))
            p.restore()
            p.drawRect(area)
            self._draw_foot(p, card, body, w, front)
            return
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
        self._draw_foot(p, card, body, w, front)

    def _draw_foot(self, p, card, body, w, front):
        foot = QRectF(body.left() + 12, body.bottom() - 36, w - 24, 26)
        p.setPen(QPen(QColor("#E2E8F0"), 1))
        p.setBrush(QColor("#F8FAFC"))
        p.drawRoundedRect(foot, 8, 8)
        f = QFont(self.font())
        f.setPointSizeF(8)
        p.setFont(f)
        p.setPen(QColor("#64748B"))
        p.drawText(foot.adjusted(10, 0, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, card.get("foot", ""))
        p.setPen(QColor("#4F46E5"))
        p.drawText(foot.adjusted(10, 0, -10, 0), Qt.AlignRight | Qt.AlignVCenter, "Đang xem ●" if front else "Bấm để xem")


_IMG_CACHE = {}


def template_image(store, it, width=900):
    """Hình ảnh mẫu (QImage), nhớ theo (file, thời điểm sửa) để không vẽ lại mỗi lần. Lỗi thì trả QImage rỗng."""
    from . import mau_render
    try:
        key = (it["path"], os.path.getmtime(it["path"]), width)
    except OSError:
        return QImage()
    if key not in _IMG_CACHE:
        try:
            with open(it["path"], "rb") as f:
                _IMG_CACHE[key] = mau_render.render_template(it["ext"], f.read(), width)
        except Exception:  # noqa: BLE001 - mẫu hỏng: thẻ hiện không hình
            _IMG_CACHE[key] = QImage()
        if len(_IMG_CACHE) > 40:
            _IMG_CACHE.pop(next(iter(_IMG_CACHE)))
    return _IMG_CACHE[key]


def kho_cards(items, store=None):
    """Nội dung thẻ băng chuyền cho các mẫu trong kho. Có `store` thì thẻ hiện HÌNH ảnh của mẫu; không thì hiện danh sách ô dữ liệu."""
    import mau_rieng
    desc = dict(mau_rieng.TOKENS) | dict(mau_rieng.ITEM_TOKENS)
    out = []
    for it in items:
        card = {"code": f"{it['loai']} • {loai_text(it['loai']).upper()}", "title": os.path.splitext(it["file"])[0], "color": CARD_COLOR.get(it["loai"], "#64748B"),
                "lines": [desc.get(t, t) for t in it["tokens"][:5]] or ["(chưa có ô thay thế)"], "foot": f"{ext_text(it['ext'])} · {len(it['tokens'])} ô"}
        if store is not None:
            card["image"] = template_image(store, it, 420)
        out.append(card)
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


class DetectDialog(QDialog):
    """Nạp chứng từ đã điền sẵn thành mẫu: phần mềm nhận ra các chỗ có thể thay đổi (số PO, hóa đơn, ngày, tên hàng, bảng hàng…) và ĐỀ XUẤT ô thay thế;
    người dùng quyết định chỗ nào thành ô. Excel nhiều sheet: mỗi sheet tích chọn thành một mẫu riêng. Kết quả: `names` (các mẫu đã vào kho)."""

    KEEP, DROP = "(giữ nguyên)", "(xóa dòng)"

    def __init__(self, core, store, path, khach_label="Chung", parent=None):
        super().__init__(parent)
        import mau_detect
        import mau_rieng
        self.core, self.store, self.md, self.mr = core, store, mau_detect, mau_rieng
        self.path, self.names = path, []
        self.ext = os.path.splitext(path)[1].lower().lstrip(".")
        with open(path, "rb") as f:
            self.data = f.read()
        self.setWindowTitle("Nạp mẫu vào kho — phân tích chứng từ")
        self.resize(1360, 820)
        self.khach = QLineEdit(khach_label)
        self.ctx = store.detect_context(khach_label)
        lay = QVBoxLayout(self)
        head = QLabel(f"File: {os.path.basename(path)}. Phần mềm đã nhận ra các chỗ có thể thay đổi. Bạn tích chỗ nào muốn thành ô, đổi ô nếu cần; chỗ không tích giữ nguyên chữ.")
        head.setWordWrap(True)
        head.setObjectName("hint")
        lay.addWidget(head)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.pages = []
        names = mau_detect.sheet_names(self.data) if self.ext in ("xlsx", "xlsm") else [""]
        for sh in names:
            pg = self._page(sh)
            self.pages.append(pg)
            self.tabs.addTab(pg["widget"], sh or "Văn bản")
        self.tabs.tabBar().setVisible(len(names) > 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Khách nguồn (đặt tên mẫu):"))
        self.khach.setMaximumWidth(220)
        self.khach.textChanged.connect(self._names)
        row.addWidget(self.khach)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        row.addWidget(self.msg, 1)
        cancel = QPushButton("Hủy")
        cancel.setObjectName("sec")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("📎  Nạp vào kho")
        self.ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self._names()

    def _page(self, sheet):
        from . import mau_render
        w = QWidget()
        h = QHBoxLayout(w)
        left = QVBoxLayout()
        h.addLayout(left, 5)
        top = QHBoxLayout()
        inc = QCheckBox("Nạp thành mẫu")
        inc.setChecked("INVOICE" not in self.md._UP(sheet))  # Invoice dùng chung cho mọi khách nên mặc định không nạp
        inc.toggled.connect(lambda _c: self._names())
        top.addWidget(inc)
        top.addWidget(QLabel("Loại chứng từ:"))
        loai = QComboBox()
        for code, text in LOAI_TEXT.items():
            loai.addItem(f"{code} — {text}", code)
        loai.setCurrentIndex(loai.findData(self.md.guess_loai(sheet or os.path.basename(self.path))))
        loai.currentIndexChanged.connect(lambda _i: self._names())
        top.addWidget(loai)
        name = QLabel("")
        top.addWidget(name)
        top.addStretch(1)
        left.addLayout(top)
        view = ImageView(fit=True)
        try:
            one = self.md.split_sheet(self.data, sheet) if sheet else self.data
            from . import mau_render as mr
            view.show_image(mr.render_template(self.ext, one, 900))
        except Exception as e:  # noqa: BLE001
            view.show_image(None, f"Không vẽ được hình: {e}")
        left.addWidget(view, 1)
        cap = QLabel("Hình mẫu gốc (chưa sửa); bấm vào hình để phóng to. Sau khi nạp, chỗ đã tích thành ô {{…}} tô vàng.")
        cap.setObjectName("hint")
        left.addWidget(cap)
        right = QVBoxLayout()
        h.addLayout(right, 6)
        cands = self.md.detect(self.ext, self.data, self.ctx, sheet or None)
        right.addWidget(QLabel(f"<b>{len(cands)} chỗ máy nhận ra</b> — dòng nền vàng nhạt là chỗ máy chưa rõ là gì, bạn tự chọn ô hoặc để nguyên."))
        table = QTableWidget(len(cands), 5)
        table.setHorizontalHeaderLabels(["Dùng", "Vị trí", "Đang là", "Đổi thành ô", "Vì sao đề xuất"])
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        toks = list(self.mr.TOKENS) + list(self.mr.ITEM_TOKENS)
        combos = []
        for r, d in enumerate(cands):
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            it.setCheckState(Qt.Checked if d["token"] else Qt.Unchecked)
            table.setItem(r, 0, it)
            where = d["where"].replace(" (dòng hàng đầu tiên)", " · dòng hàng").replace(" (dòng tổng cộng)", " · tổng cộng")
            for c, v in ((1, where), (2, d["value"].replace("\n", " ")[:60]), (4, d["why"])):
                table.setItem(r, c, QTableWidgetItem(v))
                if not d["token"]:
                    table.item(r, c).setBackground(QColor("#FEF3C7"))
            cb = QComboBox()
            cb.addItem(self.KEEP, "")
            for k, desc in toks:
                cb.addItem(f"{{{{{k}}}}}  —  {desc}", k)
            if d["kind"] == "drop_rows":
                cb.addItem(self.DROP, "(xóa)")
            cb.setCurrentIndex(max(0, cb.findData(d["token"])))
            cb.currentIndexChanged.connect(lambda _i, row=r, t=table: t.item(row, 0).setCheckState(Qt.Checked if t.cellWidget(row, 3).currentData() else Qt.Unchecked))
            table.setCellWidget(r, 3, cb)
            combos.append(cb)
        right.addWidget(table, 1)
        rr = QHBoxLayout()
        b1 = QPushButton("✔  Tích tất cả gợi ý")
        b1.setObjectName("sec")
        b2 = QPushButton("✖  Bỏ tích hết")
        b2.setObjectName("sec")
        b1.clicked.connect(lambda: [table.item(i, 0).setCheckState(Qt.Checked if cands[i]["token"] else Qt.Unchecked) for i in range(len(cands))])
        b2.clicked.connect(lambda: [table.item(i, 0).setCheckState(Qt.Unchecked) for i in range(len(cands))])
        rr.addWidget(b1)
        rr.addWidget(b2)
        rr.addStretch(1)
        right.addLayout(rr)
        return {"widget": w, "sheet": sheet, "inc": inc, "loai": loai, "name": name, "table": table, "combos": combos, "cands": cands, "view": view}

    def _names(self):
        n = 0
        for pg in self.pages:
            label = f"{pg['loai'].currentData()}_{re.sub(r'[^0-9A-Za-zÀ-ỹ]+', '', self.khach.text()) or 'Chung'}_…"
            pg["name"].setText(f"<b>{label}</b>" if pg["inc"].isChecked() else "<i>(không nạp)</i>")
            n += pg["inc"].isChecked()
        self.ok.setText(f"📎  Nạp {n} mẫu vào kho" if n else "📎  Nạp vào kho")
        self.ok.setEnabled(n > 0)

    def choices(self, pg):
        out = {}
        for i, d in enumerate(pg["cands"]):
            if pg["table"].item(i, 0).checkState() == Qt.Checked and pg["combos"][i].currentData():
                out[d["id"]] = pg["combos"][i].currentData()
        return out

    def accept(self):
        added = []
        for pg in self.pages:
            if not pg["inc"].isChecked():
                continue
            ch = self.choices(pg)
            try:
                if ch:
                    data = self.md.apply(self.ext, self.data, ch, pg["sheet"] or None, self.ctx)
                else:  # không tích chỗ nào: chỉ nạp được nếu file đã có sẵn ô {{...}}
                    data = self.md.split_sheet(self.data, pg["sheet"]) if pg["sheet"] else self.data
                name, _k, _u = self.store.kho_add_bytes(data, self.ext, pg["loai"].currentData(), self.khach.text())
                added.append(name)
            except ValueError as e:
                widgets.warn(self, "Chưa nạp được mẫu", f"{pg['sheet'] or os.path.basename(self.path)}: {e}")
                self.names = added
                return
        self.names = added
        super().accept()


def add_template_to_kho(parent, store, khach_label, path=None):
    """Chọn file Word/Excel rồi mở hộp thoại nhận diện chỗ đổi được; trả danh sách tên mẫu đã nạp vào kho (rỗng nếu hủy)."""
    if not path:
        path, _ = QFileDialog.getOpenFileName(parent, "Chọn file Word/Excel chứng từ hoặc mẫu", "", "Chứng từ (*.docx *.xlsx)")
    if not path:
        return []
    if os.path.splitext(path)[1].lower() not in (".docx", ".xlsx"):
        widgets.warn(parent, "Chưa nạp được mẫu", "Chỉ nhận file Word (.docx) hoặc Excel (.xlsx).")
        return []
    dlg = DetectDialog(None, store, path, khach_label, parent)
    return dlg.names if dlg.exec() else []


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
        self.flow.set_cards(kho_cards(self.items, self.store), keep)
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
        names = add_template_to_kho(self, self.store, self.khach_label(), path if isinstance(path, str) else None)
        if names:
            self.refresh(check=names)
            self.flow.set_current([it["file"] for it in self.items].index(names[0]), animate=False)
            self.on_row(self.flow.index)


class ImageView(QScrollArea):
    """Khung hiện hình mẫu. Mặc định VỪA KHUNG (thấy cả trang); bấm vào hình để phóng to cỡ thật (cuộn được), bấm lần nữa để thu lại."""

    def __init__(self, fit=True):
        super().__init__()
        self.fit = fit
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.label = QLabel("Chọn một mẫu để xem hình.")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background:#E2E8F0")
        self.setWidget(self.label)
        self.image = QImage()
        self.label.mousePressEvent = lambda e: self.toggle_fit()

    def show_image(self, img, note=""):
        self.image = img if img is not None else QImage()
        if self.image.isNull():
            self.label.setPixmap(QPixmap())
            self.label.setText(note or "Không vẽ được hình mẫu này. Bấm “Mở bằng Word/Excel” để xem.")
        else:
            self._apply()

    def _apply(self):
        if self.image.isNull():
            return
        if self.fit:
            vp = self.viewport().size()
            pm = QPixmap.fromImage(self.image).scaled(max(100, vp.width() - 4), max(100, vp.height() - 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pm = QPixmap.fromImage(self.image)
        self.label.setPixmap(pm)
        self.label.setText("")

    def toggle_fit(self):
        self.fit = not self.fit
        self._apply()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit:
            self._apply()

    def clear(self):
        self.image = QImage()
        self.label.setPixmap(QPixmap())
        self.label.setText("Chọn một mẫu để xem hình.")


class PagedView(QScrollArea):
    """Xem như bản in: nền xám, mỗi trang A4 là một tờ giấy trắng có bóng đổ (đầu trang: ngày + tên mẫu; chân trang: tên mẫu + số trang), cuộn qua từng
    trang, ô góc trên phải báo trang đang xem. Zoom: nút ＋ － / Vừa chiều rộng hoặc Ctrl + lăn chuột."""

    PW = 900  # bề ngang trang vẽ sẵn (px); chiều cao theo tỉ lệ A4
    PH = int(900 * 1.4142)
    MARGIN = 44

    def __init__(self):
        super().__init__()
        self.pages, self.zoom, self.labels = [], 1.0, []
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setStyleSheet("QScrollArea{background:#D4D4D4;border:1px solid #9CA3AF}")
        self.host = QWidget()
        self.host.setStyleSheet("background:#D4D4D4")
        self.col = QVBoxLayout(self.host)
        self.col.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.col.setSpacing(14)
        self.col.setContentsMargins(0, 14, 0, 14)
        self.setWidget(self.host)
        self.badge = QLabel("", self)
        self.badge.setStyleSheet("background:rgba(75,85,99,235);color:white;font-weight:700;border-radius:6px;padding:8px 14px")
        self.badge.hide()
        self.verticalScrollBar().valueChanged.connect(self._page_badge)

    def paginate(self, img, title):
        """Xếp hình mẫu lên các trang A4 có lề, đầu trang và chân trang."""
        import datetime
        m = self.MARGIN
        inner = self.PW - 2 * m
        sc = inner / img.width()
        src_h = int((self.PH - 2 * m - 16) / sc)
        n = max(1, -(-img.height() // src_h))
        out = []
        for i in range(n):
            pg = QImage(self.PW, self.PH, QImage.Format_ARGB32)
            pg.fill(QColor("white"))
            p = QPainter(pg)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            part = img.copy(0, i * src_h, img.width(), min(src_h, img.height() - i * src_h))
            p.drawImage(QRectF(m, m + 4, inner, part.height() * sc), part)
            f = QFont()
            f.setPixelSize(11)
            p.setFont(f)
            p.setPen(QColor("#111827"))
            p.drawText(QRectF(m, 12, inner, 16), Qt.AlignLeft, datetime.date.today().strftime("%d/%m/%Y"))
            p.drawText(QRectF(m, 12, inner, 16), Qt.AlignHCenter, title)
            p.drawText(QRectF(m, self.PH - 26, inner, 16), Qt.AlignLeft, "Kho mẫu / " + title)
            p.drawText(QRectF(m, self.PH - 26, inner, 16), Qt.AlignRight, f"{i + 1}/{n}")
            p.end()
            out.append(pg)
        return out

    def show_image(self, img, title=""):
        self.pages = [] if img is None or img.isNull() else self.paginate(img, title)
        self._build()
        self.verticalScrollBar().setValue(0)  # mẫu mới luôn mở từ đầu trang 1

    def clear(self):
        self.pages = []
        self._build()

    def _page_w(self):
        return max(200, int((self.viewport().width() - 40) * self.zoom))

    def _build(self):
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w:
                w.hide()  # ẩn ngay để không còn vệt trang cũ trước khi widget được xóa
                w.deleteLater()
        self.labels = []
        if not self.pages:
            self.col.addWidget(QLabel("Chọn một mẫu để xem."), 0, Qt.AlignHCenter)
        w = self._page_w()
        for pg in self.pages:
            lab = QLabel()
            lab.setPixmap(QPixmap.fromImage(pg).scaledToWidth(w, Qt.SmoothTransformation))
            sh = QGraphicsDropShadowEffect(lab)
            sh.setBlurRadius(18)
            sh.setOffset(0, 3)
            sh.setColor(QColor(0, 0, 0, 110))
            lab.setGraphicsEffect(sh)
            self.col.addWidget(lab, 0, Qt.AlignHCenter)
            self.labels.append(lab)
        self.badge.setVisible(bool(self.pages))
        self._page_badge()

    def set_zoom(self, z):
        self.zoom = max(0.4, min(4.0, z))
        self._build()

    def fit_width(self):
        self.set_zoom(1.0)

    def _page_badge(self, *_):
        if not self.pages:
            return
        y = self.verticalScrollBar().value() + self.viewport().height() // 2
        cur = 0
        for i, lab in enumerate(self.labels):
            if lab.y() <= y:
                cur = i
        self.badge.setText(f"{cur + 1} / {len(self.pages)}")
        self.badge.adjustSize()
        self.badge.move(self.width() - self.badge.width() - 24, 8)
        self.badge.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.pages:
            self._build()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.set_zoom(self.zoom * (1.12 if e.angleDelta().y() > 0 else 1 / 1.12))
        else:
            super().wheelEvent(e)


class EditTemplateDialog(QDialog):
    """Công cụ sửa mẫu: đổi một đoạn chữ/số trong mẫu thành ô {{...}}, xem hình ngay, hoàn tác, lưu; hoặc mở bằng Word/Excel để sửa tự do rồi tải lại."""

    def __init__(self, core, store, name, parent=None):
        super().__init__(parent)
        import mau_rieng
        self.core, self.store, self.name, self.mr = core, store, name, mau_rieng
        self.ext = os.path.splitext(name)[1].lstrip(".")
        self.setWindowTitle(f"Sửa mẫu — {os.path.splitext(name)[0]}")
        self.resize(1100, 720)
        self.data = store.kho_read(name)
        self.history = []
        self.dirty = False
        lay = QHBoxLayout(self)
        self.view = ImageView(fit=False)
        lay.addWidget(self.view, 3)
        side = QVBoxLayout()
        lay.addLayout(side, 2)
        t = QLabel("Đổi chữ trong mẫu thành ô thay thế")
        t.setObjectName("h2")
        side.addWidget(t)
        hint = QLabel("Gõ đúng đoạn chữ (hoặc số) đang có trong mẫu rồi chọn ô sẽ thay vào đó. Ô thay thế được tô vàng trên hình.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        side.addWidget(hint)
        self.find = QLineEdit()
        self.find.setPlaceholderText("Chữ hoặc số cần đổi, ví dụ 21.200.000")
        side.addWidget(self.find)
        self.token = QComboBox()
        for k, d in list(mau_rieng.TOKENS) + list(mau_rieng.ITEM_TOKENS):
            self.token.addItem(f"{{{{{k}}}}}  —  {d}", k)
        side.addWidget(self.token)
        row = QHBoxLayout()
        self.apply_btn = QPushButton("✏  Đổi thành ô")
        self.apply_btn.clicked.connect(self.apply)
        self.undo_btn = QPushButton("↩  Hoàn tác")
        self.undo_btn.setObjectName("sec")
        self.undo_btn.clicked.connect(self.undo)
        row.addWidget(self.apply_btn)
        row.addWidget(self.undo_btn)
        side.addLayout(row)
        t2 = QLabel("Chèn ô thay thế khi sửa bằng Word/Excel")
        t2.setObjectName("h2")
        side.addWidget(t2)
        self.copy_list = QListWidget()
        for k, d in list(mau_rieng.TOKENS) + list(mau_rieng.ITEM_TOKENS):
            li = QListWidgetItem(f"{{{{{k}}}}}  —  {d}")
            li.setData(Qt.UserRole, k)
            self.copy_list.addItem(li)
        self.copy_list.itemDoubleClicked.connect(self.copy_token)
        side.addWidget(self.copy_list, 1)
        self.msg = QLabel("Bấm đúp một ô trong danh sách để chép {{ô}} vào bộ nhớ, rồi dán vào file đang sửa.")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        side.addWidget(self.msg)
        row2 = QHBoxLayout()
        self.open_btn = QPushButton("📂  Mở bằng Word/Excel")
        self.open_btn.setObjectName("sec")
        self.open_btn.clicked.connect(self.open_external)
        self.reload_btn = QPushButton("🔄  Tải lại từ file")
        self.reload_btn.setObjectName("sec")
        self.reload_btn.clicked.connect(self.reload)
        row2.addWidget(self.open_btn)
        row2.addWidget(self.reload_btn)
        side.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addStretch(1)
        cancel = QPushButton("Đóng")
        cancel.setObjectName("sec")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("💾  Lưu vào kho")
        self.save_btn.clicked.connect(self.save)
        row3.addWidget(cancel)
        row3.addWidget(self.save_btn)
        side.addLayout(row3)
        self.redraw()

    def redraw(self):
        from . import mau_render
        try:
            self.view.show_image(mau_render.render_template(self.ext, self.data, 760))
        except Exception as e:  # noqa: BLE001
            self.view.show_image(None, f"Không vẽ được hình: {e}")
        self.undo_btn.setEnabled(bool(self.history))
        self.save_btn.setEnabled(self.dirty)

    def apply(self):
        try:
            data, n = self.mr.replace_text(self.ext, self.data, self.find.text(), self.token.currentData())
        except ValueError as e:
            self.msg.setText(str(e))
            return
        if not n:
            self.msg.setText("Không thấy chữ đó trong mẫu (gõ đúng từng ký tự, kể cả dấu chấm).")
            return
        self.history.append(self.data)
        self.data, self.dirty = data, True
        self.msg.setText(f"Đã đổi {n} chỗ thành {{{{{self.token.currentData()}}}}}. Bấm “Lưu vào kho” để giữ lại.")
        self.find.clear()
        self.redraw()

    def undo(self):
        if self.history:
            self.data = self.history.pop()
            self.dirty = bool(self.history)
            self.msg.setText("Đã hoàn tác một lần đổi.")
            self.redraw()

    def copy_token(self, item):
        QGuiApplication.clipboard().setText("{{" + item.data(Qt.UserRole) + "}}")
        self.msg.setText(f"Đã chép {{{{{item.data(Qt.UserRole)}}}}}: dán vào chỗ cần điền trong file mẫu.")

    def open_external(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(self.store.kho_folder(), self.name)))
        self.msg.setText("Đã mở file bằng Word/Excel. Sửa xong thì lưu file, đóng lại rồi bấm “Tải lại từ file”.")

    def reload(self):
        self.data, self.history, self.dirty = self.store.kho_read(self.name), [], False
        self.msg.setText("Đã tải lại mẫu từ file.")
        self.redraw()

    def save(self):
        known, unknown = self.mr.template_tokens(self.ext, self.data)
        if not known:
            widgets.warn(self, "Chưa lưu được", "Mẫu không còn ô thay thế nào.")
            return
        self.store.kho_write(self.name, self.data)
        self.dirty = False
        self.accept()


class MauPage(QWidget):
    """Tab "Kho mẫu": hình mẫu đang chọn nằm BÊN TRÁI (vừa khung, thấy cả trang), danh sách mẫu BÊN PHẢI (có thanh cuộn). Chỉ để xem;
    có nút Sửa mẫu, Nạp mẫu mới, Mở bằng Word/Excel, Xóa. Việc chọn mẫu cho khách làm ở bước thêm khách mới."""

    def __init__(self, core, store):
        super().__init__()
        self.setObjectName("page")
        self.core, self.store, self.items = core, store, []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(10)
        t = QLabel("Kho mẫu chứng từ")
        t.setObjectName("title")
        h = QLabel("Xem như bản in: chọn một mẫu ở danh sách bên phải. Ô tô vàng là chỗ phần mềm điền số liệu. Cuộn để qua từng trang A4; Ctrl + lăn chuột để zoom. Cần chỉnh thì bấm “Sửa mẫu”.")
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(h)
        body = QHBoxLayout()
        lay.addLayout(body, 1)
        left = QVBoxLayout()
        body.addLayout(left, 3)
        self.title = QLabel("")
        self.title.setObjectName("h2")
        left.addWidget(self.title)
        tools = QHBoxLayout()
        for text, fn in (("－", lambda: self.view.set_zoom(self.view.zoom / 1.2)), ("＋", lambda: self.view.set_zoom(self.view.zoom * 1.2)), ("Vừa chiều rộng", lambda: self.view.fit_width())):
            b = QPushButton(text)
            b.setObjectName("sec")
            b.clicked.connect(fn)
            tools.addWidget(b)
        tools.addStretch(1)
        left.addLayout(tools)
        self.view = PagedView()
        left.addWidget(self.view, 1)
        right = QVBoxLayout()
        body.addLayout(right, 1)
        rt = QLabel("Danh sách mẫu")
        rt.setObjectName("h2")
        right.addWidget(rt)
        self.listw = QListWidget()
        self.listw.setIconSize(QSize(96, 124))
        self.listw.setSpacing(4)
        self.listw.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.listw.currentRowChanged.connect(self.on_row)
        right.addWidget(self.listw, 1)
        self.edit_btn = QPushButton("✏  Sửa mẫu…")
        self.edit_btn.clicked.connect(self.edit)
        self.add_btn = QPushButton("📎  Nạp mẫu mới vào kho…")
        self.add_btn.setObjectName("sec")
        self.add_btn.clicked.connect(self.add_new)
        self.open_btn = QPushButton("📂  Mở bằng Word/Excel")
        self.open_btn.setObjectName("sec")
        self.open_btn.clicked.connect(self.open_file)
        self.del_btn = QPushButton("🗑  Xóa khỏi kho")
        self.del_btn.setObjectName("dng")
        self.del_btn.clicked.connect(self.remove)
        for b in (self.edit_btn, self.add_btn, self.open_btn, self.del_btn):
            right.addWidget(b)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        right.addWidget(self.msg)
        self.on_row(-1)

    def refresh(self, select=None):
        keep = self.listw.currentRow()
        self.items = self.store.kho_list()
        names = [it["file"] for it in self.items]
        self.listw.blockSignals(True)
        self.listw.clear()
        for it in self.items:
            img = template_image(self.store, it, 300)
            icon = QIcon(QPixmap.fromImage(img).scaled(96, 124, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if not img.isNull() else QIcon()
            self.listw.addItem(QListWidgetItem(icon, f"{os.path.splitext(it['file'])[0]}\n{loai_text(it['loai'])} · {ext_text(it['ext'])} · {len(it['tokens'])} ô"))
        self.listw.blockSignals(False)
        row = names.index(select) if select in names else (keep if 0 <= keep < len(names) else (0 if names else -1))
        self.listw.setCurrentRow(row)
        self.on_row(row)

    def current(self):
        i = self.listw.currentRow()
        return self.items[i] if 0 <= i < len(self.items) else None

    def on_row(self, _i):
        it = self.current()
        for b in (self.edit_btn, self.open_btn, self.del_btn):
            b.setEnabled(bool(it))
        if not it:
            self.title.setText("")
            self.view.clear()
            return
        self.title.setText(f"{os.path.splitext(it['file'])[0]}  —  {loai_text(it['loai'])}, {ext_text(it['ext'])}, {len(it['tokens'])} ô thay thế")
        self.view.show_image(template_image(self.store, it, 1000), os.path.splitext(it["file"])[0])

    def add_new(self, path=None):
        names = add_template_to_kho(self, self.store, "Chung", path if isinstance(path, str) else None)
        if names:
            self.msg.setText("✅  Đã nạp vào kho: " + ", ".join(os.path.splitext(n)[0] for n in names) + ".")
            self.refresh(select=names[0])

    def edit(self):
        it = self.current()
        if it and EditTemplateDialog(self.core, self.store, it["file"], self).exec():
            self.msg.setText(f"✅  Đã lưu mẫu “{os.path.splitext(it['file'])[0]}”. Khách đã mượn mẫu này trước đó vẫn giữ bản của họ.")
            self.refresh(select=it["file"])

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

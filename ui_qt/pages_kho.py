"""Kho mẫu chung: mẫu Word/Excel dùng lại giữa các khách (đặt tên <LOẠI>_<Khách>_<số>, VD PLX_Arizon_01). Có xem mẫu ngay trong phần mềm."""

import os
import re

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QTimer, QUrl, QVariantAnimation, Signal
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
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(0))  # mẫu mới luôn mở từ đầu trang 1 (sau khi bố cục xong)

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


class ContentEditor(QWidget):
    """Sửa chữ/số ngay trong phần mềm. Excel: lưới ô theo từng sheet (ô gộp chỉ sửa ô đầu). Word: mỗi dòng một đoạn văn (kể cả đoạn trong bảng).
    Mỗi lần sửa một ô phát `edited(bytes mới)`; định dạng, ô gộp, khung in của file giữ nguyên."""

    edited = Signal(bytes)

    def __init__(self, ext):
        super().__init__()
        import mau_rieng
        self.mr, self.ext, self.data, self.sheets = mau_rieng, ext, b"", []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.sheet = QComboBox()
        self.sheet.currentIndexChanged.connect(self._show_sheet)
        top.addWidget(QLabel("Sheet:" if ext != "docx" else "Các đoạn văn của file Word:"))
        top.addWidget(self.sheet, 1)
        self.sheet.setVisible(ext != "docx")
        lay.addLayout(top)
        self.grid = QTableWidget(0, 0)
        self.grid.setWordWrap(True)
        self.grid.itemChanged.connect(self._changed)
        lay.addWidget(self.grid, 1)

    def load(self, data):
        self.data = data
        self.grid.blockSignals(True)
        if self.ext == "docx":
            paras = self.mr.docx_paragraphs(data)
            self.grid.clear()
            self.grid.setColumnCount(1)
            self.grid.setRowCount(len(paras))
            self.grid.setHorizontalHeaderLabels(["Đoạn văn (bấm đúp để sửa)"])
            self.grid.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            for i, t in enumerate(paras):
                self.grid.setItem(i, 0, QTableWidgetItem(t))
            self.grid.resizeRowsToContents()
        else:
            keep = self.sheet.currentIndex()
            self.sheets = self.mr.xlsx_cells(data)
            self.sheet.blockSignals(True)
            self.sheet.clear()
            self.sheet.addItems([sh["sheet"] for sh in self.sheets])
            self.sheet.setCurrentIndex(keep if 0 <= keep < len(self.sheets) else 0)
            self.sheet.blockSignals(False)
            self._show_sheet()
        self.grid.blockSignals(False)

    def _show_sheet(self, *_):
        from openpyxl.utils import get_column_letter
        i = self.sheet.currentIndex()
        if not (0 <= i < len(self.sheets)):
            return
        sh = self.sheets[i]
        rows = sh["rows"]
        nc = max((len(r) for r in rows), default=0)
        self.grid.blockSignals(True)
        self.grid.clear()
        self.grid.setRowCount(len(rows))
        self.grid.setColumnCount(nc)
        self.grid.setHorizontalHeaderLabels([get_column_letter(c + 1) for c in range(nc)])
        for r, row in enumerate(rows):
            for c in range(nc):
                it = QTableWidgetItem(row[c] if c < len(row) else "")
                if it.text():
                    it.setToolTip(it.text())
                if (r + 1, c + 1) in sh["merged"]:
                    it.setFlags(Qt.ItemIsEnabled)
                    it.setBackground(QColor("#EEF2F7"))
                elif "{{" in it.text():
                    it.setBackground(QColor("#FEF3C7"))
                self.grid.setItem(r, c, it)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for c in range(nc):
            self.grid.setColumnWidth(c, 140)
        self.grid.blockSignals(False)

    def _changed(self, item):
        if self.ext == "docx":
            data = self.mr.set_docx_paragraphs(self.data, {item.row(): item.text()})
        else:
            sh = self.sheets[self.sheet.currentIndex()]
            data = self.mr.set_xlsx_cells(self.data, {(sh["sheet"], item.row() + 1, item.column() + 1): item.text()})
            row = sh["rows"][item.row()]
            while len(row) <= item.column():
                row.append("")
            row[item.column()] = item.text()
        self.data = data
        self.grid.blockSignals(True)
        item.setBackground(QColor("#FEF3C7") if "{{" in item.text() else QColor("white"))
        self.grid.blockSignals(False)
        self.edited.emit(data)

    def insert_token(self, token):
        """Chèn {{ô}} vào cuối ô / đoạn đang chọn. Trả False nếu chưa chọn ô nào."""
        it = self.grid.currentItem()
        if it is None or not (it.flags() & Qt.ItemIsEditable):
            return False
        it.setText((it.text() + " " if it.text() and not it.text().endswith(" ") else it.text()) + "{{" + token + "}}")
        return True


class EditTemplateDialog(QDialog):
    """Sửa mẫu ngay trong phần mềm: tab "Xem như bản in" và tab "Sửa chữ / số" (sửa từng ô Excel hoặc từng đoạn Word);
    đổi một đoạn chữ thành ô {{...}}, chèn ô vào chỗ đang chọn, hoàn tác, lưu. Vẫn mở được bằng Word/Excel để sửa định dạng rồi tải lại.
    `path`: file form / mẫu riêng của khách (lưu qua store.doc_write, có bản gốc); không có thì là mẫu `name` trong kho chung."""

    def __init__(self, core, store, name, parent=None, path=None, title=None):
        super().__init__(parent)
        import mau_rieng
        self.core, self.store, self.name, self.mr, self.path = core, store, name, mau_rieng, path
        self.ext = os.path.splitext(path or name)[1].lstrip(".").lower()
        self.setWindowTitle(f"Sửa mẫu — {title or os.path.splitext(name)[0]}")
        self.resize(1200, 760)
        self.data = self._read()
        self.history = []
        self.dirty = False
        lay = QHBoxLayout(self)
        self.tabs = QTabWidget()
        self.view = ImageView(fit=False)
        self.content = ContentEditor(self.ext)
        self.content.edited.connect(self._content_edited)
        self.tabs.addTab(self.view, "🖼  Xem như bản in")
        self.tabs.addTab(self.content, "✏  Sửa chữ / số")
        self.tabs.currentChanged.connect(lambda i: self.redraw() if i == 0 else None)
        lay.addWidget(self.tabs, 3)
        side = QVBoxLayout()
        lay.addLayout(side, 2)
        t = QLabel("Đổi chữ trong mẫu thành ô thay thế")
        t.setObjectName("h2")
        side.addWidget(t)
        hint = QLabel("Ô thay thế {{...}} là chỗ phần mềm tự điền số liệu của lô khi xuất. Gõ đúng đoạn chữ (hoặc số) đang có trong mẫu rồi chọn ô sẽ thay vào đó; "
                      "hoặc chọn một ô ở tab “Sửa chữ / số” rồi bấm “Chèn vào ô đang chọn”.")
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
        self.insert_btn = QPushButton("➕  Chèn vào ô đang chọn")
        self.insert_btn.setObjectName("sec")
        self.insert_btn.clicked.connect(self.insert)
        row.addWidget(self.apply_btn)
        row.addWidget(self.insert_btn)
        side.addLayout(row)
        self.undo_btn = QPushButton("↩  Hoàn tác")
        self.undo_btn.setObjectName("sec")
        self.undo_btn.clicked.connect(self.undo)
        side.addWidget(self.undo_btn)
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
        self.save_btn = QPushButton("💾  Lưu mẫu" if path else "💾  Lưu vào kho")
        self.save_btn.clicked.connect(self.save)
        row3.addWidget(cancel)
        row3.addWidget(self.save_btn)
        side.addLayout(row3)
        self.content.load(self.data)
        self.redraw()

    def _read(self):
        return self.store.doc_read(self.path) if self.path else self.store.kho_read(self.name)

    def _file(self):
        return self.path or os.path.join(self.store.kho_folder(), self.name)

    def redraw(self):
        from . import mau_render
        try:
            self.view.show_image(mau_render.render_template(self.ext, self.data, 760))
        except Exception as e:  # noqa: BLE001
            self.view.show_image(None, f"Không vẽ được hình: {e}")
        self.undo_btn.setEnabled(bool(self.history))
        self.save_btn.setEnabled(self.dirty)

    def _set_data(self, data, reload_content=True):
        self.history.append(self.data)
        self.data, self.dirty = data, True
        if reload_content:
            self.content.load(data)
        self.redraw()

    def _content_edited(self, data):
        self.history.append(self.data)
        self.data, self.dirty = data, True
        self.undo_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.msg.setText("Đã sửa. Bấm “Lưu mẫu” để các lần xuất sau dùng nội dung mới." if self.path else "Đã sửa. Bấm “Lưu vào kho” để giữ lại.")

    def apply(self):
        try:
            data, n = self.mr.replace_text(self.ext, self.data, self.find.text(), self.token.currentData())
        except ValueError as e:
            self.msg.setText(str(e))
            return
        if not n:
            self.msg.setText("Không thấy chữ đó trong mẫu (gõ đúng từng ký tự, kể cả dấu chấm).")
            return
        self._set_data(data)
        self.msg.setText(f"Đã đổi {n} chỗ thành {{{{{self.token.currentData()}}}}}. Bấm “{self.save_btn.text().split('  ')[-1]}” để giữ lại.")
        self.find.clear()

    def insert(self):
        if self.tabs.currentWidget() is not self.content or not self.content.insert_token(self.token.currentData()):
            self.tabs.setCurrentWidget(self.content)
            self.msg.setText("Chọn một ô (Excel) hoặc một đoạn (Word) ở tab “Sửa chữ / số” rồi bấm lại “Chèn vào ô đang chọn”.")

    def undo(self):
        if self.history:
            self.data = self.history.pop()
            self.dirty = bool(self.history)
            self.content.load(self.data)
            self.msg.setText("Đã hoàn tác một lần sửa.")
            self.redraw()

    def copy_token(self, item):
        QGuiApplication.clipboard().setText("{{" + item.data(Qt.UserRole) + "}}")
        self.msg.setText(f"Đã chép {{{{{item.data(Qt.UserRole)}}}}}: dán vào chỗ cần điền trong file mẫu.")

    def open_external(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._file()))
        self.msg.setText("Đã mở file bằng Word/Excel. Sửa xong thì lưu file, đóng lại rồi bấm “Tải lại từ file”.")

    def reload(self):
        self.data, self.history, self.dirty = self._read(), [], False
        self.content.load(self.data)
        self.msg.setText("Đã tải lại mẫu từ file.")
        self.redraw()

    def save(self):
        known, unknown = self.mr.template_tokens(self.ext, self.data)
        if not self.path and not known:
            widgets.warn(self, "Chưa lưu được", "Mẫu không còn ô thay thế nào.")
            return
        if self.path:
            self.store.doc_write(self.path, self.data)
        else:
            self.store.kho_write(self.name, self.data)
        self.dirty = False
        self.accept()


KIND_TEXT = {"form": "Form đã sửa", "rieng": "Mẫu riêng Word/Excel", "builtin": "Mẫu dựng sẵn", "bkav": "File nạp Bkav", "fixed": "Mẫu dựng sẵn"}
KIND_HINT = {
    "form": "Chứng từ này đang xuất theo form đã sửa ở đây. Sửa xong bấm Lưu: các lần xuất sau dùng ngay nội dung mới.",
    "rieng": "Mẫu riêng Word/Excel của khách. Sửa xong bấm Lưu: các lần xuất sau dùng ngay nội dung mới.",
    "builtin": "Chứng từ đang do phần mềm dựng sẵn. Bấm “Chuyển thành form để sửa” để có file Excel/Word sửa được; từ đó xuất theo form, "
               "bỏ form thì quay lại mẫu dựng sẵn. Hình bên trái là form sẽ tạo ra (ô tô vàng là chỗ phần mềm điền).",
    "bkav": "Hóa đơn VAT / Phiếu xuất kho là file để nạp vào Bkav, phải giữ đúng định dạng Bkav nên không sửa form ở đây.",
    "fixed": "Chứng từ này phần mềm tự dựng theo số liệu riêng (không đổi thành form được).",
}


class MauPage(QWidget):
    """Tab "Kho mẫu": nơi xem và sửa form chứng từ.
    Cột trái: "Kho chung" (mẫu dùng lại giữa các khách) và từng khách trong hệ thống (Deli Hải Dương / Bắc Ninh là hai khách riêng).
    Giữa: hình chứng từ như bản in. Phải: danh sách mẫu / chứng từ của mục đang chọn và các nút sửa.
    Sửa chứng từ của khách thì các lần xuất sau dùng form đã sửa; lần sửa đầu có cất bản gốc để khôi phục."""

    def __init__(self, core, store):
        super().__init__()
        self.setObjectName("page")
        self.core, self.store, self.items, self.docs = core, store, [], []
        self.cust = None  # None = Kho chung; khác = mã khách đang xem
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(10)
        t = QLabel("Kho mẫu chứng từ")
        t.setObjectName("title")
        h = QLabel("Chọn một khách ở cột trái để xem và sửa chứng từ của khách đó (sửa xong, các lần xuất sau dùng form mới). “Kho chung” là các mẫu dùng lại giữa các khách. "
                   "Ô tô vàng là chỗ phần mềm điền số liệu. Ctrl + lăn chuột để zoom.")
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(h)
        body = QHBoxLayout()
        lay.addLayout(body, 1)
        cl = QVBoxLayout()
        body.addLayout(cl, 0)
        ct = QLabel("Khách hàng")
        ct.setObjectName("h2")
        cl.addWidget(ct)
        self.custs = QListWidget()
        self.custs.setFixedWidth(210)
        self.custs.currentRowChanged.connect(self.on_cust)
        cl.addWidget(self.custs, 1)
        left = QVBoxLayout()
        body.addLayout(left, 3)
        self.title = QLabel("")
        self.title.setObjectName("h2")
        self.title.setWordWrap(True)
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
        self.list_title = QLabel("Danh sách mẫu")
        self.list_title.setObjectName("h2")
        right.addWidget(self.list_title)
        self.listw = QListWidget()
        self.listw.setIconSize(QSize(96, 124))
        self.listw.setSpacing(4)
        self.listw.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.listw.currentRowChanged.connect(self.on_row)
        right.addWidget(self.listw, 1)
        self.kind_hint = QLabel("")
        self.kind_hint.setObjectName("hint")
        self.kind_hint.setWordWrap(True)
        right.addWidget(self.kind_hint)
        self.conv_btn = QPushButton("🧩  Chuyển thành form để sửa")
        self.conv_btn.clicked.connect(self.convert)
        self.edit_btn = QPushButton("✏  Sửa mẫu…")
        self.edit_btn.clicked.connect(self.edit)
        self.add_btn = QPushButton("📎  Nạp mẫu mới vào kho…")
        self.add_btn.setObjectName("sec")
        self.add_btn.clicked.connect(self.add_new)
        self.open_btn = QPushButton("📂  Mở bằng Word/Excel")
        self.open_btn.setObjectName("sec")
        self.open_btn.clicked.connect(self.open_file)
        self.restore_btn = QPushButton("↺  Khôi phục bản gốc")
        self.restore_btn.setObjectName("sec")
        self.restore_btn.clicked.connect(self.restore)
        self.drop_btn = QPushButton("⟲  Dùng lại mẫu dựng sẵn")
        self.drop_btn.setObjectName("sec")
        self.drop_btn.clicked.connect(self.drop)
        self.del_btn = QPushButton("🗑  Xóa khỏi kho")
        self.del_btn.setObjectName("dng")
        self.del_btn.clicked.connect(self.remove)
        for b in (self.conv_btn, self.edit_btn, self.add_btn, self.open_btn, self.restore_btn, self.drop_btn, self.del_btn):
            right.addWidget(b)
        self.msg = QLabel("")
        self.msg.setObjectName("hint")
        self.msg.setWordWrap(True)
        right.addWidget(self.msg)
        self._fill_custs()
        self.on_row(-1)

    # ---- cột khách -----------------------------------------------------------------------------------------
    def _fill_custs(self):
        keep = self.cust
        self.custs.blockSignals(True)
        self.custs.clear()
        li = QListWidgetItem("📦  Kho chung")
        li.setData(Qt.UserRole, None)
        self.custs.addItem(li)
        profs = self.core.PROFILES
        keys = [k for k in self.core.BUILTIN_CUSTOMERS if k in profs] + sorted((k for k in profs if k not in self.core.BUILTIN_CUSTOMERS), key=lambda k: str(profs[k].get("label") or k).lower())
        for k in keys:
            li = QListWidgetItem(f"👤  {profs[k].get('label') or k}")
            li.setData(Qt.UserRole, k)
            li.setToolTip(str(profs[k].get("name") or ""))
            self.custs.addItem(li)
        row = next((i for i in range(self.custs.count()) if self.custs.item(i).data(Qt.UserRole) == keep), 0)
        self.custs.setCurrentRow(row)
        self.custs.blockSignals(False)
        self.cust = self.custs.item(row).data(Qt.UserRole)

    def select_customer(self, key):
        for i in range(self.custs.count()):
            if self.custs.item(i).data(Qt.UserRole) == key:
                self.custs.setCurrentRow(i)
                return True
        return False

    def on_cust(self, i):
        self.cust = self.custs.item(i).data(Qt.UserRole) if 0 <= i < self.custs.count() else None
        self.msg.setText("")
        self.refresh()

    # ---- danh sách bên phải ------------------------------------------------------------------------------------
    def refresh(self, select=None):
        if self.custs.count() != len(self.core.PROFILES) + 1:
            self._fill_custs()
        keep = self.listw.currentRow()
        self.listw.blockSignals(True)
        self.listw.clear()
        if self.cust is None:
            self.list_title.setText("Danh sách mẫu")
            self.docs = []
            self.items = self.store.kho_list()
            names = [it["file"] for it in self.items]
            for it in self.items:
                img = template_image(self.store, it, 300)
                icon = QIcon(QPixmap.fromImage(img).scaled(96, 124, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if not img.isNull() else QIcon()
                self.listw.addItem(QListWidgetItem(icon, f"{os.path.splitext(it['file'])[0]}\n{loai_text(it['loai'])} · {ext_text(it['ext'])} · {len(it['tokens'])} ô"))
        else:
            label = self.core.PROFILES.get(self.cust, {}).get("label") or self.cust
            self.list_title.setText(f"Chứng từ của {label}")
            self.items = []
            self.docs = self.store.customer_docs(self.cust)
            names = [d["mode"] for d in self.docs]
            for d in self.docs:
                mark = "✏" if d["kind"] in ("form", "rieng") else ("🔒" if d["kind"] in ("bkav", "fixed") else "⚙")
                self.listw.addItem(QListWidgetItem(f"{mark}  {d['label']}\n{KIND_TEXT[d['kind']]} · {ext_text(d['ext'])}"))
        self.listw.blockSignals(False)
        row = names.index(select) if select in names else (keep if 0 <= keep < len(names) else (0 if names else -1))
        self.listw.setCurrentRow(row)
        self.on_row(row)

    def current(self):
        i = self.listw.currentRow()
        return self.items[i] if self.cust is None and 0 <= i < len(self.items) else None

    def current_doc(self):
        i = self.listw.currentRow()
        return self.docs[i] if self.cust is not None and 0 <= i < len(self.docs) else None

    def _buttons(self, shown):
        for name in ("conv_btn", "edit_btn", "add_btn", "open_btn", "restore_btn", "drop_btn", "del_btn"):
            getattr(self, name).setVisible(name in shown)

    def on_row(self, _i):
        if self.cust is None:
            self._buttons(("edit_btn", "add_btn", "open_btn", "del_btn"))
            self.edit_btn.setText("✏  Sửa mẫu…")
            self.kind_hint.setText("")
            it = self.current()
            for b in (self.edit_btn, self.open_btn, self.del_btn):
                b.setEnabled(bool(it))
            if not it:
                self.title.setText("")
                self.view.clear()
                return
            self.title.setText(f"{os.path.splitext(it['file'])[0]}  —  {loai_text(it['loai'])}, {ext_text(it['ext'])}, {len(it['tokens'])} ô thay thế")
            self.view.show_image(template_image(self.store, it, 1000), os.path.splitext(it["file"])[0])
            return
        d = self.current_doc()
        if not d:
            self._buttons(())
            self.kind_hint.setText("Khách này chưa có chứng từ nào.")
            self.title.setText("")
            self.view.clear()
            return
        kind = d["kind"]
        self.kind_hint.setText(KIND_HINT[kind])
        if kind in ("form", "rieng"):
            self._buttons(("edit_btn", "open_btn", "restore_btn") + (("drop_btn",) if kind == "form" else ()))
            self.edit_btn.setText("✏  Sửa trong app…")
            self.edit_btn.setEnabled(True)
            self.open_btn.setEnabled(True)
            self.restore_btn.setEnabled(bool(d["goc"]))
            self.drop_btn.setEnabled(True)
        elif kind == "builtin":
            self._buttons(("conv_btn",))
            self.conv_btn.setEnabled(True)
        else:
            self._buttons(())
        label = self.core.PROFILES.get(self.cust, {}).get("label") or self.cust
        self.title.setText(f"{label}  —  {d['label']}  ({KIND_TEXT[kind]}, {ext_text(d['ext'])})")
        self.view.show_image(self._doc_image(d), f"{label} / {d['label']}")

    def _doc_image(self, d, width=1000):
        if d["path"]:
            return template_image(self.store, {"path": d["path"], "ext": d["ext"]}, width)
        from . import mau_render
        import json
        key = ("builtin", self.cust, d["mode"], width, json.dumps(self.core.PROFILES.get(self.cust, {}), sort_keys=True, default=str))
        if key not in _IMG_CACHE:
            try:
                ext, data, _w = self.core.form_from_builtin(self.store, self.cust, d["mode"], tokenize=d["kind"] == "builtin")
                _IMG_CACHE[key] = mau_render.render_template(ext, data, width)
            except Exception:  # noqa: BLE001 - không dựng được hình: khung xem báo trống
                _IMG_CACHE[key] = QImage()
        return _IMG_CACHE[key]

    # ---- nút ---------------------------------------------------------------------------------------------------
    def add_new(self, path=None):
        names = add_template_to_kho(self, self.store, "Chung", path if isinstance(path, str) else None)
        if names:
            self.msg.setText("✅  Đã nạp vào kho: " + ", ".join(os.path.splitext(n)[0] for n in names) + ".")
            self.refresh(select=names[0])

    def convert(self):
        d = self.current_doc()
        if not d or d["kind"] != "builtin":
            return
        try:
            path, warns = self.store.form_make(self.cust, d["mode"])
        except Exception as e:  # noqa: BLE001
            widgets.warn(self, "Chưa chuyển được", str(e))
            return
        note = f"✅  Đã chuyển “{d['label']}” thành form. Từ nay chứng từ này xuất theo form; bấm “Sửa trong app…” để sửa."
        if warns:
            note += " Nên xem lại: " + "; ".join(warns[:3]) + ("…" if len(warns) > 3 else "")
        self.msg.setText(note)
        self.refresh(select=d["mode"])

    def edit(self):
        if self.cust is None:
            it = self.current()
            if it and EditTemplateDialog(self.core, self.store, it["file"], self).exec():
                self.msg.setText(f"✅  Đã lưu mẫu “{os.path.splitext(it['file'])[0]}”. Khách đã mượn mẫu này trước đó vẫn giữ bản của họ.")
                self.refresh(select=it["file"])
            return
        d = self.current_doc()
        if d and d["path"]:
            label = self.core.PROFILES.get(self.cust, {}).get("label") or self.cust
            if EditTemplateDialog(self.core, self.store, os.path.basename(d["path"]), self, path=d["path"], title=f"{label} / {d['label']}").exec():
                self.msg.setText(f"✅  Đã lưu “{d['label']}” của {label}. Các lần xuất sau dùng form này (bản gốc vẫn giữ để khôi phục).")
                self.refresh(select=d["mode"])

    def open_file(self):
        it = self.current() if self.cust is None else self.current_doc()
        if it and it.get("path"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(it["path"]))
            if self.cust is not None:
                self.msg.setText("Đã mở file bằng Word/Excel. Sửa xong thì lưu file: lần xuất sau dùng luôn file đó (bản gốc chỉ được cất khi sửa trong app).")

    def restore(self):
        d = self.current_doc()
        if d and d["path"] and widgets.ask(self, "Khôi phục bản gốc", f"Đưa “{d['label']}” về bản trước lần sửa đầu tiên? Các chỗ đã sửa sẽ mất."):
            try:
                self.store.doc_restore(d["path"])
            except ValueError as e:
                widgets.warn(self, "Chưa khôi phục được", str(e))
                return
            self.msg.setText(f"✅  Đã khôi phục bản gốc của “{d['label']}”.")
            self.refresh(select=d["mode"])

    def drop(self):
        d = self.current_doc()
        if d and d["kind"] == "form" and widgets.ask(self, "Dùng lại mẫu dựng sẵn", f"Bỏ form đã sửa của “{d['label']}” và xuất lại theo mẫu dựng sẵn của phần mềm?"):
            self.store.form_drop(self.cust, d["mode"])
            self.msg.setText(f"Đã bỏ form: “{d['label']}” xuất lại theo mẫu dựng sẵn.")
            self.refresh(select=d["mode"])

    def remove(self):
        it = self.current()
        if it and widgets.ask(self, "Xóa mẫu", f"Xóa “{os.path.splitext(it['file'])[0]}” khỏi kho? Khách đã dùng mẫu này vẫn giữ bản của họ."):
            self.store.kho_remove(it["file"])
            self.msg.setText("Đã xóa khỏi kho.")
            self.refresh()

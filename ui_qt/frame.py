"""Khung trang chung: banner gradient có hình tờ chứng từ (vẽ bằng QPainter) và các hằng số của thanh menu."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from . import theme

# tiêu đề + mô tả của banner theo thứ tự mục menu (main_window.NAV)
BANNERS = [
    ("Làm chứng từ", "Chọn khách, nạp PO, kiểm tra dòng hàng rồi xuất trọn bộ chứng từ trong vài bước."),
    ("Tờ khai đang có", "Các thư mục tờ khai trong HAI_QUAN: hồ sơ nào còn thiếu file, mở thư mục để làm tiếp."),
    ("Hồ sơ đã lưu", "Các lô đã làm: mở lại để làm tiếp hoặc xuất sổ theo dõi ra Excel."),
    ("Danh mục", "Hồ sơ theo tháng, theo khách hàng, thư viện cân nặng và danh mục ERP."),
    ("Khách hàng", "Tìm kiếm, cập nhật thông tin pháp lý, địa chỉ giao nhận và mẫu chứng từ riêng của từng khách hàng."),
    ("Data tổng", "Danh mục sản phẩm dùng chung: tên, kg/chiếc, SL/kiện đã xác nhận cho mọi máy."),
    ("Kho mẫu", "Xem như bản in các mẫu Word/Excel; sửa mẫu hoặc nạp mẫu mới khi cần."),
    ("Cài đặt", "Thông tin công ty, thư mục dữ liệu, nạp dữ liệu học và kiểm tra bộ đọc scan."),
]


class Banner(QFrame):
    """Banner đầu trang, vẽ theo kiểu giao diện đang bật.
    Kính mờ: nền trắng trong mờ với hai vệt màu loang (xanh, hồng) như file mẫu, hai tờ chứng từ bên phải.
    Tactile: khối nổi cùng màu nền, viền sáng trên-trái, tối dưới-phải."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(128)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 20, 280, 14)
        self.title = QLabel("")
        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addWidget(self.desc)
        lay.addStretch(1)
        self.restyle()
        theme.on_change(lambda _n: self.restyle())

    def restyle(self):
        t = theme.tokens()
        self.title.setStyleSheet(f"font-size:24px;font-weight:700;color:{t['deep']};background:transparent")
        self.desc.setStyleSheet(f"font-size:13px;color:{t['muted']};background:transparent")
        self.update()

    def set_text(self, title, desc):
        self.title.setText(title)
        self.desc.setText(desc)

    def paintEvent(self, _e):
        t = theme.tokens()
        tactile = theme.CURRENT == "tactile"
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, 24, 24)
        if tactile:
            p.fillPath(path, QColor(t["bg"]))
            p.setClipPath(path)
            p.setPen(QPen(QColor("#FFFFFF"), 4))  # viền sáng phía trên-trái
            p.drawLine(int(rect.left()), int(rect.top()), int(rect.right()), int(rect.top()))
            p.drawLine(int(rect.left()), int(rect.top()), int(rect.left()), int(rect.bottom()))
            p.setPen(QPen(QColor("#B4C0D0"), 4))  # viền tối phía dưới-phải
            p.drawLine(int(rect.left()), int(rect.bottom()), int(rect.right()), int(rect.bottom()))
            p.drawLine(int(rect.right()), int(rect.top()), int(rect.right()), int(rect.bottom()))
            sheet, sheet_line, bar_a, bar_b = QColor("#E8ECF2"), QColor("#B4C0D0"), QColor("#B4C0D0"), QColor("#2B6CB0")
        else:
            p.fillPath(path, QColor(255, 255, 255, 185))
            p.setClipPath(path)
            g1 = QRadialGradient(rect.left() + 120, rect.top() + 20, 330)  # vệt xanh loang như blob-1 của file mẫu
            g1.setColorAt(0, QColor(161, 196, 253, 150))
            g1.setColorAt(1, QColor(194, 233, 251, 0))
            p.fillPath(path, QBrush(g1))
            g2 = QRadialGradient(rect.right() - 90, rect.bottom() + 10, 300)  # vệt hồng như blob-2
            g2.setColorAt(0, QColor(255, 154, 158, 120))
            g2.setColorAt(1, QColor(254, 207, 239, 0))
            p.fillPath(path, QBrush(g2))
            p.setPen(QPen(QColor(255, 255, 255, 230), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 24, 24)
            sheet, sheet_line, bar_a, bar_b = QColor(255, 255, 255, 235), QColor(0, 0, 0, 20), QColor("#D2D2D7"), QColor("#1D1D1F")
        for dx, dy, rot in ((self.width() - 250, 14, -8), (self.width() - 170, 36, 6)):  # hai tờ chứng từ
            p.save()
            p.translate(dx + 70, dy + 56)
            p.rotate(rot)
            p.setBrush(sheet)
            p.setPen(QPen(sheet_line, 1))
            p.drawRoundedRect(QRectF(-70, -56, 140, 170), 14, 14)
            p.setPen(Qt.NoPen)
            for i in range(5):
                p.setBrush(bar_a if i else bar_b)
                p.drawRoundedRect(QRectF(-52, -38 + i * 22, 90 if i else 60, 8), 4, 4)
            p.restore()

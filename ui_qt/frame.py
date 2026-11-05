"""Khung trang chung: banner gradient có hình tờ chứng từ (vẽ bằng QPainter) và các hằng số của thanh menu."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

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
    """Banner đầu trang: gradient xanh 120°, bo 24px, tiêu đề + mô tả bên trái, hình hai tờ chứng từ bên phải."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(128)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 20, 280, 14)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size:24px;font-weight:700;color:#0B3F85;background:transparent")
        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet("font-size:13px;color:#12263F;background:transparent")
        lay.addWidget(self.title)
        lay.addWidget(self.desc)
        lay.addStretch(1)

    def set_text(self, title, desc):
        self.title.setText(title)
        self.desc.setText(desc)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor("#E3F1FF"))
        g.setColorAt(0.55, QColor("#BFE0FF"))
        g.setColorAt(1, QColor("#8FC8FF"))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 24, 24)
        p.fillPath(path, QBrush(g))
        p.setClipPath(path)
        for dx, dy, rot, alpha in ((self.width() - 250, 14, -8, 235), (self.width() - 170, 36, 6, 255)):  # hai tờ chứng từ
            p.save()
            p.translate(dx + 70, dy + 56)
            p.rotate(rot)
            p.setBrush(QColor(255, 255, 255, alpha))
            p.setPen(QPen(QColor("#CFE4FB"), 1))
            p.drawRoundedRect(QRectF(-70, -56, 140, 170), 12, 12)
            p.setPen(Qt.NoPen)
            for i in range(5):
                p.setBrush(QColor("#BFD8F5") if i else QColor("#1570D8"))
                p.drawRoundedRect(QRectF(-52, -38 + i * 22, 90 if i else 60, 8), 4, 4)
            p.restore()

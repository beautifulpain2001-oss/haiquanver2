"""Khung dùng chung cho các trang Hồ sơ, Danh mục, Khách hàng, Cài đặt."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QLineEdit, QTableView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


def _head(title, hint=""):
    t = QLabel(title)
    t.setObjectName("title")
    h = QLabel(hint)
    h.setObjectName("hint")
    h.setWordWrap(True)
    return t, h


def _table(headers, stretch_col=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().hide()
    t.verticalHeader().setDefaultSectionSize(38)  # đủ cao cho nút trong ô (không bị đè lên dòng khác)
    t.setAlternatingRowColors(True)
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_col is not None:
        hh.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    return t


def _fill(table, rows, right=()):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            cell = QTableWidgetItem("" if v is None else str(v))
            if c in right:
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, cell)


class _Page(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(28, 24, 28, 24)
        self.lay.setSpacing(10)

    def search_box(self, placeholder, on_change):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.textChanged.connect(on_change)
        return e


class RowsModel(QAbstractTableModel):
    """Bảng chỉ đọc nhiều dòng (hàng nghìn): chỉ vẽ dòng đang nhìn thấy nên mở tức thì, khác QTableWidget phải tạo ô cho từng dòng."""

    def __init__(self, headers, right=()):
        super().__init__()
        self.headers, self.right, self.rows = list(headers), set(right), []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            v = self.rows[index.row()][index.column()]
            return "" if v is None else str(v)
        if role == Qt.TextAlignmentRole and index.column() in self.right:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None


def _big_table(headers, widths, stretch_col, right=()):
    """QTableView + RowsModel với độ rộng cột cố định (không đo nội dung từng ô)."""
    v = QTableView()
    v.setModel(RowsModel(headers, right))
    v.setSelectionBehavior(QAbstractItemView.SelectRows)
    v.setSelectionMode(QAbstractItemView.SingleSelection)
    v.setEditTriggers(QAbstractItemView.NoEditTriggers)
    v.verticalHeader().hide()
    v.verticalHeader().setDefaultSectionSize(30)
    v.setAlternatingRowColors(True)
    hh = v.horizontalHeader()
    for c, w in enumerate(widths):
        hh.setSectionResizeMode(c, QHeaderView.Interactive)
        v.setColumnWidth(c, w)
    hh.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    return v

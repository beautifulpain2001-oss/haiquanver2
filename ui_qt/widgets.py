"""Tiện ích dùng chung: chạy việc nặng ở luồng nền, hộp thoại thông báo, mở thư mục."""

import os
import subprocess
import sys
import traceback

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox


class Job(QThread):
    """Chạy `fn()` ở luồng nền; báo kết quả qua `done` (hoặc `failed` kèm thông báo)."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:  # noqa: BLE001 - báo lỗi cho người dùng thay vì để luồng chết lặng lẽ
            self.error_trace = traceback.format_exc()
            self.failed.emit(str(e) or e.__class__.__name__)


def run_job(owner, fn, on_done, on_failed):
    """Giữ tham chiếu tới luồng trong `owner` để không bị dọn mất khi đang chạy."""
    job = Job(fn, owner)
    owner._job = job
    job.done.connect(on_done)
    job.failed.connect(on_failed)
    job.start()
    return job


# Tách ra hàm riêng để test thay thế được (không bật hộp thoại chặn trong test)
def info(parent, title, text):
    QMessageBox.information(parent, title, text)


def warn(parent, title, text):
    QMessageBox.warning(parent, title, text)


def ask(parent, title, text):
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


def open_folder(path):
    os.makedirs(path, exist_ok=True)
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)) and not sys.platform.startswith("win"):
        try:
            subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


def fmt_num(v, nd=0):
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return ""

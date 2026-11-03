"""Tiện ích dùng chung: chạy việc nặng ở luồng nền, hộp thoại thông báo, mở thư mục."""

import os
import subprocess
import sys
import traceback

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox
from shiboken6 import isValid


class Job(QThread):
    """Chạy `fn()` ở luồng nền; báo kết quả qua `done` (hoặc `failed` kèm thông báo)."""

    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str, float)

    def __init__(self, fn, parent=None, with_progress=False):
        super().__init__(parent)
        self.fn, self.with_progress = fn, with_progress

    def run(self):
        try:
            self.done.emit(self.fn(self.progress.emit) if self.with_progress else self.fn())
        except Exception as e:  # noqa: BLE001 - báo lỗi cho người dùng thay vì để luồng chết lặng lẽ
            self.error_trace = traceback.format_exc()
            self.failed.emit(str(e) or e.__class__.__name__)


_JOBS = set()


def run_job(owner, fn, on_done, on_failed=None, on_progress=None):
    """Giữ tham chiếu tới luồng trong `owner` để không bị dọn mất khi đang chạy.
    on_progress(text, fraction): khi có, `fn` được gọi với một hàm báo tiến trình `report(text, fraction)`."""
    job = Job(fn, owner, with_progress=on_progress is not None)
    if on_progress is not None:
        job.progress.connect(on_progress)
    owner._job = job
    _JOBS.add(job)
    job.finished.connect(lambda j=job: _JOBS.discard(j))
    job.done.connect(on_done)
    job.failed.connect(on_failed or (lambda _msg: None))
    job.start()
    return job


def wait_jobs(ms=5000):
    """Chờ các việc nền xong (gọi khi đóng cửa sổ để luồng không bị hủy giữa chừng)."""
    for j in list(_JOBS):
        if not isValid(j):  # luồng đã bị Qt hủy cùng cửa sổ chủ: bỏ qua
            _JOBS.discard(j)
            continue
        j.wait(ms)


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

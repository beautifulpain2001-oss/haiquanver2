"""Các trang ngoài luồng làm chứng từ: Tờ khai, Data tổng, Hồ sơ đã lưu, Danh mục, Khách hàng, Cài đặt.

Mỗi trang nay nằm trong một file riêng ở `ui_qt/pages/`. File này chỉ nối lại để `main_window.py` và test cũ không phải sửa.
"""

from .pages.declarations import *  # noqa: F401,F403
from .pages.data_tong import *  # noqa: F401,F403
from .pages.records import *  # noqa: F401,F403
from .pages.catalog import *  # noqa: F401,F403
from .pages.customers import *  # noqa: F401,F403
from .pages.settings import *  # noqa: F401,F403

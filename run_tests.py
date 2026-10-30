#!/usr/bin/env python3
"""Một lệnh chạy toàn bộ kiểm thử Hồng Thiên.

    python run_tests.py            # self-test của app + pytest (bỏ qua GUI nếu không có màn hình)
    python run_tests.py --gui      # thêm kiểm thử giao diện (Linux: tự dùng xvfb-run nếu có)
    python run_tests.py -k pkl     # tham số còn lại chuyển thẳng cho pytest
    python run_tests.py --update-snapshots
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))


def run_self_test():
    """Chạy `hongthien_desktop_app.py --self-test` trong bản sao tạm để không đụng dữ liệu thật."""
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(ROOT, "hongthien_desktop_app.py"), tmp)
        print("== --self-test (thư mục tạm) ==")
        res = subprocess.run([sys.executable, "hongthien_desktop_app.py", "--self-test"], cwd=tmp)
        out = os.path.join(tmp, "DATA_LUU_TRU_HONG_THIEN", "01_WORKING_LAM_CHUNG_TU")
        made = sorted(f for f in os.listdir(out) if f.startswith("Test_Full_")) if os.path.isdir(out) else []
        if res.returncode or len(made) != 3:
            print(f"self-test THẤT BẠI (exit {res.returncode}, file sinh ra: {made})")
            return 1
        print("self-test OK:", ", ".join(made))
        return 0


def main(argv):
    gui = "--gui" in argv
    args = [a for a in argv if a != "--gui"]
    if run_self_test():
        return 1
    cmd = [sys.executable, "-m", "pytest", *args]
    if not gui:
        cmd += ["-m", "not gui"]
    elif sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a", *cmd]
    print("== pytest ==")
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Đóng gói app thành 1 file chạy độc lập (không cần cài Python) bằng PyInstaller.

    python build_exe.py              # build + tự kiểm tra (--self-test) + nén zip
    python build_exe.py --no-test    # chỉ build

Kết quả (trên Windows):
    dist/HongThien_HaiQuan_Desktop.exe
    dist/HongThien_HaiQuan_Desktop_Windows.zip   (file .exe + hướng dẫn)
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "HongThien_HaiQuan_Desktop"
DIST = os.path.join(ROOT, "dist")
EXE = os.path.join(DIST, NAME + (".exe" if os.name == "nt" else ""))
ZIP = os.path.join(DIST, NAME + "_Windows.zip")
GUIDE = os.path.join(ROOT, "HUONG_DAN_BAN_EXE.md")


def build():
    if os.name == "nt":
        # Thiếu Tcl/Tk thì PyInstaller lặng lẽ bỏ Tkinter và .exe sẽ không mở được cửa sổ
        import tkinter
        tkinter.Tcl()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", NAME,
        "--distpath", DIST,
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", os.path.join(ROOT, "build"),
        # Không dùng tới, bỏ bớt cho file nhỏ và khởi động nhanh hơn
        "--exclude-module", "pytest",
        "--exclude-module", "numpy",
        "hongthien_desktop_app.py",
    ]
    print("==", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    print("Đã tạo:", EXE, f"({os.path.getsize(EXE) / 1e6:.1f} MB)")


def self_test():
    """Chạy bản đóng gói với --self-test trong thư mục trống: dữ liệu phải sinh ra cạnh file .exe."""
    with tempfile.TemporaryDirectory() as tmp:
        exe = shutil.copy(EXE, tmp)
        print("== self-test bản đóng gói:", exe)
        # cwd khác thư mục chứa .exe để chắc chắn app không phụ thuộc thư mục đang đứng
        res = subprocess.run([exe, "--self-test"], cwd=ROOT, timeout=600)
        out = os.path.join(tmp, "DATA_LUU_TRU_HONG_THIEN", "01_WORKING_LAM_CHUNG_TU")
        made = sorted(f for f in os.listdir(out) if f.startswith("Test_Full_")) if os.path.isdir(out) else []
        if res.returncode or len(made) != 3:
            log = os.path.join(tmp, "SELF_TEST_LOI.txt")
            if os.path.exists(log):
                print(open(log, encoding="utf-8").read())
            print(f"self-test THẤT BẠI (exit {res.returncode}, file sinh ra: {made})")
            return 1
        print("self-test OK:", ", ".join(made))
        if os.name == "nt":
            print("== mở thử giao diện (--gui-smoke)")
            try:
                res = subprocess.run([exe, "--gui-smoke"], cwd=ROOT, timeout=180)
            except subprocess.TimeoutExpired:
                print("Giao diện THẤT BẠI: không tự đóng sau 180 giây (có thể đang hiện hộp thoại lỗi)")
                return 1
            if res.returncode:
                print(f"Giao diện THẤT BẠI (exit {res.returncode})")
                return 1
            print("Giao diện OK")
        return 0


def package():
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(EXE, os.path.basename(EXE))
        z.write(GUIDE, "HUONG_DAN.txt")
    print("Đã nén:", ZIP)


def main(argv):
    # Console Windows cũ không in được tiếng Việt: thay ký tự lỗi thay vì dừng build
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    build()
    if "--no-test" not in argv and self_test():
        return 1
    package()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

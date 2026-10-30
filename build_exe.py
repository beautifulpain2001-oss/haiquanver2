#!/usr/bin/env python3
"""Đóng gói app thành 1 file chạy độc lập (không cần cài Python) bằng PyInstaller.

    python build_exe.py              # build + tự kiểm tra (--self-test) + nén zip
    python build_exe.py --no-test    # chỉ build
    python build_exe.py --no-ocr     # không kèm bộ OCR Tesseract (zip nhỏ hơn, không đọc được PDF scan)

Kết quả (trên Windows):
    dist/HongThien_HaiQuan_Desktop.exe
    dist/Tesseract-OCR/                          (bộ OCR offline cho PDF scan / ảnh, tiếng Việt + Anh)
    dist/HongThien_HaiQuan_Desktop_Windows.zip   (file .exe + Tesseract-OCR + hướng dẫn)

Bộ OCR lấy từ Tesseract đã cài trên máy build (mặc định C:\\Program Files\\Tesseract-OCR, hoặc biến
môi trường TESSERACT_DIR) và phải có sẵn tessdata/vie.traineddata.
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
OCR_DIR = os.path.join(DIST, "Tesseract-OCR")
OCR_LANGS = ("eng", "vie", "osd")


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


def find_tesseract_dir():
    candidates = [
        os.environ.get("TESSERACT_DIR", ""),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR"),
    ]
    # Để sau cùng: tesseract trong PATH có thể chỉ là shim (Chocolatey) không có DLL bên cạnh
    if shutil.which("tesseract"):
        candidates.append(os.path.dirname(os.path.realpath(shutil.which("tesseract"))))
    for d in candidates:
        if d and os.path.isfile(os.path.join(d, "tesseract.exe")):
            return d
    sys.exit("Không tìm thấy Tesseract-OCR để đóng gói (cài Tesseract hoặc đặt TESSERACT_DIR; hoặc dùng --no-ocr)")


def bundle_ocr():
    """Chép bản gọn của Tesseract (tesseract.exe + DLL + dữ liệu eng/vie/osd) ra dist/Tesseract-OCR."""
    src = find_tesseract_dir()
    if not os.path.isfile(os.path.join(src, "tessdata", "vie.traineddata")):
        sys.exit(f"Thiếu {os.path.join(src, 'tessdata', 'vie.traineddata')} (dữ liệu OCR tiếng Việt)")
    shutil.rmtree(OCR_DIR, ignore_errors=True)
    os.makedirs(os.path.join(OCR_DIR, "tessdata"))
    for f in os.listdir(src):
        low = f.lower()
        if low == "tesseract.exe" or low.endswith(".dll") or low.startswith(("license", "copying")):
            shutil.copy2(os.path.join(src, f), OCR_DIR)
    for f in os.listdir(os.path.join(src, "tessdata")):
        path = os.path.join(src, "tessdata", f)
        if os.path.isdir(path):
            shutil.copytree(path, os.path.join(OCR_DIR, "tessdata", f))  # configs/, tessconfigs/
        elif f.endswith(".traineddata") and f[: -len(".traineddata")] in OCR_LANGS:
            shutil.copy2(path, os.path.join(OCR_DIR, "tessdata"))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OCR_DIR) for f in fs)
    print(f"Đã chép bộ OCR từ {src} -> {OCR_DIR} ({size / 1e6:.1f} MB)")
    for r, _, fs in os.walk(OCR_DIR):
        for f in fs:
            print(f"   {os.path.getsize(os.path.join(r, f)) / 1e6:7.2f} MB  {os.path.relpath(os.path.join(r, f), OCR_DIR)}")


def self_test(with_ocr=True):
    """Chạy bản đóng gói với --self-test trong thư mục trống: dữ liệu phải sinh ra cạnh file .exe."""
    with tempfile.TemporaryDirectory() as tmp:
        exe = shutil.copy(EXE, tmp)
        if with_ocr:
            shutil.copytree(OCR_DIR, os.path.join(tmp, "Tesseract-OCR"))
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
        if with_ocr:
            # Đọc PDF scan Kodi/Tesa bằng đúng bộ OCR nằm cạnh file .exe trong zip
            print("== OCR PDF scan (--ocr-self-test)")
            res = subprocess.run([exe, "--ocr-self-test"], cwd=ROOT, timeout=600)
            if res.returncode:
                log = os.path.join(tmp, "SELF_TEST_LOI.txt")
                if os.path.exists(log):
                    print(open(log, encoding="utf-8").read())
                print(f"OCR THẤT BẠI (exit {res.returncode})")
                return 1
            print("OCR OK")
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


def package(with_ocr=True):
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(EXE, os.path.basename(EXE))
        z.write(GUIDE, "HUONG_DAN.txt")
        if with_ocr:
            for root, _, files in os.walk(OCR_DIR):
                for f in files:
                    path = os.path.join(root, f)
                    z.write(path, os.path.relpath(path, DIST))
    print(f"Đã nén: {ZIP} ({os.path.getsize(ZIP) / 1e6:.1f} MB)")


def main(argv):
    # Console Windows cũ không in được tiếng Việt: thay ký tự lỗi thay vì dừng build
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    with_ocr = "--no-ocr" not in argv
    build()
    if with_ocr:
        bundle_ocr()
    if "--no-test" not in argv and self_test(with_ocr):
        return 1
    package(with_ocr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

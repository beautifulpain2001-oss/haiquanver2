"""Chạy lại chế độ `python hongthien_desktop_app.py --self-test` trong thư mục tạm."""

import functools
import subprocess
import sys

import openpyxl

import hongthien_desktop_app as app
from conftest import APP_DIR


def test_run_self_test_writes_one_workbook_per_customer(monkeypatch, data_dir):
    monkeypatch.setattr(app, "DedicatedDataStore", functools.partial(app.DedicatedDataStore, base_dir=str(data_dir)))
    app.run_self_test()
    out = sorted(p.name for p in (data_dir / "01_WORKING_LAM_CHUNG_TU").glob("Test_Full_*.xlsx"))
    assert out == ["Test_Full_KODI.xlsx", "Test_Full_SHIRAI.xlsx", "Test_Full_TESA.xlsx"]
    for name in out:
        openpyxl.load_workbook(data_dir / "01_WORKING_LAM_CHUNG_TU" / name)


def test_module_imports_without_tkinter(tmp_path):
    # Bản đóng gói và máy chủ không màn hình vẫn phải import được phần xử lý
    code = (
        "import sys; sys.modules['tkinter'] = None; "
        f"sys.path.insert(0, {str(APP_DIR)!r}); "
        "import hongthien_desktop_app as m; assert m.tk is None; print('ok')"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "ok"

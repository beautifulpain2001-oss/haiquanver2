"""Data tổng: danh mục sản phẩm dùng chung (kg/chiếc từ file ERP, SL/kiện từ invoice cũ), nằm trong HAI_QUAN/DATA_TONG.json."""
import openpyxl

import hongthien_desktop_app as app


def make_store(data_dir, tmp_path, name="a"):
    s = app.DedicatedDataStore(base_dir=str(data_dir))
    s.config_file = str(tmp_path / f"config_{name}.json")
    return s


def erp_file(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CÔNG TY GIẢ"])
    ws.append(["Sử dụng", "Tên tắt khách hàng", "Mã cũ", "Tên khách hàng", "Mã số", "Tên (vn)", "Mô tả", "Quy trình SX", "Cân nặng (g)"])
    ws.append(["Chọn", "DTGIA", "C1", "CÔNG TY DATA TỔNG GIẢ", "FG1-001", "ống 76x5x87, T.nâu", None, "CAT", 91])
    ws.append(["Chọn", "DTGIA", "C2", "CÔNG TY DATA TỔNG GIẢ", "FG1-002", "ống 76x5x57, T.nâu", None, "CAT", 60])
    ws.append(["Chọn", "None", None, None, "FG9", "vật tư nội bộ", None, "CAT", 5])  # không có khách: bỏ qua
    ws.append(["Chọn", "DTGIA", "C3", "CÔNG TY DATA TỔNG GIẢ", "FG1-003", "ống 76x5x90", None, "CAT", 0])  # không có cân nặng: bỏ qua
    wb.save(path)


def test_erp_import_fills_kg_and_lines_get_missing_values(data_dir, tmp_path):
    s = make_store(data_dir, tmp_path)
    s.save_learned_customer("dtgia", {"name": "CÔNG TY DATA TỔNG GIẢ", "label": "Dtgia", "addr": "x"}, [])
    erp_file(str(tmp_path / "erp.xlsx"))
    res = s.dt_import_erp(str(tmp_path / "erp.xlsx"))
    assert res == {"them": 2, "cap_nhat": 0, "bo_qua": 2}
    assert (data_dir / "HAI_QUAN" / "DATA_TONG.json").exists()  # file nằm trong thư mục hải quan dùng chung
    line = {"ten_sp": "Ống giấy phi 76.2 (3inch) x 5 x 87 mm", "ma_sp": "", "qty": 1000, "kg": 0, "div": 0, "tare": 0.5}
    assert s.dt_fill_lines("dtgia", [line]) == 1 and line["kg"] == 0.091 and line["net"] == 91.0 and line["gross"] == 91.5
    assert line["kien"] == 0  # chưa có SL/kiện: để trống cho người dùng điền


def test_kien_learned_from_confirmed_lines_is_shared_with_other_machine(data_dir, tmp_path):
    a, b = make_store(data_dir, tmp_path, "a"), make_store(data_dir, tmp_path, "b")
    a.save_learned_customer("dtgia", {"name": "CÔNG TY DATA TỔNG GIẢ", "label": "Dtgia", "addr": "x"}, [])
    erp_file(str(tmp_path / "erp.xlsx"))
    a.dt_import_erp(str(tmp_path / "erp.xlsx"))
    item = {"ten_sp": "Ống giấy phi 76.2( 3inch) x 5 x 57 mm", "ma_sp": "3609100570001", "kg": 0.06, "div": 40}
    assert a.dt_learn_items("dtgia", [item]) == 1  # xuất chứng từ: nhớ SL/kiện đã xác nhận
    assert b.changed_on_disk() and b.sync()  # máy B thấy data tổng mới
    hit = b.dt_lookup("dtgia", "Ống giấy phi 76.2( 3inch) x 5 x 57 mm", "3609100570001")
    assert hit["kien"] == 40 and hit["kien_nguon"] == "tay" and hit["ma_erp"] == "FG1-002"


def test_stronger_source_is_not_overwritten_by_weaker(data_dir, tmp_path):
    s = make_store(data_dir, tmp_path)
    s.save_learned_customer("dtgia", {"name": "CÔNG TY DATA TỔNG GIẢ", "label": "Dtgia", "addr": "x"}, [])
    s.dt_learn_items("dtgia", [{"ten_sp": "Sản phẩm X", "kg": 0.5, "div": 10}])  # người dùng đã xác nhận
    erp_file(str(tmp_path / "erp.xlsx"))
    s._dt_upsert("Dtgia", "Sản phẩm X", kg=9.9, kg_nguon="erp", exact=True)  # nguồn yếu hơn không đè
    assert s.dt_lookup("dtgia", "Sản phẩm X")["kg"] == 0.5

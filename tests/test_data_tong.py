"""Data tổng: danh mục sản phẩm dùng chung (kg/chiếc từ file ERP, SL/kiện từ invoice cũ), nằm trong HAI_QUAN ngang hàng thư mục khách."""
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
    assert (data_dir / "HAI_QUAN" / "DATA_TONG.json").exists()  # file nằm trong HAI_QUAN, ngang hàng thư mục tên khách
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


QI_FAKE = """
 No PRODUCT CODE  DESCRIPTION  QTY UNITS UNIT PRICE AMOUNT  NOTE
       2V01PRK000002    Ống giấy trắng không in 空白管2500    PCS                 29,000,000.00  24/10/202611,600.0000
  1               77*2.5*1265mm 內外白
  2                2V01PRB000004Ống giấy in 紅色3K管 外白內印刷      120    PCS                  1,536,000.00   03/11/202612,800.0000
  3                2V01PRJ000002 Ống giấy 8H 紙管50    PCS    999,999.00   03/11/202612,800.0000
"""


def test_pcs_note_rows_need_qty_times_price_equal_amount():
    rows = app.parse_pcs_note_rows(QI_FAKE)
    assert [(r["code"], r["qty"], r["price"], r["ship"]) for r in rows] == [
        ("2V01PRK000002", 2500.0, 11600.0, "24/10/2026"), ("2V01PRB000004", 120.0, 12800.0, "03/11/2026")]  # dòng cuối: 50 x 12.800 khác thành tiền -> bỏ


def test_mapping_import_links_customer_code_and_name_to_erp_product(data_dir, tmp_path):
    s = make_store(data_dir, tmp_path)
    s.save_learned_customer("qi", {"name": "CÔNG TY TNHH BAO BÌ QUANG ÍCH GIẢ", "label": "Quang Ích Giả", "addr": "x"}, [])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mã sản phẩm gốc", "Tên sản phẩm gốc", "Mã khách hàng", "Tên khách hàng", "Mã sản phẩm theo KH", "Tên sản phẩm theo KH"])
    ws.append(["FG1-001", "ống 77x2.5x1265 trắng", "1", "CÔNG TY TNHH BAO BÌ QUANG ÍCH GIẢ", "FG1-001", "2V01PRK000002 Ống giấy trắng 77 x 2.5 x 1265 mm"])
    wb.save(str(tmp_path / "map.xlsx"))
    s._dt_upsert("Quang Ích Giả", "ống 77x2.5x1265 trắng", ma_erp="FG1-001", kg=0.696, kg_nguon="erp", exact=True)
    res = s.dt_import_mapping(str(tmp_path / "map.xlsx"))
    assert res["cap_nhat"] == 1
    hit = s.dt_lookup("qi", "", "2V01PRK000002")  # mã trên PO của khách tìm ra sản phẩm ERP
    assert hit["ma_erp"] == "FG1-001" and hit["kg"] == 0.696 and hit["ten_kh"] == "Ống giấy trắng 77 x 2.5 x 1265 mm"


def test_kien_divisor_is_read_from_formula_in_sheet_without_quantities(tmp_path):
    """Sheet 'data' của invoice: chưa có SL nên SL/kiện suy ra từ công thức Số kiện (=ROUNDUP(F14/10,0) -> 10, =F19/20 -> 20)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["STT", "Mã hàng", "Tên Hàng", "PO", "ĐVT", "Số Lượng", "Trọng lượng(kg)", "Số kiện", "Đơn Giá", "Thành Tiền"])
    ws.append([1, None, "2V01PRB000002 Ống giả A", None, "Chiếc", None, 0.696, "=ROUNDUP((F2/10),0)", 12800, "=I2*F2"])
    ws.append([2, None, "2V1004P000001 Thanh nẹp giả", None, "Chiếc", None, 0.03, "=F3/20", 5800, "=I3*F3"])
    wb.save(str(tmp_path / "inv.xlsx"))
    d = app.learn_from_invoice_excel(str(tmp_path / "inv.xlsx"), ignore_norms=True)
    got = {x["name"]: (x.get("kg"), x.get("div")) for x in d["items"]}
    assert got["Ống giả A"] == (0.696, 10) and got["Thanh nẹp giả"] == (0.03, 20)


def test_bbgh_sheet_lists_items_with_both_parties(data_dir, tmp_path):
    s = make_store(data_dir, tmp_path)
    s.save_learned_customer("bbgia", {"name": "CÔNG TY BBGH GIẢ", "label": "Bbgh Giả", "addr": "Địa chỉ nhận giả", "unit": "Chiếc"}, [])
    items = [{"po": "20261001001", "ma_sp": "2V01PRK000002", "ten_sp": "Ống giả 77 x 2.5", "qty": 2500, "price": 11600, "amount": 29000000, "unit": "Chiếc"}]
    rec = {"customer": "bbgia", "docDate": "2026-10-01", "items": items, "poNumber": "20261001001", "poDates": {}}
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = app.build_bbgh_sheet(wb, rec)
    cells = {c.coordinate: c.value for row in ws.iter_rows() for c in row if c.value is not None}
    assert cells["A4"] == "BIÊN BẢN BÀN GIAO" and cells["A6"] == "Hôm nay, ngày 1 tháng 10 năm 2026"
    assert cells["A14"] == "Bên nhận: CÔNG TY BBGH GIẢ" and cells["A16"] == "Địa chỉ: Địa chỉ nhận giả"
    assert [cells[f"{c}21"] for c in "ABCDE"] == ["2V01PRK000002 Ống giả 77 x 2.5", "20261001001", "Chiếc", 2500, 11600] and cells["F21"] == "=D21*E21"
    assert "BBGH" in app.customer_extra_docs({"extraDocs": "bbgh, plx"}) and app.DedicatedDataStore.folder_checklist(["PKL", "BBGH"])[0].count("Biên bản bàn giao") == 1


def test_data_tong_sits_in_customs_folder_level_with_customers(data_dir, tmp_path):
    """DATA_TONG.json nằm trong thư mục HAI_QUAN ngang hàng thư mục khách; bản ở thư mục dữ liệu ngoài không được dùng.
    Nếu thư mục dữ liệu chính là HAI_QUAN thì file nằm cạnh các thư mục khách (Arizon, Best, Tesa...)."""
    import json
    (data_dir / "HAI_QUAN").mkdir(parents=True, exist_ok=True)
    (data_dir / "DATA_TONG.json").write_text(json.dumps({"items": [{"khach": "K", "ten": "Bản ngoài"}]}), encoding="utf-8")
    (data_dir / "HAI_QUAN" / "DATA_TONG.json").write_text(json.dumps({"version": 1, "items": [{"khach": "K", "ten": "Sản phẩm X", "kg": 0.5, "kg_nguon": "erp"}]}), encoding="utf-8")
    s = make_store(data_dir, tmp_path)
    assert s.dt_path() == str(data_dir / "HAI_QUAN" / "DATA_TONG.json") and [x["ten"] for x in s.data_tong] == ["Sản phẩm X"]
    s._dt_upsert("K", "Sản phẩm Y", kg=0.2, kg_nguon="tay", exact=True)
    s.dt_save()
    assert len(json.loads((data_dir / "HAI_QUAN" / "DATA_TONG.json").read_text(encoding="utf-8"))["items"]) == 2
    assert [x["ten"] for x in json.loads((data_dir / "DATA_TONG.json").read_text(encoding="utf-8"))["items"]] == ["Bản ngoài"]
    hq = tmp_path / "HAI_QUAN"
    (hq / "Arizon").mkdir(parents=True)
    s2 = make_store(hq, tmp_path / "x")
    assert s2.customs_root() == str(hq) and s2.dt_path() == str(hq / "DATA_TONG.json")


def test_export_learned_roundtrip_to_other_machine(data_dir, tmp_path):
    """Xuất file học của khách ở máy A rồi nạp ở máy B: có đủ khách, mặt hàng, định mức, file mẫu."""
    import base64, json
    a = make_store(data_dir, tmp_path)
    a.save_learned_customer("xuathoc", {"name": "CTY XUAT HOC", "mst": "0100000001", "addr": "HN"}, [{"name": "Ống 38 x 5", "code": "X1", "div": 20, "kg": 0.3}])
    tdir = data_dir / "MAU_CHUNG_TU" / "xuathoc"
    tdir.mkdir(parents=True)
    (tdir / "pkl.xlsx").write_bytes(b"abc")
    d = json.loads(json.dumps(a.export_learned("xuathoc")))
    assert d["khach_moi"]["key"] == "xuathoc" and d["khach_moi"]["items"][0]["name"] == "Ống 38 x 5" and base64.b64decode(d["khach_moi"]["mau"]["pkl"]) == b"abc"
    import pytest
    with pytest.raises(ValueError):
        a.export_learned("kodi")
    b_dir = tmp_path / "may_b"
    b_dir.mkdir()
    b = make_store(b_dir, tmp_path / "wb")
    res = b.import_learned(d)
    assert res["khach"] == "xuathoc" and b.custom_items["xuathoc"][0]["name"] == "Ống 38 x 5" and (b_dir / "MAU_CHUNG_TU" / "xuathoc" / "pkl.xlsx").read_bytes() == b"abc"


def test_able_import_po_rows_and_dccn_template(data_dir, tmp_path):
    """Able: nạp file học (kèm mẫu DCCN3), đọc PO theo gam + quy cách + SL, xuất đối chiếu công nợ theo mẫu của khách."""
    import json, base64, io, os, openpyxl
    d = {"khach_moi": {"key": "ablex", "profile": {"name": "CONG TY ABLE TEST", "label": "AbleX", "unit": "Chiếc", "addr": "HP", "mst": "0202226426", "extraDocs": "DCCN", "poStyle": "able"},
                       "items": [{"code": "38*5*460*250g", "name": "Ống 38x5x460 250g in", "unit": "Chiếc", "price": 4725, "div": 75, "kg": 0.25, "hs": "48229090"},
                                 {"code": "38*5*460*250g-ko-in", "name": "Ống 38x5x460 250g", "unit": "Chiếc", "price": 4725, "div": 75, "kg": 0.25, "hs": "48229090"}],
                       "mau": {}}, "item_mem": {}}
    tpl = "/root/.claude/uploads/60e0f727-02f2-5c49-8a4c-929e37443d6a/b3c71436-DCCN3.xlsx"
    if os.path.exists(tpl):
        d["khach_moi"]["mau"]["dccn"] = base64.b64encode(open(tpl, "rb").read()).decode()
    s = make_store(data_dir, tmp_path)
    s.import_learned(d)
    prof = app.PROFILES["ablex"]
    assert app.is_able(prof) and "DCCN" in app.customer_extra_docs(prof) and "DCCN" in app.lot_bundle_modes({"customer": "ablex"})
    cat = s.items_for_customer("ablex")
    rows = app.parse_able_po_rows("1 印刷纸管 250g 38*5*460 1728 4,725.00 d 8,164,800.00 d 2026-2350-020\n2 纸管 250g 38*5*460 100 4,725.00 d 472,500.00 d 2026-2350-027", cat)
    assert [(r["code"], r["qty"], r["price"]) for r in rows] == [("38*5*460*250g", 1728, 4725), ("38*5*460*250g-ko-in", 100, 4725)]
    if os.path.exists(tpl):
        lines = app.lines_from_erp_rows(rows, "20260821-00231", prof, cat, data_store=s)
        rec = {"customer": "ablex", "docDate": "2026-03-31", "items": lines, "poNumber": "20260821-00231", "scheduleKey": "31.03", "pxkNo": "0000113"}
        res = app.lot_export(s, rec, "DCCN")
        ws = openpyxl.load_workbook(res["path"]).worksheets[0]
        assert ws["I12"].value == 1728 and ws["J12"].value == 4725 and ws["K12"].value == "=I12*J12" and ws["D12"].value == "20260821-00231"
        assert ws["I13"].value == 100 and ws["B7"].value.endswith("CONG TY ABLE TEST")


def test_pcs_note_rows_handle_lowercase_pcs_and_fused_price_date_in_any_order():
    text = ("1  2V01PRK000010   Ố ắng gi y tr ng 空白管1000    PCS                 18,104,000.00  27/11/202618,104.0000\n77*4*1160mm\n"
            "2  2V01PRK000014Ố ắng gi y tr ng 空白管2200    pcs                 23,980,000.00 10/11/202610,900.0000\n"
            " 2V01PRK000013   Ố ắng gi y tr ng 空白管100    PCS                  1,239,500.0012,395.000011/11/2026\n"
            " 2V01PRK000013   Ố ắng gi y tr ng 空白管100    PCS                  1,239,500.000.000009/11/2026\n")
    rows = app.parse_pcs_note_rows(text)
    assert [(r["code"], r["qty"], r["price"], r["ship"]) for r in rows] == [
        ("2V01PRK000010", 1000.0, 18104.0, "27/11/2026"), ("2V01PRK000014", 2200.0, 10900.0, "10/11/2026"),
        ("2V01PRK000013", 100.0, 12395.0, "11/11/2026"), ("2V01PRK000013", 100.0, 12395.0, "09/11/2026")]

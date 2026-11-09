"""PO kiểu Richsound: mã liệu dài, ngày giao, SL, ĐVT, đơn giá, thành tiền; không lấy mã liệu làm số lượng."""
import hongthien_desktop_app as app

PO_TEXT = """ĐƠN ĐẶT HÀNG 采购订单
mã PO :
采购订单编号： 5100063100
ngày đặt hàng:
下单日期： 2026-09-09
STT
项次 Mã liệu 物料编码 Mô tả hàng hóa Thời gian giao hàng Số lượng Đơn vị Đơn giá(đã bao gồm thuế) Thành tiền
10 211000504 紙滑板/1145x1000x1.2mm/附图 2026-10-13 100 PC 75,430 7,543,000
Tổng cộng 100 7,543,000
"""


def test_dated_rows_do_not_take_material_code_as_quantity():
    rows = app.parse_dated_unit_rows(PO_TEXT)
    assert len(rows) == 1
    r = rows[0]
    assert (r["code"], r["qty"], r["price"], r["ship"]) == ("211000504", 100, 75430, "13/10/2026")
    assert app.find_po_after_label(PO_TEXT) == "5100063100"


def test_dated_rows_skip_lines_where_qty_times_price_differs():
    bad = PO_TEXT.replace("7,543,000\nTổng", "7,000,000\nTổng")
    assert app.parse_dated_unit_rows(bad) == []


def test_load_po_for_learned_customer_uses_dated_rows(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    items = [{"name": "Tấm slip sheet 1145x1000x1.2mm", "code": "211000504", "unit": "chiếc", "price": 75430, "div": 200, "kg": 1.4}]
    store.save_learned_customer("richt", {"name": "CTY RICHSOUND T", "unit": "chiếc", "addr": "BN", "mst": "0100000002"}, items)
    f = tmp_path / "po.txt"
    f.write_text(PO_TEXT, encoding="utf-8")
    res = app.lot_load_po(store, str(f), "richt")
    assert res["ok"] and len(res["items"]) == 1 and res["po"] == "5100063100"
    it = res["items"][0]
    assert it["qty"] == 100 and it["price"] == 75430 and it["ma_sp"] == "211000504" and it["div"] == 200 and it["kg"] == 1.4 and it["kien"] == 1


def _rich_store(tmp_path, key="rich9"):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    items = [{"name": "Tấm slip sheet 1145x1000x1.2mm", "code": "211000504", "unit": "chiếc", "price": 75430, "div": 200, "kg": 1.4},
             {"name": "Tấm giấy 770x480x1.2mm", "code": "211000037", "unit": "chiếc", "price": 31800, "div": 45, "kg": 0.99}]
    store.save_learned_customer(key, {"name": "CTY RICH NINE " + key, "unit": "chiếc", "addr": "BN", "mst": "0100000009"}, items)
    return store


def test_pick_numbers_remembers_rule_and_applies_next_time(tmp_path):
    from ui_qt.state import Lot
    store = _rich_store(tmp_path)
    po1 = tmp_path / "po1.txt"
    po1.write_text("Số PO 5100063100\n10 211000504 Tấm slip sheet 100 PC 75,430 7,543,000\n", encoding="utf-8")
    lot = Lot(app, store)
    lot.select_customer("rich9")
    assert lot.apply_po(lot.read_po(str(po1)))
    it = lot.items[0]
    assert it["src"].startswith("10 211000504") and app.line_numbers(it["src"]) == ["10", "211000504", "100", "75,430", "7,543,000"]
    it["qty"], it["price"] = 211000504, 100  # máy đọc sai
    info = lot.pick_info(0)
    assert info["numbers"][2] == "100" and info["qty"] == 211000504
    msg = lot.apply_pick(0, "100", "75,430")
    assert it["qty"] == 100 and it["price"] == 75430 and it["amount"] == 7543000 and it["read"] == "tay"
    assert "số thứ 3 tính từ cuối" in msg and "số thứ 2" in msg
    rules = store.read_rules("rich9")
    assert rules == {"qty": -3, "price": -2, "n": 5, "amount": -1}
    log = store.read_fix_log("rich9")
    assert {x["field"] for x in log} == {"qty", "price"} and all("line" in x and x["how"] == "chọn từ số máy đọc" for x in log)

    # lần sau: máy đọc sai thì quy tắc đã học sửa lại; dòng khác bố cục (khác số lượng số) thì bỏ qua
    wrong = [{"ma_sp": "211000037", "ten_sp": "Tấm giấy", "qty": 31800, "price": 300, "src": "20 211000037 Tấm giấy 300 PC 31,800 9,540,000", "read": "ok"},
             {"ma_sp": "X", "ten_sp": "Lạ", "qty": 1, "price": 2, "src": "30 X 5 PC 9", "read": "ok"}]
    fixed = app.apply_read_rules(wrong, store.read_rules("rich9"))
    assert fixed == 1 and (wrong[0]["qty"], wrong[0]["price"]) == (300, 31800) and (wrong[1]["qty"], wrong[1]["price"]) == (1, 2)


def test_pick_numbers_typed_by_hand_logs_fix_without_rule(tmp_path):
    from ui_qt.state import Lot
    store = _rich_store(tmp_path, "rich8")
    po1 = tmp_path / "po1.txt"
    po1.write_text("Số PO 5100063101\n10 211000504 Tấm slip sheet 100 PC 75,430 7,543,000\n", encoding="utf-8")
    lot = Lot(app, store)
    lot.select_customer("rich8")
    assert lot.apply_po(lot.read_po(str(po1)))
    lot.items[0]["qty"] = 7
    msg = lot.apply_pick(0, "120", "75,430")  # 120 không có trong dòng: gõ tay
    assert "ghi lại chỗ máy đọc sai" in msg and store.read_rules("rich8") == {}
    assert store.read_fix_log("rich8")[0]["how"] == "gõ tay"
    reloaded = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    assert any(x["customer"] == "rich8" for x in reloaded.read_fixes)  # nhật ký còn sau khi mở lại app


def test_next_pxk_is_max_plus_one_keeping_zero_padding(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    assert store.next_pxk() == ""
    store.records = [{"customer": "kodi", "pxkNo": "0000294", "docDate": "2026-10-01"}, {"customer": "tesa", "pxkNo": "0000298", "docDate": "2026-10-05"}]
    assert store.next_pxk() == "0000299"
    d = tmp_path / "d" / "HAI_QUAN" / "Able" / "2026_Thang_11" / "2026-11-01"
    d.mkdir(parents=True)
    (d / "PXK 301.pdf").write_text("x")
    assert store.next_pxk() == "0000302"  # lấy cả số từ tên file PXK trong thư mục hồ sơ


def _table_po(tmp_path, rows, header_row=17):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "po1"
    ws["A5"] = "ĐƠN ĐẶT HÀNG/ P.O"
    ws["D7"] = "Số/ No.  HT20269999"
    for c, h in enumerate(["STT/ 序号", "TÊN HÀNG/ 货物", "ĐƠN VỊ/ 单位", "THÔNG SỐ KT ,QUY CÁCH", "SỐ LƯỢNG 数量", "ĐƠN GIÁ 单价VND", "THÀNH TIỀN 总价VND", "GHI CHÚ"], 1):
        ws.cell(header_row, c, h)
    r = header_row + 1
    for name, unit, spec, qty, price in rows:
        ws.cell(r, 1, r - header_row)
        ws.cell(r, 2, name)
        ws.cell(r, 3, unit)
        ws.cell(r, 4, spec)
        ws.cell(r, 5, qty)
        ws.cell(r, 6, price)
        ws.cell(r, 7, f"=E{r}*F{r}")
        r += 1
    ws.cell(r, 1, "TỔNG TIỀN/总价 (VND):")
    ws.cell(r, 5, f"=SUM(E{header_row + 1}:E{r - 1})")
    p = tmp_path / "po_table.xlsx"
    wb.save(p)
    return p


def test_excel_table_po_skips_empty_rows_matches_by_paren_code_or_dims_and_reads_formula_qty(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    items = [{"name": "Ống giấy 78 x 8 x 400mm (44A020101.0636)", "code": "44A020101.0636", "unit": "Chiếc", "price": 22100, "div": 20, "kg": 0.711},
             {"name": "Ống giấy 78 x 16.5 x 1185mm (44A020101.0319)", "code": "44A020101.0319", "unit": "Chiếc", "price": 103000, "div": 3, "kg": 5.25},
             {"name": "Nắp giấy 1202 x1098 x 110mm", "code": "44A010301.0023", "unit": "Chiếc", "price": 19000, "div": 5, "kg": 1.11},
             {"name": "Thùng giấy 1190 x 542 x 540mm", "code": "44A010101.0049", "unit": "Chiếc", "price": 29000, "div": 5, "kg": 1.88}]
    store.save_learned_customer("betx", {"name": "CTY BETX", "unit": "Chiếc", "addr": "BN", "mst": "0100000011", "po_pattern": r"HT\d{8}"}, items)
    po = _table_po(tmp_path, [
        ("Nắp giấy", "PCS个", " 1202 x1098 x 110mm ", None, 19000),  # dòng mẫu trống: bỏ qua
        ("Thùng giấy ", "PCS个", "1190 x 542 x 540mm", 400, 29000),  # không có mã trong ngoặc: ghép theo loại hàng + kích thước
        ("Ống giấy", "PCS个", "Ống  giấy 78 x 8 x 400mm (44A020101.0636)", 1200, 22100),
        ("Ống giấy", "PCS个", "Ống giấy 78 x 16.5 x 1185mm\n(44A020101.0319)", "=992+2504", 103000),  # SL là công thức chưa có giá trị lưu sẵn
        ("Ống giấy", "PCS个", "Ống lạ 99 x 9 x 999mm (44A099999.0001)", 10, 500),  # mặt hàng chưa học
    ])
    rows = app.parse_excel_table_po(str(po))
    assert [(r["qty"], r["price"]) for r in rows] == [(400, 29000), (1200, 22100), (3496, 103000), (10, 500)]
    res = app.lot_load_po(store, str(po), "betx")
    assert res["ok"] and res["po"] == "HT20269999" and len(res["items"]) == 4
    by = {x["ma_sp"] or x["ten_sp"][:12]: x for x in res["items"]}
    assert by["44A010101.0049"]["qty"] == 400 and by["44A010101.0049"]["kg"] == 1.88
    assert by["44A020101.0319"]["qty"] == 3496 and by["44A020101.0319"]["kien"] == 1166 and by["44A020101.0636"]["kien"] == 60
    unknown = res["items"][-1]
    assert unknown["qty"] == 10 and unknown["price"] == 500 and unknown.get("read") == "suy_ra"


def test_po_item_names_resolved_by_material_code_and_spec_from_customer_then_erp(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    items = [
        # mã 203020046 bị học nhầm cho tấm slip: kích thước trong mô tả PO (ống 53x50x220) mâu thuẫn nên không được tin
        {"name": "Tấm giấy Slip sheet 1240 x 1000 x 1.2mm", "code": "203020046", "unit": "chiếc", "price": 80800, "div": 408, "kg": 1.59},
        {"name": "Ống giấy phi 53 x 50 x 220 mm", "code": "5121", "unit": "chiếc", "price": 2111, "div": 119, "kg": 0.04, "hs": "48229090"},
    ]
    store.save_learned_customer("richt2", {"name": "CTY RICH T2", "unit": "chiếc", "addr": "BN", "mst": "0100000012", "po_pattern": r"(?<!\\d)99\\d{8}(?!\\d)"}, items)
    po = tmp_path / "po.txt"
    po.write_text(
        "mã PO :\n采购订单编号： 5100063442\n"
        "10 203020046 纸筒φ53xφ50x220mm/两端+内黑 2026-10-12 260 PC 2,940 764,400\n"
        "20 211000504 纸滑板/1145x1000x1.2mm/附图 2026-10-12 100 PC 75,430 7,543,000\n", encoding="utf-8")
    res = app.lot_load_po(store, str(po), "richt2")
    assert res["ok"] and res["po"] == "5100063442"  # mẫu số PO đã học không khớp: lấy số sau nhãn 'mã PO'
    tube, slip = res["items"]
    assert tube["ten_sp"] == "Ống giấy phi 53 x 50 x 220 mm" and tube["kg"] == 0.04 and tube["div"] == 119 and tube["ma_sp"] == "203020046"  # theo quy cách, không theo mã sai
    assert "211000504" in slip["ten_sp"] and slip["ten_sp"].startswith("Tấm slip sheet") and slip["read"] == "suy_ra"  # tên lấy từ danh mục ERP theo mã liệu


def test_desc_dims_and_kind_handle_chinese_descriptions():
    assert app.desc_dims("纸筒/外Φ43.5X内Φ39.5XH290mm黑内孔") == ["43.5", "39.5", "290"]
    assert app.desc_dims("纸筒φ53xφ50x220mm/两端+内黑") == ["53", "50", "220"] and app.desc_kind("纸筒φ53xφ50x220mm") == "ONG"
    assert app.desc_dims("纸滑板/1145x1000x1.2mm/附图") == ["1145", "1000", "1.2"] and app.desc_kind("纸滑板/1145x1000x1.2mm") == "SLIP"
    assert app.desc_kind("Thanh nẹp góc 1320x50x50x5mm") == "NEP" and app.desc_kind("Ống giấy phi 53 x 50 x 220 mm") == "ONG"


def _ledger(tmp_path, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    heads = ["Tên khách hàng", "Ngày hóa đơn", "Mã PXK", "Số hóa đơn", "Tên hàng xuất hóa đơn", "ĐVT (bán hàng)", "Số lượng (ĐVT bán hàng)", "Đơn giá", "Thành tiền trước thuế"]
    for c, h in enumerate(heads, 1):
        ws.cell(4, c, h)
    for i, (pxk, name, qty, price) in enumerate(rows, 5):
        for c, v in enumerate(("CTY X", "2026-10-30", pxk, None, name, "ống", qty, price, qty * price), 1):
            ws.cell(i, c, v)
    n = 5 + len(rows)
    ws.cell(n, 7, sum(r[2] for r in rows))
    ws.cell(n, 8, sum(r[3] for r in rows))  # dòng tổng cộng không có tên hàng: phải bị bỏ
    ws.cell(n, 9, sum(r[2] * r[3] for r in rows))
    p = tmp_path / "so_chi_tiet.xlsx"
    wb.save(p)
    return p


def test_sales_ledger_is_input_rows_merge_by_item_and_price_and_total_matches(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    items = [{"name": "Ống giấy 78 x 16.5 x 1185mm (44A020101.0319)", "code": "44A020101.0319", "unit": "Chiếc", "price": 103000, "div": 3, "kg": 5.25},
             {"name": "Ống giấy 79 x 8 x 45 mm (44A020101.0648)", "code": "44A020101.0648", "unit": "Chiếc", "price": 3600, "div": 10, "kg": 0.08}]
    store.save_learned_customer("betled", {"name": "CTY BETLED", "unit": "Chiếc", "addr": "BN", "mst": "0100000013", "po_pattern": r"HT\\d{8}",
                                           "extraDocs": "PO", "poGen": "HT{yyyymm}{nn}"}, items)
    f = _ledger(tmp_path, [("XK-1", "Ống giấy 78 x 16.5 x 1185mm(44A020101.0319)", 126, 101000), ("XK-2", "Ống giấy 78 x 16.5 x 1185mm(44A020101.0319)", 126, 101000),
                           ("XK-3", "Ống  giấy  79 x 8 x 45mm ( 44A020101.0648)", 5902, 3600),
                           ("XK-4", "Ống giấy 79 x 8 x 55mm (44A020101.0648)", 800, 4500)])  # cùng mã nhưng quy cách khác: không gộp vào mặt hàng 45mm
    res = app.lot_load_po(store, str(f), "betled")
    assert res["ok"] and res["po"] == "" and len(res["items"]) == 3
    a, b, c = res["items"]
    assert (a["qty"], a["price"]) == (252, 101000) and "Gộp 2 dòng" in a["read_note"] and a["read"] == "ok"  # giá theo sổ, không theo danh mục
    assert (b["qty"], b["price"]) == (5902, 3600)
    assert c["qty"] == 800 and c["price"] == 4500 and c["read"] == "suy_ra" and "55" in c["ten_sp"]  # quy cách mâu thuẫn: giữ tên trong sổ, báo kiểm tra
    assert sum(x["amount"] for x in res["items"]) == 252 * 101000 + 5902 * 3600 + 800 * 4500


def test_po_number_generated_from_poGen_and_po_document_exports(tmp_path):
    from ui_qt.state import Lot
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    store.save_learned_customer("betpo", {"name": "CTY BETPO", "unit": "Chiếc", "addr": "BN", "mst": "0100000014", "extraDocs": "PO", "poGen": "HT{yyyymm}{nn}"},
                                [{"name": "Ống giấy 78 x 8 x 400mm (44A020101.0636)", "code": "44A020101.0636", "unit": "Chiếc", "price": 22100, "div": 20, "kg": 0.711}])
    store.records = [{"id": "R1", "customer": "betpo", "poNumber": "HT20261001", "docDate": "2026-10-03"}, {"id": "R2", "customer": "betpo", "poNumber": "HT20261002", "docDate": "2026-10-04"}]
    assert store.next_po_number("betpo", "2026-10-30") == "HT20261003" and store.next_po_number("betpo", "2026-11-02") == "HT20261101"
    assert "PO" in app.lot_bundle_modes({"customer": "betpo"})
    lot = Lot(app, store)
    lot.select_customer("betpo")
    lot.form["doc_date"] = "2026-11-02"
    lot.items = [{"stt": 1, "po": "", "hs": "48229090", "ma_sp": "44A020101.0636", "ten_sp": "Ống giấy 78 x 8 x 400mm (44A020101.0636)", "unit": "Chiếc", "qty": 1200, "price": 22100,
                  "amount": 26520000, "div": 20, "kg": 0.711, "kien": 60, "net": 853.2, "gross": 854.2, "tare": 1.0}]
    lot.fill_next_po()
    assert lot.form["po"] == "HT20261101" and lot.items[0]["po"] == "HT20261101"
    lot.form["pxk"] = "0000999"
    res = lot.export("PO")
    import openpyxl
    ws = openpyxl.load_workbook(res["files"][0]["path"]).worksheets[0]
    cells = {c.value for row in ws.iter_rows() for c in row if c.value is not None}
    assert "HT20261101" in " ".join(str(v) for v in cells) and 1200 in cells and 22100 in cells


TESA_V2 = """tesa Purchase Order: 5200049042 Page 2

Item Order Quantity Unit Material Delivery Date: Net Price (VND) Per Price Unit Net Value: (VND)
1 100 EA Paper core (1500) Oct 29, 2026 264,600.00 1 EA 26,460,000.00
Ramp
Your Material No.: Ø153 x 15 x 1500mm
Ø153 x 15 x 1500mm
Net Value: VND 26,460,000.00
@@HDR@@
tesa Purchase Order: 5200049042 Page 2
"""


def test_tesa_new_po_format_adds_code_from_erp(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    n0 = len(store.tesa_items)
    store.erp_catalog = [{"ma_sp": "TM91120-001-00099", "ten_sp": "Ống lõi giấy phi 153 x 15 x 1500mm", "mota": ""}]
    po, lines = app.parse_tesa_po_text(TESA_V2, store.tesa_items, store)
    assert po == "5200049042" and len(lines) == 1
    ln = lines[0]
    assert (ln["qty"], ln["price"], ln["amount"], ln["ma_sp"]) == (100, 264600, 26460000, "TM91120-001-00099")
    assert ln["read"] == "suy_ra" and "ERP" in ln["read_note"]
    assert len(store.tesa_items) == n0 + 1 and store.tesa_items[-1]["code"] == "TM91120-001-00099"
    store.remember_item_norm(ln["ten_sp"], 10, 4.2, "48229090")  # nhập kg/SL kiện một lần, lần sau tự có
    _po, again = app.parse_tesa_po_text(TESA_V2, store.tesa_items, store)
    assert len(store.tesa_items) == n0 + 1 and again[0]["kg"] == 4.2 and again[0]["kien"] == 10 and again[0]["read"] == "ok"
    exp = store.export_tesa_new()
    assert [x["code"] for x in exp["tesa_items"]] == ["TM91120-001-00099"]
    other = app.DedicatedDataStore(base_dir=str(tmp_path / "e"))
    assert other.import_learned(exp)["tesa"] == 1 and other.import_learned(exp).get("tesa", 0) == 0


def test_tesa_new_po_not_in_erp_still_reads(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    po, lines = app.parse_tesa_po_text(TESA_V2, store.tesa_items, store)
    assert lines[0]["ten_sp"] == "Ống lõi giấy phi 153 x 15 x 1500mm" and lines[0]["read"] == "suy_ra" and "đã thêm mới" in lines[0]["read_note"]


def test_tesa_name_comes_from_erp_product_list_of_customer(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    store.data_tong = [{"khach": "Tesa", "ten": "Ống lõi giấy phi 153 x 15 x 1500mm - ERP", "ma_hang": "", "ma_erp": "TM91120-001-00099", "kg": 4.5, "kg_nguon": "erp", "kien": 10}]
    store._dt_cache = {}
    po, lines = app.parse_tesa_po_text(TESA_V2, store.tesa_items, store)
    assert lines[0]["ten_sp"] == "Ống lõi giấy phi 153 x 15 x 1500mm - ERP" and lines[0]["ma_sp"] == "TM91120-001-00099"
    # PO dạng cũ có mã Tesa: tên danh mục có sẵn bị thay bằng tên ERP của khách
    store.data_tong = [{"khach": "Tesa", "ten": "Ống lõi giấy ERP 76.5x3x1390 Blue", "ma_hang": "39753-91390-00", "ma_erp": "TM91120-001-00007", "kg": 0.858, "kg_nguon": "erp", "kien": 250}]
    store._dt_cache = {}
    old = "tesa Purchase Order: 8600123456\n 1 39753-91390-00 Ống 500 EA 29,998.00 1 EA 14,999,000.00\n"
    r = app.parse_tesa_po_page(old + "@@HDR@@ 8600123456")
    if r:
        _po, ls = app.parse_tesa_po_text(old + "@@HDR@@ 8600123456", store.tesa_items, store)
        assert ls and ls[0]["ten_sp"] == "Ống lõi giấy ERP 76.5x3x1390 Blue"


def test_po_number_from_order_cell_label():
    f = app.find_po_after_label
    assert f("Mã đơn đặt hàng/ 订单编号\nYNCGDD2611050001\nNgày giao") == "YNCGDD2611050001"
    assert f("Mã đơn đặt hàng/\n订单编号\n13060706026 Tên hàng") == "13060706026"
    assert f("mã PO: 4500123456") == "4500123456" and f("không có nhãn 13060706026") == ""


def test_tesa_new_code_takes_name_from_erp_customer_product_name(tmp_path):
    """Mã Tesa chưa có trong danh mục riêng: tên lấy từ cột 'Tên sản phẩm theo KH' của ERP (tìm theo mã nằm trong ngoặc tên), kèm mã hàng."""
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    ten_kh = "Ống lõi giấy phi 33.2 x 2.65 x 19mm_Blue (39764-90019-00)- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013550)"
    store.tesa_items = [x for x in store.tesa_items if x.get("code") != "39764-90019-00"]
    store.data_tong = [{"khach": "Tesa", "ten": "ống 33.02x2.65x19", "ma_hang": "", "ma_erp": "FG10291-004-00000", "ten_kh": ten_kh, "khach_day_du": "CÔNG TY TNHH TESA SITE HẢI PHÒNG", "kg": 0.005, "kg_nguon": "erp"}]
    store._dt_cache = {}
    old = "tesa Purchase Order: 8600229092\n 1 39764-90019-00 Ống 136000 EA 265.00 1 EA 36,040,000.00\n"
    _po, ls = app.parse_tesa_po_text(old + "@@HDR@@ 8600229092", store.tesa_items, store)
    assert ls and ls[0]["ten_sp"] == ten_kh and ls[0]["ma_sp"] == "39764-90019-00"
    assert store.dt_lookup("tesa", "", "39764-90019-00")["ten_kh"] == ten_kh


def test_mapping_import_keeps_tesa_code_in_customer_name(tmp_path):
    import openpyxl
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    store.data_tong = [{"khach": "Tesa", "ten": "ống 33x2", "ma_erp": "FG10291-004-00000", "kg": 0.005, "kg_nguon": "erp"}]
    ten_kh = "Ống lõi giấy phi 33.2 x 2.65 x 19mm_Blue (39764-90019-00)- FSC RECYCLED 100%"
    wb = openpyxl.Workbook()
    wb.active.append(["Mã sản phẩm gốc", "Tên sản phẩm gốc", "Mã khách hàng", "Tên khách hàng", "Mã sản phẩm theo KH", "Tên sản phẩm theo KH"])
    wb.active.append(["FG10291-004-00000", "ống 33", "10291", "CÔNG TY TNHH TESA SITE HẢI PHÒNG", "FG10291-004-0", ten_kh])
    f = tmp_path / "m.xlsx"
    wb.save(f)
    store.dt_import_mapping(str(f))
    assert store.data_tong[0]["ma_kh"] == "39764-90019-00" and store.data_tong[0]["ten_kh"] == ten_kh


def test_code_put_in_name_field_moves_to_code_and_resolves_name(tmp_path):
    """OCR đọc gạch nối mã Tesa thành gạch khác -> mã vào ô tên: phải chuyển về ô mã và tra tên theo mã."""
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    ten_kh = "Ống lõi giấy phi 33.2 x 2.65 x 19mm_Blue (39764-90019-00)- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013550)"
    store.tesa_items = [x for x in store.tesa_items if x.get("code") != "39764-90019-00"]
    store.data_tong = [{"khach": "Tesa", "ten": "ống 33x2", "ma_erp": "FG10291-004-00000", "ma_kh": "39764-90019-00", "ten_kh": ten_kh, "kg": 0.005, "kg_nguon": "erp"}]
    store._dt_cache = {}
    row = {"ma_sp": "", "ten_sp": "39764‑90019‑00", "qty": 136000, "div": 0, "kg": 0}
    keep = {"ma_sp": "X1", "ten_sp": "Ống A"}
    assert app.lot_fix_code_names(store, "tesa", [row, keep]) == 1
    assert (row["ma_sp"], row["ten_sp"], row["kg"]) == ("39764-90019-00", ten_kh, 0.005) and keep["ma_sp"] == "X1"
    page = "tesa Purchase Order: 8600228821\n 1 39764‑90019‑00 Ống 136000 EA 265.00 1 EA 36,040,000.00\n"
    assert app.parse_tesa_po_page(page + "@@HDR@@ 8600228821")["code"] == "39764-90019-00"


def test_tesa_v2_code_only_in_material_column(tmp_path):
    """PO Tesa không có dòng 'Your Material No.': mã nằm ở cột Material -> phải vào ô mã hàng, không vào ô tên."""
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    t = ("tesa Purchase Order: 8600228821\n1 136000 EA 39777-90019-00 Nov 02, 2026 265.00 1 EA 36,040,000.00\nNet Value: VND 36,040,000.00\n@@HDR@@\ntesa Purchase Order: 8600228821\n")
    _po, ls = app.parse_tesa_po_text(t, store.tesa_items, store)
    assert ls[0]["ma_sp"] == "39777-90019-00" and ls[0]["ten_sp"] != "39777-90019-00" and "39777-90019-00" in ls[0]["ten_sp"]


def test_tesa_line_with_complete_info_is_not_flagged(tmp_path):
    """Dòng Tesa đủ mã, tên, kg, SL/kiện và SL x giá = thành tiền: không cảnh báo 'máy phải suy ra', dù tên lấy từ ERP."""
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    ten_kh = "Ống lõi giấy phi 33.2 x 2.65 x 19mm_Blue (39764-90019-00)- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013550)"
    store.tesa_items = [x for x in store.tesa_items if x.get("code") != "39764-90019-00"]
    store.data_tong = [{"khach": "Tesa", "ten": "ống 33x2", "ma_erp": "FG10291-004-00000", "ma_kh": "39764-90019-00", "ten_kh": ten_kh, "kg": 0.005, "kg_nguon": "erp", "kien": 34000, "kien_nguon": "tay"}]
    store._dt_cache = {}
    store.remember_item_norm(ten_kh, 34000, 0.005, "48229090")
    t = "tesa Purchase Order: 8600228821\n10 136,000 PC 39764-90019-00 Nov 26, 2026 26,500.00 100 PC 36,040,000.00\n@@HDR@@\ntesa Purchase Order: 8600228821\n"
    _po, ls = app.parse_tesa_po_text(t, store.tesa_items, store)
    assert ls[0]["ten_sp"] == ten_kh and ls[0]["read"] == "ok" and ls[0]["read_note"] == ""


def test_tesa_name_prefers_customer_product_name_and_old_code_names_are_fixed(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    ten_kh = "Ống lõi giấy phi 33.2 x 2.65 x 19mm_51036 (39777-90019-00)- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013550)"
    store.data_tong = [{"khach": "Tesa", "ten": "ống 33.02x2.65x19, T.tem Tesa 51036 đỏ (39777-90019-00)", "ma_erp": "FG10291-001-00000", "ma_kh": "39777-90019-00", "ten_kh": ten_kh, "kg": 0.005, "kg_nguon": "erp"}]
    store._dt_cache = {}
    t = "tesa Purchase Order: 8600229092\n10 136,000 PC 39777-90019-00 Dec 16, 2026 26,500.00 100 PC 36,040,000.00\n@@HDR@@\ntesa Purchase Order: 8600229092\n"
    _po, ls = app.parse_tesa_po_text(t, store.tesa_items, store)
    assert ls[0]["ten_sp"] == ten_kh
    old = {"ma_sp": "39777-90019-00", "ten_sp": "39777-90019-00", "qty": 1, "div": 0, "kg": 0}  # lô lưu từ bản cũ: tên = mã
    assert app.lot_fix_code_names(store, "tesa", [old]) == 1 and old["ten_sp"] == ten_kh


def test_tesa_name_missing_fsc_suffix_is_completed():
    short = "Ống lõi giấy phi 33.2 x 2.65 x 19mm_Blue (39764-90019-00)"
    full = short + "- FSC RECYCLED 100%(Số chứng chỉ:TAH-COC-013550)"
    assert app.tesa_full_name(short) == full and app.tesa_full_name(full) == full and app.tesa_full_name("Ống lõi giấy phi 153 x 15 x 1500mm") == "Ống lõi giấy phi 153 x 15 x 1500mm"
    row = {"ma_sp": "39764-90019-00", "ten_sp": short, "ten_hq": short}
    assert app.lot_fix_code_names(None, "tesa", [row]) == 2 and row["ten_sp"] == full and row["ten_hq"] == full

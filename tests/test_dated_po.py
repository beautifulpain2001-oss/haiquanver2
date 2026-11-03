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

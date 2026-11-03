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

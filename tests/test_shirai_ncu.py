"""Shirai: chọn nhà cung ứng theo nhóm hàng (carton / inner pad / pad), tên hàng theo khách hàng lấy từ ERP, chặn khi thiếu. Dữ liệu giả."""

import os

import openpyxl
import pytest

import hongthien_desktop_app as app
from ui_qt.state import Lot

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "po_shirai_gia.xls")


@pytest.fixture
def lot(store):
    lot = Lot(app, store)
    lot.select_customer("shirai")
    assert lot.apply_po(lot.read_po(FIXTURE))
    return lot


def erp_names(store, lot, skip=()):
    """Dữ liệu ERP giả: mỗi mã của lô có 'Tên sản phẩm theo KH', trừ các mã trong skip."""
    store.data_tong = [{"khach": "Shirai", "ten": f"erp {it['ma_sp']}", "ma_erp": it["ma_sp"], "ma_kh": "", "ten_kh": f"TÊN KH {it['ma_sp']}", "kg": 0.1, "kg_nguon": "erp"}
                       for it in lot.items if it["ma_sp"] and it["ma_sp"] not in skip]
    store._dt_cache = {}


def test_groups_follow_item_names(store):
    g = app.DedicatedDataStore.shirai_group
    assert [g("Thùng Carton Box FUL-1080SDNA"), g("Tấm Inner Pad FUL-1255"), g("Tấm lót Pad FUL-1065D"), g("Pad for FUL-1255DGH"), g("Ống giấy")] == ["carton", "inner", "pad", "pad", "khac"]


def test_missing_customer_name_and_supplier_block_then_clear(store, lot):
    codes = sorted({it["ma_sp"] for it in lot.items if it["ma_sp"]})
    erp_names(store, lot, skip=codes[:1])
    lot.apply_suppliers()
    b = lot.ncu_blockers()
    assert any("Chưa có tên theo khách hàng" in x and codes[0] in x for x in b)
    assert any("nhà cung ứng" in x for x in b)  # chưa có danh sách nhà cung ứng
    errors, _w = lot.validate()
    assert errors == b  # không xuất được
    lot.set_ten_kh(codes[0], "Tên nhập tay")
    nocode = next(i for i in lot.items if not i["ma_sp"])  # dòng không có mã: tên nhập tay nhớ theo tên gốc trên PO
    assert any("(không mã)" in x for x in lot.ncu_blockers())
    lot.set_ten_kh("", "Tên dòng không mã", nocode["ten_goc"])
    store.supplier_add("Công ty A")
    store.supplier_add("Công ty B")
    for key, _label, _idx in lot.ncu_groups():
        lot.set_group_supplier(key, "Công ty A")
    assert lot.ncu_blockers() == []
    assert all(it["ten_sp"].startswith("TÊN KH") or it["ten_sp"] in ("Tên nhập tay", "Tên dòng không mã") for it in lot.items)


def test_group_choice_override_by_code_remembered_and_in_so_sheet(store, lot):
    erp_names(store, lot)
    store.supplier_add("Công ty A")
    store.supplier_add("Công ty B")
    groups = lot.ncu_groups()
    assert groups
    first_key = groups[0][0]
    lot.set_group_supplier(first_key, "Công ty A")
    idx = groups[0][2]
    idx = [i for i in idx if lot.items[i]["ma_sp"]] or idx
    code = lot.items[idx[0]]["ma_sp"]
    lot.set_code_supplier(code, "Công ty B")
    assert lot.items[idx[0]]["ncu"] == "Công ty B"
    assert all(lot.items[i]["ncu"] == "Công ty A" for i in idx if lot.items[i]["ma_sp"] != code)
    assert store.supplier_pref["nhom:" + first_key] == "Công ty A" and store.supplier_pref["ma:" + code] == "Công ty B"
    # lô mới nhớ lựa chọn cũ
    other = Lot(app, store)
    other.select_customer("shirai")
    assert other.apply_po(other.read_po(FIXTURE))
    assert next(i for i in other.items if i["ma_sp"] == code)["ncu"] == "Công ty B"
    rec = lot.record()
    assert [i["ncu"] for i in rec["items"]]
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "SO")["path"]).active
    assert ws.cell(row=4, column=17).value == "Nhà cung ứng" and ws.cell(row=5, column=17).value in ("Công ty A", "Công ty B")


def test_supplier_remove_drops_remembered_choices(store):
    store.supplier_add("Công ty A")
    store.supplier_pref["nhom:pad"] = "Công ty A"
    store.supplier_remove("Công ty A")
    assert store.suppliers == [] and "nhom:pad" not in store.supplier_pref
    reloaded = app.DedicatedDataStore(base_dir=store.base_dir)
    assert reloaded.suppliers == []


def test_po_step_shows_supplier_box_for_shirai_and_blocks_next(qapp, store, lot):
    from ui_qt.pages_lot import LotPage
    erp_names(store, lot, skip=[lot.items[0]["ma_sp"]])
    page = LotPage(app, store)
    page.lot = lot
    page.step2.lot = lot
    page.go(1)
    page.step2.refresh()
    assert not page.step2.ncu_box.isHidden() and page.step2.ncu_widgets
    page.refresh_buttons()
    assert not page.next.isEnabled()
    page.close()

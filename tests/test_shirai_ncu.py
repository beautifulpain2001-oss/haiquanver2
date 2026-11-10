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
    assert any("không mã" in x for x in lot.ncu_blockers())
    lot.set_ten_kh("", "Tên dòng không mã", nocode["ten_goc"])
    store.supplier_add("Công ty A")
    store.supplier_add("Công ty B")
    assert any("định danh" in x for x in lot.ncu_blockers())
    for it in lot.items:
        lot.set_ident_supplier(it.get("ncu_id", ""), "Công ty A", it["ma_sp"])
    assert lot.ncu_blockers() == []
    assert all(it["ten_sp"].startswith("TÊN KH") or it["ten_sp"] in ("Tên nhập tay", "Tên dòng không mã") for it in lot.items)


def test_supplier_follows_erp_code_identifier_not_the_name(store, lot):
    assert Lot.ncu_ident("TM91177-001-00124") == "91177" and Lot.ncu_ident("TM91120-001-00040") == "91120" and Lot.ncu_ident("") == ""
    erp_names(store, lot)
    store.supplier_add("Công ty A")
    store.supplier_add("Công ty B")
    pads = [i for i in lot.items if i["ma_sp"].startswith("TM91120")]
    assert pads
    lot.set_ident_supplier("91120", "Công ty B")
    assert all(i["ncu"] == "Công ty B" for i in lot.items if i["ncu_id"] == "91120")  # mọi mã cùng định danh
    other = [i for i in lot.items if i["ncu_id"] != "91120" and i["ma_sp"]]
    assert all(not i["ncu"] for i in other)
    assert store.supplier_pref["id:91120"] == "Công ty B"
    # lô mới nhớ lựa chọn theo định danh
    again = Lot(app, store)
    again.select_customer("shirai")
    assert again.apply_po(again.read_po(FIXTURE))
    assert all(i["ncu"] == "Công ty B" for i in again.items if i["ncu_id"] == "91120")
    rec = lot.record()
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "SO")["path"]).active
    assert ws.cell(row=4, column=17).value == "Nhà cung ứng" and "Công ty B" in {ws.cell(row=r, column=17).value for r in range(5, 9)}


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

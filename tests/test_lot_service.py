"""Kiểm thử các hàm lô hàng dùng chung (lot_*) không cần giao diện: dựng hồ sơ, xuất Excel,
lưu hồ sơ ở Bước 1/Bước 2 và nạp lại. Dữ liệu mẫu có sẵn của Shirai/Kodi/Tesa."""

import json
import os

import openpyxl
import pytest

import hongthien_desktop_app as app


def form_of(rec):
    return {
        "customer": rec["customer"], "doc_date": rec["docDate"], "po": rec["poNumber"],
        "po_date": rec.get("poDate", ""), "pxk": rec.get("pxkNo", ""), "hd": rec.get("hdNo", ""),
        "tk": rec.get("tkNo", ""), "luong": rec.get("luong", "Xanh"), "xe": rec.get("xeNo", ""),
        "driver": rec.get("driver", ""), "ldd": rec.get("lddSeq", ""), "po_dates": rec.get("poDates"),
        "pay_days": rec.get("payDays", ""), "delivery": rec.get("deliveryDate", ""),
    }


def test_recalc_computes_kien_net_gross():
    items = [{"qty": 1000, "div": 100, "kg": 0.5}, {"qty": 250, "div": 100, "kg": 0}]
    app.lot_recalc(items, "kodi", "1")
    assert items[0]["kien"] == 10 and items[0]["net"] == 500.0 and items[0]["gross"] == 501.0
    assert items[1]["kien"] == 3  # làm tròn lên
    assert "net" not in items[1]  # thiếu kg/chiếc thì không đoán trọng lượng


def test_recalc_bad_tare_falls_back_to_one():
    items = [{"qty": 10, "div": 10, "kg": 1}]
    app.lot_recalc(items, "kodi", "abc")
    assert items[0]["gross"] == 11.0


@pytest.mark.parametrize("customer", ["shirai", "kodi", "tesa"])
def test_build_record_totals_and_blank_files(store, seed, customer):
    src = seed[customer]
    rec = app.lot_build_record(store, form_of(src), src["items"])
    assert rec["customer"] == customer and rec["zone"] == "WORKING"
    assert rec["poNumber"] == src["poNumber"]
    assert rec["totalQty"] == sum(float(x["qty"]) for x in src["items"])
    assert rec["files"] == {"po": None, "pxk": None, "vat": None, "pkl": None, "tk": None, "scan": None}
    assert rec["items"] is not src["items"]  # là bản sao, sửa không ảnh hưởng dòng đang làm


def test_build_record_empty_date_uses_today_and_strips(store, seed):
    src = seed["kodi"]
    form = form_of(src) | {"doc_date": "  ", "po": "  PO-1  "}
    rec = app.lot_build_record(store, form, src["items"])
    assert rec["poNumber"] == "PO-1"
    assert len(rec["docDate"]) == 10 and rec["scheduleKey"] == rec["docDate"][8:10] + "." + rec["docDate"][5:7]


def test_export_all_writes_workbook_with_check_sheet(store, seed):
    src = seed["kodi"]
    rec = app.lot_build_record(store, form_of(src), src["items"])
    res = app.lot_export(store, rec, "ALL")
    assert os.path.isfile(res["path"]) and res["dsh"] is None
    wb = openpyxl.load_workbook(res["path"])
    assert any(n.startswith("KiemTra") for n in wb.sheetnames)


@pytest.mark.parametrize("mode", ["VAT", "PKL", "PXK", "DNTT", "PLX"])
def test_export_single_modes(store, seed, mode):
    src = seed["tesa"]
    rec = app.lot_build_record(store, form_of(src), src["items"])
    res = app.lot_export(store, rec, mode)
    assert os.path.isfile(res["path"]) and res["problems"] == []


def test_export_errors_are_vietnamese_value_errors(store, seed):
    src = seed["kodi"]
    empty = app.lot_build_record(store, form_of(src), [])
    with pytest.raises(ValueError, match="Chưa có dòng hàng"):
        app.lot_export(store, empty, "ALL")
    rec = app.lot_build_record(store, form_of(src), src["items"])
    with pytest.raises(ValueError, match="bộ mẫu 'best'"):
        app.lot_export(store, rec, "BEST")


def test_save_new_adds_then_overwrites_same_customer_and_po(store, seed):
    src = seed["kodi"]
    n0 = len(store.records)
    rec = app.lot_build_record(store, form_of(src) | {"po": "PO-GIA-1"}, src["items"])
    old = app.lot_save_new(store, rec, {"vat": {"name": "vat.xlsx", "path": "x", "time": "t"}})
    assert len(store.records) == n0 + 1 and store.records[0] is old

    rec2 = app.lot_build_record(store, form_of(src) | {"po": "PO-GIA-1", "pxk": "777"}, src["items"])
    new = app.lot_save_new(store, rec2, {"pxk": {"name": "pxk.xlsx", "path": "y", "time": "t"}})
    assert len(store.records) == n0 + 1  # cùng khách + cùng PO: ghi đè, không thêm
    assert new["id"] == old["id"] and new["pxkNo"] == "777"
    assert new["files"]["vat"]["name"] == "vat.xlsx"  # giữ file đã nạp ở lần trước
    assert new["files"]["pxk"]["name"] == "pxk.xlsx"


def test_save_persists_and_reloads_from_disk(store, seed, data_dir):
    src = seed["tesa"]
    rec = app.lot_build_record(store, form_of(src) | {"po": "PO-GIA-2"}, src["items"])
    app.lot_save_new(store, rec, {})
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    found = next(r for r in again.records if r["poNumber"] == "PO-GIA-2")
    assert found["items"] == rec["items"] and found["customer"] == "tesa"


def test_save_workbench_writes_meta_and_updates_by_id(store, seed):
    src = seed["kodi"]
    rec = app.lot_save_new(store, app.lot_build_record(store, form_of(src) | {"po": "PO-GIA-3"}, src["items"]), {})
    rec["zone"] = "ARCHIVE"
    rec["hdNo"] = "HD-9"
    dest = app.lot_save_workbench(store, rec)
    meta = os.path.join(dest, f"00_HO_SO_{rec['id']}.json")
    with open(meta, encoding="utf-8") as f:
        assert json.load(f)["hdNo"] == "HD-9"
    assert dest == store.get_record_folder_path(rec)
    assert sum(1 for r in store.records if r["id"] == rec["id"]) == 1
    assert next(r for r in store.records if r["id"] == rec["id"])["zone"] == "ARCHIVE"


def test_partial_cartons_round_up_and_do_not_warn(store):
    """Kiện lẻ làm tròn lên (1000/75 = 13,33 -> 14; 13,09 -> 14; chia hết thì giữ nguyên) và không còn cảnh báo kiện lẻ."""
    import hongthien_desktop_app as app
    for qty, div, want in ((1000, 75, 14), (1309, 100, 14), (1300, 100, 13), (1301, 100, 14), (5520, 84, 66), (1, 75, 1)):
        vals = {"po": "P", "ma_sp": "X", "ten_sp": "Hàng thử", "hs": "48229090", "unit": "cái", "qty": str(qty), "price": "100", "div": str(div), "kg": "0.1"}
        item = app.lot_item_from_values(store, "kodi", vals, "1.0")
        assert item["kien"] == want, (qty, div, item["kien"])
        warns = app.check_lot({"customer": "kodi", "items": [item]})
        assert not any("kiện lẻ" in w or "chia hết" in w for w in warns)

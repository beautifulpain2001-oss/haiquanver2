"""Kiểm thử trạng thái lô của giao diện mới (ui_qt/state.py) - không cần Qt hay màn hình."""

import os

import pytest

import hongthien_desktop_app as app
from test_po_parsers import KODI_PO_TEXT
from ui_qt.state import Lot


@pytest.fixture
def lot(store):
    return Lot(app, store)


@pytest.fixture
def kodi_lot(lot, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "extract_text_from_pdf_or_image_offline", lambda *a, **k: KODI_PO_TEXT)
    lot.select_customer("kodi")
    po = tmp_path / "po.pdf"
    po.write_bytes(b"%PDF-1.4")
    assert lot.apply_po(lot.read_po(str(po)))
    return lot


def test_new_lot_needs_customer(lot):
    errors, _ = lot.validate()
    assert errors == ["Chưa chọn khách hàng."]


def test_select_customer_sets_defaults(lot):
    lot.select_customer("tesa")
    assert lot.form["tare"] == "0.0" and lot.form["xe"] == app.PROFILES["tesa"]["xe"]
    lot.select_customer("kodi")
    assert lot.form["tare"] == "1.0" and lot.items == []


def test_load_po_fills_form_and_items(kodi_lot):
    assert kodi_lot.form["po"] == "03102026-01KDHT" and kodi_lot.form["po_date"] == "03/10/2026"
    assert [x["qty"] for x in kodi_lot.items] == [1000, 500]


def test_load_po_unreadable_keeps_state(lot, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "extract_text_from_pdf_or_image_offline", lambda *a, **k: "không có gì")
    lot.select_customer("kodi")
    f = tmp_path / "x.pdf"
    f.write_bytes(b"x")
    res = lot.read_po(str(f))
    assert not res["ok"] and res["msg"] and not lot.apply_po(res) and lot.items == []


def test_append_not_allowed_for_builtin_customers(kodi_lot, tmp_path):
    with pytest.raises(ValueError, match="khách đã học"):
        kodi_lot.read_po(str(tmp_path / "po.pdf"), append=True)


def test_item_add_edit_delete_and_row_issues(kodi_lot):
    v = kodi_lot.new_item_values()
    v.update(po="PO-1", ma_sp="X", ten_sp="Ống thử", qty="100", price="1,000", div="10", kg="0.5")
    item = kodi_lot.save_item({k: str(x) for k, x in v.items()})
    assert (item["kien"], item["net"], item["amount"]) == (10, 50.0, 100000)
    assert len(kodi_lot.items) == 3
    kodi_lot.save_item({"po": "PO-1", "ten_sp": "Ống thử", "qty": "100", "price": "1000", "div": "0", "kg": "0", "hs": "48229090", "unit": "ống"}, idx=2)
    assert kodi_lot.row_issues(kodi_lot.items[2]) == ["Thiếu kg/chiếc", "Thiếu SL/kiện"]
    kodi_lot.delete_item(2)
    assert len(kodi_lot.items) == 2


def test_item_rejects_bad_numbers_and_missing_name(kodi_lot):
    with pytest.raises(ValueError, match="phải là số"):
        kodi_lot.save_item({"ten_sp": "A", "qty": "abc"})
    with pytest.raises(ValueError, match="tên hàng"):
        kodi_lot.save_item({"ten_sp": "", "qty": "1", "price": "1", "div": "1", "kg": "1"})


def test_validate_warns_missing_pxk_then_export_save_reload(kodi_lot, store):
    errors, warns = kodi_lot.validate()
    assert errors == [] and any("PXK" in w for w in warns)
    kodi_lot.form.update(pxk="0000777", hd="0000888")
    res = kodi_lot.export("ALL")
    assert all(os.path.isfile(f["path"]) for f in res["files"])
    assert {"vat", "pxk", "pkl"} <= set(kodi_lot.exported)
    rec = kodi_lot.save()
    vat_name = next(f["name"] for f in res["files"] if f["mode"] == "VAT")
    assert kodi_lot.saved and rec["pxkNo"] == "0000777" and rec["files"]["vat"]["name"] == vat_name
    other = Lot(app, store)
    other.load_record(rec)
    assert other.customer == "kodi" and other.form["pxk"] == "0000777" and len(other.items) == 2 and other.saved


def test_export_all_makes_one_file_per_document(kodi_lot):
    kodi_lot.form.update(pxk="0000777", hd="0000888")
    res = kodi_lot.export("ALL")
    assert [f["mode"] for f in res["files"]] == ["PKL", "VAT", "PXK", "DNTT", "CHECK"]
    assert len({f["path"] for f in res["files"]}) == 5  # mỗi chứng từ một file riêng
    import openpyxl
    for f in res["files"]:
        assert len(openpyxl.load_workbook(f["path"]).sheetnames) == 1  # mỗi file chỉ một chứng từ
    assert [x["mode"] for x in kodi_lot.files] == ["PKL", "VAT", "PXK", "DNTT", "CHECK"]


def test_exporting_again_replaces_entry_not_duplicates(kodi_lot):
    kodi_lot.export("ALL")
    kodi_lot.export("VAT")
    assert [f["mode"] for f in kodi_lot.files].count("VAT") == 1


@pytest.mark.parametrize("customer,expected", [
    ("shirai", ["SO", "PKL", "VAT", "PXK", "DNTT", "CHECK"]),
    ("kodi", ["PKL", "VAT", "PXK", "DNTT", "CHECK"]),
    ("tesa", ["PKL", "VAT", "PXK", "PLX", "DNTT", "CHECK"]),
])
def test_bundle_modes_match_full_bundle_per_customer(store, seed, customer, expected):
    assert app.lot_bundle_modes(seed[customer]) == expected


def test_single_modes_reject_wrong_customer(store, seed):
    rec = app.lot_build_record(store, {"customer": "kodi", "po": "P"}, seed["kodi"]["items"])
    for mode in ("SO", "PACK", "PGH", "DCCN"):
        with pytest.raises(ValueError):
            app.lot_export(store, rec, mode)


def test_export_without_items_is_a_clear_error(lot):
    lot.select_customer("kodi")
    with pytest.raises(ValueError, match="Chưa có dòng hàng"):
        lot.export("ALL")


def test_recalc_uses_form_tare(kodi_lot):
    kodi_lot.form["tare"] = "2"
    kodi_lot.recalc()
    assert kodi_lot.items[0]["gross"] == kodi_lot.items[0]["net"] + 2


def test_vehicle_defaults_follow_customer_saved_after_selecting(lot, store):
    """Lưu lái xe/biển số ở mục Khách hàng sau khi đã chọn khách: ô Thông tin chuyến vẫn lấy được."""
    lot.select_customer("kodi")
    lot.form["xe"] = lot.form["driver"] = ""
    store.update_customer("kodi", {"driver": "Lái Mới", "xe": "Ô tô tải: 99X-111.11"})
    lot.fill_vehicle_defaults()
    assert lot.form["driver"] == "Lái Mới" and lot.form["xe"] == "99X-111.11"

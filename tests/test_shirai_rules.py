"""Quy luật làm invoice Shirai học từ bộ 1 (dữ liệu giả cùng cấu trúc): đọc .xls, tên hàng, số kiện, cả bì, thành tiền,
chọn ngày giao để khai, nạp dữ liệu học. Không dùng số liệu thật của khách."""

import json
import math
import os
import struct

import pytest

import hongthien_desktop_app as app
from ui_qt.state import Lot

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "po_shirai_gia.xls")


# ---------------------------------------------------------------- làm tròn và cả bì
@pytest.mark.parametrize("x,expected", [(51.145, 51.15), (2.675, 2.68), (0.285, 0.29), (56.39, 56.39), (53 * 0.965, 51.15), (1.0049, 1.0)])
def test_round_half_up_matches_excel(x, expected):
    assert app.round_half_up(x, 2) == expected


@pytest.mark.parametrize("net,tare,expected", [
    (18.36, "0.02", 18.38), (18.36, "0.01", 18.37), (18.36, "0,02", 18.38),  # dấu phẩy thập phân kiểu Việt Nam
    (18.36, "", 18.36), (18.36, "0.08%", 18.37), (110.66, "0.08%", 110.75), (0, "0.02", 0.0),
])
def test_lot_gross_fixed_or_percent(net, tare, expected):
    assert app.lot_gross(net, tare) == expected


def test_lot_gross_rejects_garbage():
    with pytest.raises(ValueError):
        app.lot_gross(10, "abc")


# ---------------------------------------------------------------- SL/kiện mặc định theo loại
@pytest.mark.parametrize("name,expected", [
    ("Thùng Carton Box FUL-1040HDK(W1233xD118xH409)", 10),
    ("Tấm lót Pad FUL-1040H(AF_1B:W117xD117xH402)", 50),
    ("Tấm lót Pad FUL-1180D1/2(AF_1:W770xD5xH95)", 50),
    ("Tấm lót Pad FUL-8011H1/2(BF_1:W760xD3xH90)", 50),
    ("Tấm lót Pad FUL-1040H(WF_1:W345xD8xH390)", 20),
    ("Tấm lót Pad FUL-1040H(WF_2:W390xD8xH390)", 20),
    ("Tấm Inner Pad Special FUL-1255DGH ( W271 x D12 x H641)", 50),
    ("Tấm lót Pad for FUL-4055G (WF: W525 x D8 x H75)", 0),   # WF/BF không có số thứ tự: không đoán
    ("Tấm lót Pad for FUL-1255DGH (BF: W530 x D3 x H290)", 0),
    ("Hàng lạ không có dấu hiệu", 0),
])
def test_shirai_default_div(name, expected):
    assert app.shirai_default_div(name) == expected


# ---------------------------------------------------------------- đọc .xls
def test_reads_real_xls_with_dates(store):
    rows = app.excel_rows(FIXTURE)
    assert rows[18][5].strftime("%Y-%m-%d") == "2026-10-25"  # ô ngày .xls trả về datetime
    po, schedules = app.parse_shirai_po_excel(FIXTURE, store)
    assert po == "202699HT"
    assert {k: len(v["items"]) for k, v in schedules.items()} == {"25.10": 2, "29.10": 2}


def test_xlrd_patch_ignores_broken_external_link_names():
    xlrd = pytest.importorskip("xlrd")
    app._patch_xlrd()
    from xlrd import book
    bad = struct.pack("<H", 2) + b"\x01" + b"\x00\xd8\x00\xd8"  # UTF-16 hỏng (surrogate lẻ) như file Shirai thật
    assert book.unpack_unicode_update_pos(bad, 0, lenlen=2) == ("", len(bad))


def test_xls_without_xlrd_gives_clear_message(monkeypatch, tmp_path):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "xlrd":
            raise ImportError
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(ValueError, match="xlrd"):
        app.excel_rows(str(tmp_path / "x.xls"))


# ---------------------------------------------------------------- quy luật dòng hàng
@pytest.fixture
def items(store):
    _, schedules = app.parse_shirai_po_excel(FIXTURE, store)
    return {it["ten_sp"]: it for v in schedules.values() for it in v["items"]}


def test_names_follow_invoice_convention(items):
    assert "Thùng Carton Box FUL-1080SDNA (W936xD186xH405)" in items
    assert "Tấm lót Pad FUL-1065D (AF_1B: W125xD105xH360)" in items
    assert "Tấm Inner Pad Special FUL-1255DGH ( W271 x D12 x H641)" in items  # Inner Pad: "Tấm", không "Tấm lót"
    assert not any("lót Inner" in n for n in items)


def test_kien_net_gross_use_rules_and_half_up(items):
    box = items["Thùng Carton Box FUL-1080SDNA (W936xD186xH405)"]
    assert box["div"] == 10 and box["kien"] == 6  # 53 / 10 làm tròn lên
    assert box["net"] == app.round_half_up(53 * box["kg"], 2) and box["gross"] == app.round_half_up(box["net"] + 0.02, 2)
    pad = items["Tấm lót Pad FUL-1065D (AF_1B: W125xD105xH360)"]
    assert pad["div"] == 50 and pad["kien"] == 5  # 204 / 50


def test_remembered_norm_beats_default_rule(store):
    name = "Tấm lót Pad FUL-1065D (AF_1B: W125xD105xH360)"
    store.import_learned({"item_mem": {name: {"div": 100, "kg": 0, "hs": ""}}})
    _, schedules = app.parse_shirai_po_excel(FIXTURE, store)
    pad = next(it for v in schedules.values() for it in v["items"] if it["ten_sp"] == name)
    assert pad["div"] == 100 and pad["kien"] == 3  # 204 / 100


def test_tare_percent_option_reproduces_percentage_gross(store):
    _, schedules = app.parse_shirai_po_excel(FIXTURE, store, "0.08%")
    box = schedules["25.10"]["items"][0]
    assert box["gross"] == app.round_half_up(box["net"] * 1.0008, 2)


# ---------------------------------------------------------------- thành tiền = SL x đơn giá; lệch thì báo
def test_amount_is_always_qty_times_price_and_mismatch_is_reported(store, items):
    inner = items["Tấm Inner Pad Special FUL-1255DGH ( W271 x D12 x H641)"]
    assert inner["amount"] == 455 * 6237 and inner["po_amount"] == 2837000  # thành tiền trên PO lệch, phần mềm không theo
    box = items["Thùng Carton Box FUL-1080SDNA (W936xD186xH405)"]
    assert box["amount"] == box["po_amount"] == 1325000
    warns = app.check_lot({"customer": "shirai", "items": list(items.values())})
    mism = [w for w in warns if "thành tiền trên PO" in w]
    assert len(mism) == 1 and "Inner Pad" in mism[0] and "2,837,000" in mism[0] and "2,837,835" in mism[0]


def test_check_lot_missing_div_is_reported(store, items):
    it = dict(items["Thùng Carton Box FUL-1080SDNA (W936xD186xH405)"], div=0, kien=0)
    assert any("chưa có SL/kiện" in w for w in app.check_lot({"customer": "shirai", "items": [it]}))


# ---------------------------------------------------------------- chọn ngày giao để khai
def test_load_po_default_is_one_invoice_for_all_dates_in_po_order(store):
    res = app.lot_load_po(store, FIXTURE, "shirai", "0.02")
    assert res["ok"] and len(res["items"]) == 4 and sorted(res["schedules"]) == ["25.10", "29.10"]
    assert [it["stt"] for it in res["items"]] == [1, 2, 3, 4]
    assert [it["po_seq"] for it in res["items"]] == sorted(it["po_seq"] for it in res["items"])  # đúng thứ tự dòng của PO


@pytest.fixture
def lot(store):
    lot = Lot(app, store)
    lot.select_customer("shirai")
    assert lot.apply_po(lot.read_po(FIXTURE))
    return lot


def test_choose_which_delivery_dates_to_declare(lot):
    assert lot.selected_dates == ["25.10", "29.10"] and len(lot.items) == 4
    lot.set_dates(["29.10"])
    assert len(lot.items) == 2 and {it["po"] for it in lot.items} == {"202699HT"} and [it["stt"] for it in lot.items] == [1, 2]
    lot.set_dates(["25.10", "29.10"])
    assert len(lot.items) == 4  # chọn lại cả hai: trở về một invoice
    with pytest.raises(ValueError, match="ít nhất một ngày"):
        lot.set_dates([])


def test_same_po_declared_on_two_days_makes_two_records_and_two_folders(store, lot):
    lot.form.update(doc_date="2026-10-25", pxk="0000001")
    lot.set_dates(["25.10"])
    lot.export("PKL")
    rec1 = lot.save()
    lot.reset("shirai")
    assert lot.apply_po(lot.read_po(FIXTURE))
    lot.form.update(doc_date="2026-10-29", pxk="0000002")
    lot.set_dates(["29.10"])
    lot.export("PKL")
    rec2 = lot.save()
    assert rec1["id"] != rec2["id"] and rec1["folder"] != rec2["folder"]
    assert rec1["folder"].endswith(os.path.join("2026_Thang_10", "2026-10-25")) and rec2["folder"].endswith(os.path.join("2026_Thang_10", "2026-10-29"))
    mine = [r for r in store.records if r["poNumber"] == "202699HT"]
    assert len(mine) == 2 and sorted(len(r["items"]) for r in mine) == [2, 2]  # lần khai sau không ghi đè lần trước


def test_saving_again_same_po_same_day_updates_instead_of_duplicating(store, lot):
    lot.form.update(doc_date="2026-10-25")
    first = lot.save()
    lot.form["pxk"] = "0000009"
    again = lot.save()
    assert again["id"] == first["id"] and len([r for r in store.records if r["poNumber"] == "202699HT"]) == 1


def test_reopened_record_updates_same_record_even_if_date_changed(store, lot):
    lot.form["doc_date"] = "2026-10-25"
    rec = lot.save()
    other = Lot(app, store)
    other.load_record(rec)
    other.form["doc_date"] = "2026-10-26"
    again = other.save()
    assert again["id"] == rec["id"] and len([r for r in store.records if r["poNumber"] == "202699HT"]) == 1


# ---------------------------------------------------------------- nạp dữ liệu học
def test_import_learned_adds_skips_existing_and_persists(store, data_dir):
    data = {"item_mem": {"Mặt hàng A": {"div": 50, "kg": 0.09, "hs": ""}, "Mặt hàng B": {"div": 10}}}
    assert store.import_learned(data) == {"them": 2, "ghi_de": 0, "bo_qua": 0, "khach": "", "mau": 0}
    store.item_mem["Mặt hàng A"]["div"] = 25  # người dùng tự sửa
    assert store.import_learned(data) == {"them": 0, "ghi_de": 0, "bo_qua": 2, "khach": "", "mau": 0}
    assert store.item_mem["Mặt hàng A"]["div"] == 25  # không bị ghi đè
    assert store.import_learned(data, overwrite=True)["ghi_de"] == 2
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    assert again.item_mem["Mặt hàng B"]["div"] == 10


def test_import_learned_rejects_wrong_files(store):
    with pytest.raises(ValueError, match="item_mem"):
        store.import_learned({"khac": 1})
    with pytest.raises(ValueError, match="không phải số"):
        store.import_learned({"item_mem": {"X": {"div": "abc"}}})


def test_import_learned_adds_customer_with_items(store, data_dir):
    cust = {"key": "kh_gia", "profile": {"docSet": "best", "name": "CÔNG TY GIẢ", "addr": "Địa chỉ giả", "label": "Giả"},
            "items": [{"name": "Ống giả 40 x 4 x 1000mm", "code": "VN9990001", "price": 1000, "kg": 0.5, "div": 20, "hs": "48229090"}]}
    res = store.import_learned({"khach_moi": cust})
    assert res["khach"] == "kh_gia" and "kh_gia" in app.PROFILES and app.is_best_docset(app.PROFILES["kh_gia"])
    assert store.items_for_customer("kh_gia")[0]["code"] == "VN9990001"
    assert store.import_learned({"khach_moi": dict(cust, profile={"name": "SỬA"})})["khach"] == ""  # có rồi: giữ nguyên
    assert app.PROFILES["kh_gia"]["name"] == "CÔNG TY GIẢ"
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    assert "kh_gia" in again.custom_profiles


def test_best_vat_and_pxk_follow_customer_sample(store):
    """Khách docSet 'best': mã chứng từ 'khách dd.mm PO', thông tin người mua chỉ ở dòng đầu, 'Ô tô tải: biển số'."""
    import openpyxl
    prof = {"docSet": "best", "name": "CÔNG TY GIẢ", "addr": "Địa chỉ giả", "mst": "0123456789", "buyerPerson": "Nguyễn Giả",
            "province": "Tỉnh Giả", "emails": "a@b.vn", "label": "Giả"}
    store.import_learned({"khach_moi": {"key": "bgia", "profile": prof, "items": []}})
    items = [{"po": "POGIA001", "ten_sp": f"Ống giả {i}", "qty": 10 * i, "price": 100, "amount": 1000 * i, "unit": "ống"} for i in (1, 2)]
    rec = {"customer": "bgia", "docDate": "2026-11-02", "items": items, "poNumber": "POGIA001", "xeNo": "99H-000.00", "driver": "Lái Giả", "poDates": {}}
    assert app.get_vat_and_pxk_ids(rec) == ("bgia 02.11 POGIA001", "bgia 02.11 POGIA001")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    v, p = app.build_vat_bkav_sheet(wb, rec), app.build_pxk_bkav_sheet(wb, rec)
    assert [v.cell(6, c).value for c in (14, 19, 31)] == ["Nguyễn Giả", "0123456789", "Tỉnh Giả"]
    assert v.cell(7, 14).value == "Nguyễn Giả" and v.cell(7, 19).value is None and v.cell(7, 13).value is None
    assert v.cell(6, 10).value is None
    assert p.cell(3, 21).value == "Ô tô tải: 99H-000.00" and p.cell(4, 21).value is None


def test_learned_customer_default_bundle_and_arizon_plx(store, tmp_path):
    """Khách đã học: mặc định Invoice + VAT + PXK; Arizon thêm Phụ lục X theo mẫu Arizon; khách cũ giữ nguyên."""
    import openpyxl
    store.import_learned({"khach_moi": {"key": "khgia", "profile": {"name": "CÔNG TY GIẢ", "addr": "Địa chỉ giả", "label": "Giả"}, "items": []}})
    store.import_learned({"khach_moi": {"key": "arz", "profile": {"name": "CÔNG TY TNHH CÔNG NGHỆ ARIZON (VIỆT NAM)", "addr": "Địa chỉ", "label": "Arizon", "unit": "chiếc"}, "items": []}})
    items = [{"po": "VN-3501-1", "ma_sp": "3609100570001", "ten_sp": "Ống giấy phi 76.2( 3inch) x 5 x 57 mm", "qty": 1000, "price": 2716, "amount": 2716000, "unit": "chiếc"},
             {"po": "VN-3501-1", "ma_sp": "3609100620001", "ten_sp": "Ống giấy phi 76.2( 3inch) x 5 x62 mm", "qty": 1050, "price": 2954, "amount": 3101700, "unit": "chiếc"}]
    base = {"docDate": "2026-10-16", "hdNo": "00004113", "pxkNo": "00000292", "items": items, "poNumber": "VN-3501-1", "poDates": {}}
    assert app.lot_bundle_modes(dict(base, customer="khgia")) == ["PKL", "VAT", "PXK"]
    assert app.lot_bundle_modes(dict(base, customer="arz")) == ["PKL", "VAT", "PXK", "PLX"]
    assert "DNTT" in app.lot_bundle_modes(dict(base, customer="kodi")) and "CHECK" in app.lot_bundle_modes(dict(base, customer="tesa"))  # khách cũ giữ nguyên
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = app.build_plx_sheet(wb, dict(base, customer="arz"))
    cells = {c.coordinate: c.value for row in ws.iter_rows() for c in row if c.value is not None}
    assert cells["A1"] == "PHỤ LỤC X" and cells["A8"] == "Hóa đơn giá trị gia tăng: 00004113 Ngày 16/10/2026"
    assert [cells[f"{c}11"] for c in "ABCD"] == [1, "3609100570001", "Ống giấy phi 76.2( 3inch) x 5 x 57 mm", 1000]
    assert cells["C6"] == "=SUM(D11:D12)" and cells["C7"] == 5817700 and cells["D6"] == "(Chiếc)"
    assert any("Bắc Ninh, ngày 16 tháng 10 năm 2026" == v for v in cells.values())

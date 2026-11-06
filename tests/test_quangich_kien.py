"""Quang Ích: tên hàng 'mã + tên' trên Hóa đơn VAT và PXK Bkav; số kiện luôn dùng ROUNDUP; cập nhật SL/kiện theo mã (Arizon, sheet CN). Dữ liệu giả."""

import json

import openpyxl
import pytest

import hongthien_desktop_app as app

QI = {"name": "CÔNG TY TNHH CÔNG NGHIỆP BAO BÌ QUANG ÍCH VIỆT NAM", "label": "Quang Ích", "mst": "0202266122", "addr": "Hải Phòng", "unit": "ống", "poInDocs": True, "linePo": True}
ITEMS = [{"name": "Ống giấy OPP TAPE đỏ, ngoài trắng,trong in 77x2.5x1265mm", "code": "2V01PRB000002", "unit": "ống", "price": 12800, "div": 0, "kg": 0.696}]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


def make_rec(store, key, items, **form):
    f = {"customer": key, "doc_date": "2026-11-06", "po": "20261030001", "pxk": "00000321", "hd": "00001"}
    f.update(form)
    return app.lot_build_record(store, f, items)


def test_quangich_vat_and_pxk_name_is_code_plus_name(store):
    store.save_learned_customer("quangich", dict(QI), [dict(x) for x in ITEMS])
    item = {"stt": 1, "po": "20261030001", "ma_sp": "2V01PRB000002", "ten_sp": ITEMS[0]["name"], "unit": "ống", "qty": 2500, "price": 12800, "amount": 32000000, "div": 0, "kg": 0.696, "kien": 0, "net": 1740, "gross": 1741}
    rec = make_rec(store, "quangich", [item])
    expected = "2V01PRB000002 " + ITEMS[0]["name"]
    for mode, col, row in (("PXK", "E", 3), ("VAT", "C", 6)):
        ws = openpyxl.load_workbook(app.lot_export(store, rec, mode)["path"]).active
        assert ws[f"{col}{row}"].value == expected, mode
    # khách khác không bị đổi
    store.save_learned_customer("khac", {"name": "CÔNG TY KHÁC", "label": "Khac", "mst": "0100000001", "addr": "BN", "unit": "ống"}, [dict(ITEMS[0])])
    ws = openpyxl.load_workbook(app.lot_export(store, make_rec(store, "khac", [item]), "PXK")["path"]).active
    assert ws["E3"].value == ITEMS[0]["name"]


def test_so_kien_is_roundup_formula_in_standard_invoice(store):
    store.save_learned_customer("kien1", {"name": "CÔNG TY KIEN", "label": "Kien", "mst": "0100000002", "addr": "BN", "unit": "chiếc"}, [{"name": "Ống A", "code": "A1", "price": 10, "div": 75, "kg": 0.5}])
    item = {"stt": 1, "po": "P", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 1000, "price": 10, "amount": 10000, "div": 75, "kg": 0.5, "kien": 14, "net": 500, "gross": 501}
    rec = make_rec(store, "kien1", [item])
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "PKL")["path"]).active
    kien = [c.value for row in ws.iter_rows(min_row=13, max_row=13) for c in row if isinstance(c.value, str) and "ROUNDUP" in c.value]
    assert kien == ["=ROUNDUP(E13/75,0)"]  # 1000/75 = 13,33 -> 14


def test_cap_nhat_kien_from_cn_sheet_updates_div_by_code(store):
    store.save_learned_customer("arz9", {"name": "CÔNG TY TNHH CÔNG NGHỆ ARIZON (VIỆT NAM)", "label": "Arizon", "mst": "0901155231", "addr": "Hưng Yên", "unit": "Chiếc"},
                                [{"name": "Ống giấy phi 76.2 x 5 x 62", "code": "3609100620001", "price": 2954, "div": 100, "kg": 0.1}, {"name": "Ống 153x5x100", "code": "3609301000001", "price": 1, "div": 0, "kg": 1}])
    data = {"version": "hongthien-hoc-v1", "cap_nhat_kien": {"khach": "Arizon", "so_ong_moi_kien": {"3609100620001": 196, "3609301000001": 36, "9999999999999": 5}}}
    res = store.import_learned(data)
    assert res["kien"] == 2 and res["kien_thieu"] == ["9999999999999"]
    divs = {it["code"]: it["div"] for it in store.custom_items["arz9"]}
    assert divs == {"3609100620001": 196, "3609301000001": 36} and store.get_item_norm("Ống giấy phi 76.2 x 5 x 62")["div"] == 196
    with pytest.raises(ValueError, match="chưa có khách"):
        store.import_learned({"cap_nhat_kien": {"khach": "Khong co", "so_ong_moi_kien": {"1": 2}}})

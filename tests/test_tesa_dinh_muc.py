"""Định mức Tesa theo bảng tổng hợp: 39753-91390-00 phải ra 0.876 kg/ống và 270 ống/kiện, kể cả trên máy đã lưu số cũ."""
import json

import hongthien_desktop_app as app
import tesa_names

PO = "tesa Purchase Order: 8600123456\n 1 39753-91390-00 Ống 2000 EA 29,998.00 1 EA 59,996,000.00\n@@HDR@@ 8600123456"


def _line(store):
    _po, ls = app.parse_tesa_po_text(PO, store.tesa_items, store)
    return ls[0]


def test_new_install_uses_summary_table(tmp_path):
    store = app.DedicatedDataStore(base_dir=str(tmp_path / "d"))
    ln = _line(store)
    assert (ln["kg"], ln["div"]) == (0.876, 270)
    assert ln["kien"] == app.math.ceil(ln["qty"] / 270) and ln["net"] == app.round_up(ln["qty"] * 0.876)


def test_old_catalog_on_disk_is_corrected_once_then_user_edit_wins(tmp_path):
    d = tmp_path / "d"
    store = app.DedicatedDataStore(base_dir=str(d))
    cat = json.loads((d / "master_catalog.json").read_text(encoding="utf-8"))
    name = tesa_names.TESA_NAMES["39753-91390-00"][1]
    for it in cat["tesa_items"]:
        if it.get("code") == "39753-91390-00":
            it["kg"], it["div"] = 0.858, 250
    cat["item_mem"][name] = {"div": 250, "kg": 0.858, "hs": "48229090"}
    cat.pop("tesa_dinh_muc_v", None)  # máy cài bản cũ: chưa áp bảng
    (d / "master_catalog.json").write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    store = app.DedicatedDataStore(base_dir=str(d))
    ln = _line(store)
    assert (ln["kg"], ln["div"]) == (0.876, 270)
    store.remember_item_norm(name, 300, 0.9, code="39753-91390-00")  # người dùng sửa tay sau đó: lần mở sau giữ số đã sửa
    store = app.DedicatedDataStore(base_dir=str(d))
    ln = _line(store)
    assert (ln["kg"], ln["div"]) == (0.9, 300)


def test_summary_table_codes_have_standard_names():
    assert set(tesa_names.TESA_DINH_MUC) <= set(tesa_names.TESA_NAMES) | {"39809-90000-00", "39811-90000-00", "39770-91750-00", "39780-91750-00", "39805-90000-00", "39805-91640-00"}

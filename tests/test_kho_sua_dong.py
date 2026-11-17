"""Sửa dòng hàng → kho dữ liệu (Data tổng) phải nhận số vừa sửa, kể cả khách Tesa và dòng mang tên HQ (mã nằm trong ngoặc, ô mã trống)."""
import json

import hongthien_desktop_app as app
import tesa_names

CODE = "39753-91390-00"
HQ, HD = tesa_names.TESA_NAMES[CODE]
OTHER = "Ống lõi giấy phi 33.2 x 2.65 x 19mm"  # mục ERP gắn nhầm mã 39753-91390-00: khác quy cách, không được đụng


def _seed_dt(store, items):
    path = store.dt_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "items": items}, f, ensure_ascii=False)
    store.dt_load()


def _stale_items():
    return [{"khach": "Tesa", "ten": HQ, "ma_hang": "", "ma_erp": "", "kg": 0.858, "kg_nguon": "invoice", "kien": 250, "kien_nguon": "invoice", "hs": "48229090"},
            {"khach": "Tesa", "ten": OTHER, "ma_hang": "", "ma_erp": "X1", "ma_kh": CODE, "kg": 0.005, "kg_nguon": "erp", "kien": 32000, "kien_nguon": "invoice", "hs": ""}]


def _dt(store, name):
    return next(x for x in store.data_tong if x["ten"] == name)


def test_edit_line_with_hq_name_and_blank_code_updates_kho(store):
    _seed_dt(store, _stale_items())
    vals = {"po": "8600229113", "ma_sp": "", "ten_sp": HQ, "unit": "cái", "qty": "1", "price": "0", "div": "270", "kg": "0.876"}
    app.lot_item_from_values(store, "tesa", vals)
    hq = _dt(store, HQ)
    assert (hq["kg"], hq["kien"], hq["kg_nguon"], hq["kien_nguon"]) == (0.876, 270, "tay", "tay")
    other = _dt(store, OTHER)
    assert (other["kg"], other["kien"]) == (0.005, 32000)  # khác quy cách: giữ nguyên
    it = next(x for x in store.tesa_items if x["code"] == CODE)  # mục danh mục Tesa của mã cũng nhận số vừa sửa
    assert (it["kg"], it["div"]) == (0.876, 270)
    # đọc lại từ đĩa (máy khác / lần mở sau) vẫn là số đã sửa
    again = app.DedicatedDataStore(base_dir=store.base_dir)
    assert (_dt(again, HQ)["kg"], _dt(again, HQ)["kien"]) == (0.876, 270)


def test_lookup_shows_edited_numbers_and_hides_duplicate_hq_row(store):
    _seed_dt(store, _stale_items())
    app.lot_item_from_values(store, "tesa", {"ma_sp": CODE, "ten_sp": HD, "unit": "ống", "qty": "100", "price": "29998", "div": "300", "kg": "0.9"})
    hits = app.lot_search_items(store, "tesa", CODE)
    rows = [(h["ten_sp"], float(h["div"]), float(h["kg"])) for h in hits]
    assert (HD, 300.0, 0.9) in rows
    assert not any(r[0] == HQ for r in rows)  # mục trùng mang tên HQ không còn hiện số cũ thành dòng riêng
    assert _dt(store, HQ)["kg"] == 0.9 and _dt(store, HQ)["kien"] == 300


def test_tesa_table_applied_to_kho_once_then_user_edit_wins(tmp_path):
    d = tmp_path / "d"
    store = app.DedicatedDataStore(base_dir=str(d))
    _seed_dt(store, _stale_items())
    cat = json.loads((d / "master_catalog.json").read_text(encoding="utf-8"))
    cat.pop("tesa_dinh_muc_dt_v", None)  # máy chưa áp bảng vào kho dữ liệu
    (d / "master_catalog.json").write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    store = app.DedicatedDataStore(base_dir=str(d))
    assert (_dt(store, HQ)["kg"], _dt(store, HQ)["kien"]) == (0.876, 270)
    assert (_dt(store, OTHER)["kg"], _dt(store, OTHER)["kien"]) == (0.005, 32000)
    store.dt_confirm_item("tesa", HQ, "", 0.88, 280)
    store = app.DedicatedDataStore(base_dir=str(d))
    assert (_dt(store, HQ)["kg"], _dt(store, HQ)["kien"]) == (0.88, 280)

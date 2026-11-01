import json
import os
import sqlite3

import hongthien_desktop_app as app


def test_fresh_store_creates_only_one_customs_folder_and_seed_data(store, data_dir):
    assert (data_dir / "HAI_QUAN").is_dir()
    for old in ("00_TEMPLATES_MAU_CHUNG_TU", "01_WORKING_LAM_CHUNG_TU", "02_ARCHIVE_SAU_PHAT_HANH"):
        assert not (data_dir / old).exists()  # chỉ cần một thư mục hải quan
    assert (data_dir / "master_catalog.json").is_file()
    assert (data_dir / "hongthien_records.json").is_file()
    assert (data_dir / "hongthien_haiquan.db").is_file()
    assert {r["customer"] for r in store.records} == {"shirai", "kodi", "tesa"}


def test_embedded_catalog_is_loaded(store):
    # Theo HUONG_DAN: 206 mã cân nặng, 1.833 mã ERP đầu TM
    assert len(store.weights_db) == 206
    assert len(store.erp_catalog) == 1833
    assert all(str(it.get("ma_sp", "")).startswith("TM") for it in store.erp_catalog)
    assert store.erp_map, "erp_map phải được dựng từ erp_catalog"


def test_seed_records_totals_are_consistent(seed):
    for rec in seed.values():
        items = rec["items"]
        assert rec["totalQty"] == sum(x["qty"] for x in items), rec["id"]
        assert rec["totalAmount"] == sum(x["amount"] for x in items), rec["id"]
        for it in items:
            assert abs(it["qty"] * it["price"] - it["amount"]) < 1, (rec["id"], it["stt"])


def test_records_roundtrip_json_and_sqlite(store, data_dir):
    rec = dict(store.records[0], id="HS-TEST-01", poNumber="PO-TEST")
    store.records.insert(0, rec)
    store.save_records()

    reloaded = app.DedicatedDataStore(base_dir=str(data_dir))
    assert reloaded.records[0]["id"] == "HS-TEST-01"

    with open(data_dir / "hongthien_records.json", encoding="utf-8") as f:
        assert len(json.load(f)) == len(store.records)

    conn = sqlite3.connect(data_dir / "hongthien_haiquan.db")
    rows = dict(conn.execute("SELECT ma_ho_so, so_po FROM ho_so_hai_quan").fetchall())
    conn.close()
    assert rows["HS-TEST-01"] == "PO-TEST"
    assert len(rows) == len(store.records)


def test_remember_item_norm_updates_catalog_and_persists(store, data_dir):
    name = store.kodi_items[1]["name"]
    store.remember_item_norm(name, div=10, kg=2.5, hs="48229090")
    assert store.get_item_norm(name) == {"div": 10, "kg": 2.5, "hs": "48229090"}
    assert store.kodi_items[1]["div"] == 10 and store.kodi_items[1]["kg"] == 2.5

    reloaded = app.DedicatedDataStore(base_dir=str(data_dir))
    assert reloaded.get_item_norm(name)["div"] == 10


def test_record_folder_is_customs_customer_month_day(store, seed, data_dir):
    rec = dict(seed["tesa"], docDate="2026-11-01", poNumber="PO-MOI-1", folder=None)
    assert store.get_record_folder_path(rec) == os.path.join(str(data_dir), "HAI_QUAN", "Tesa", "2026_Thang_11", "2026-11-01")


def test_old_style_records_use_old_folder_only_if_it_exists(store, seed, data_dir):
    rec = seed["kodi"]  # hồ sơ mẫu kiểu cũ, chưa có thư mục cũ trên máy
    assert store.get_record_folder_path(rec) == os.path.join(str(data_dir), "HAI_QUAN", "Kodi", "2026_Thang_10", "2026-10-28")
    legacy = store.legacy_folder_path(rec)
    os.makedirs(legacy)  # thư mục kiểu cũ có sẵn: vẫn tìm đúng chỗ cũ
    assert store.get_record_folder_path(rec) == legacy


def test_month_and_customer_folders_are_reused_not_duplicated(store, seed, data_dir):
    def make(day, po):
        rec = dict(seed["kodi"], docDate=day, poNumber=po, folder=None)
        os.makedirs(store.get_record_folder_path(rec), exist_ok=True)
        rec["folder"] = os.path.relpath(store.get_record_folder_path(rec), store.base_dir)
        store.records.append(rec)
    make("2026-11-01", "A")
    make("2026-11-05", "B")
    make("2026-12-02", "C")
    kodi = data_dir / "HAI_QUAN" / "Kodi"
    assert sorted(p.name for p in kodi.iterdir()) == ["2026_Thang_11", "2026_Thang_12"]  # tháng 11 chỉ có một thư mục
    assert sorted(p.name for p in (kodi / "2026_Thang_11").iterdir()) == ["2026-11-01", "2026-11-05"]


def test_same_customer_same_day_different_po_gets_separate_folder(store, seed):
    first = dict(seed["tesa"], docDate="2026-11-03", poNumber="PO-1", folder=None)
    first["folder"] = store.new_record_folder(first)
    store.records.append(first)
    second = dict(seed["tesa"], docDate="2026-11-03", poNumber="PO-2", folder=None)
    assert store.get_record_folder_path(second).endswith(os.path.join("2026_Thang_11", "2026-11-03_2"))
    assert store.get_record_folder_path(first).endswith(os.path.join("2026_Thang_11", "2026-11-03"))
    # cùng khách + cùng PO thì mở lại đúng thư mục cũ
    again = dict(first, folder=None)
    assert store.get_record_folder_path(again) == store.get_record_folder_path(first)


def test_saved_record_keeps_folder_after_customer_label_renamed(store, seed):
    rec = app.lot_build_record(store, {"customer": "tesa", "po": "PO-DOI-TEN", "doc_date": "2026-11-04"}, seed["tesa"]["items"])
    app.lot_save_new(store, rec, {})
    saved_folder = store.get_record_folder_path(rec)
    assert os.path.join("HAI_QUAN", "Tesa") in saved_folder
    store.update_customer("tesa", {"label": "Tesa Moi"})
    again = app.lot_build_record(store, {"customer": "tesa", "po": "PO-DOI-TEN", "doc_date": "2026-11-04"}, seed["tesa"]["items"])
    assert store.get_record_folder_path(again) == saved_folder  # không bị chuyển sang thư mục tên mới


def test_customer_folder_name_is_safe_for_windows(store, seed):
    store.update_customer("tesa", {"label": 'Tê*sa: "A/B"'})
    rec = dict(seed["tesa"], docDate="2026-11-01", poNumber="PO-AN-TOAN", folder=None)
    name = store.get_record_folder_path(rec).split(os.sep)
    assert not any(ch in "".join(name[-4:-3]) for ch in '*:"/\\?<>|')


def test_change_base_dir_moves_store_and_writes_config(store, tmp_path):
    new_dir = tmp_path / "LAN_Z"
    store.change_base_dir(str(new_dir))
    assert store.base_dir == str(new_dir)
    assert (new_dir / "HAI_QUAN").is_dir()
    with open(store.config_file, encoding="utf-8") as f:
        assert json.load(f)["data_dir"] == str(new_dir)


def test_corrupt_records_file_falls_back_to_seed(data_dir, store):
    (data_dir / "hongthien_records.json").write_text("{not json", encoding="utf-8")
    reloaded = app.DedicatedDataStore(base_dir=str(data_dir))
    assert len(reloaded.records) == 3

import json
import os
import sqlite3

import hongthien_desktop_app as app


def test_fresh_store_creates_folder_tree_and_seed_data(store, data_dir):
    for sub in ("00_TEMPLATES_MAU_CHUNG_TU", "01_WORKING_LAM_CHUNG_TU", "02_ARCHIVE_SAU_PHAT_HANH"):
        assert (data_dir / sub).is_dir()
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


def test_record_folder_paths(store, seed, data_dir):
    working = store.get_record_folder_path(seed["shirai"])
    assert working == os.path.join(str(data_dir), "01_WORKING_LAM_CHUNG_TU", "Nam_2026", "Thang_10", "SHIRAI_PO-202637HT_20261030")

    archive = store.get_record_folder_path(seed["kodi"])
    assert archive == os.path.join(
        str(data_dir), "02_ARCHIVE_SAU_PHAT_HANH", "Nam_2026", "KhachHang_KODI", "Thang_10",
        "20261028_KODI_PO-03102026-01KDHT_PXK-00000303_HD-0000398_TK-306889012340",
    )


def test_change_base_dir_moves_store_and_writes_config(store, tmp_path):
    new_dir = tmp_path / "LAN_Z"
    store.change_base_dir(str(new_dir))
    assert store.base_dir == str(new_dir)
    assert (new_dir / "02_ARCHIVE_SAU_PHAT_HANH").is_dir()
    with open(store.config_file, encoding="utf-8") as f:
        assert json.load(f)["data_dir"] == str(new_dir)


def test_corrupt_records_file_falls_back_to_seed(data_dir, store):
    (data_dir / "hongthien_records.json").write_text("{not json", encoding="utf-8")
    reloaded = app.DedicatedDataStore(base_dir=str(data_dir))
    assert len(reloaded.records) == 3

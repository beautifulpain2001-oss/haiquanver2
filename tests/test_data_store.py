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
    rec = dict(seed["tesa"], id="HS-MOI", docDate="2026-11-01", poNumber="PO-MOI-1", folder=None)
    assert store.get_record_folder_path(rec) == os.path.join(str(data_dir), "HAI_QUAN", "Tesa", "2026_Thang_11", "2026-11-01_00000287")  # <ngày>_<số PXK>


def test_old_style_records_use_old_folder_only_if_it_exists(store, seed, data_dir):
    rec = seed["kodi"]  # hồ sơ mẫu kiểu cũ, chưa có thư mục cũ trên máy
    assert store.get_record_folder_path(rec) == os.path.join(str(data_dir), "HAI_QUAN", "Kodi", "2026_Thang_10", "2026-10-28_00000303")
    legacy = store.legacy_folder_path(rec)
    os.makedirs(legacy)  # thư mục kiểu cũ có sẵn: vẫn tìm đúng chỗ cũ
    assert store.get_record_folder_path(rec) == legacy


def test_month_and_customer_folders_are_reused_not_duplicated(store, seed, data_dir):
    def make(day, po):
        rec = dict(seed["kodi"], id=f"HS-{po}", docDate=day, poNumber=po, folder=None)
        os.makedirs(store.get_record_folder_path(rec), exist_ok=True)
        rec["folder"] = os.path.relpath(store.get_record_folder_path(rec), store.base_dir)
        store.records.append(rec)
    make("2026-11-01", "A")
    make("2026-11-05", "B")
    make("2026-12-02", "C")
    kodi = data_dir / "HAI_QUAN" / "Kodi"
    assert sorted(p.name for p in kodi.iterdir()) == ["2026_Thang_11", "2026_Thang_12"]  # tháng 11 chỉ có một thư mục
    assert sorted(p.name for p in (kodi / "2026_Thang_11").iterdir()) == ["2026-11-01_00000303", "2026-11-05_00000303"]


def test_same_customer_same_day_different_pxk_gets_separate_folder(store, seed):
    first = dict(seed["tesa"], id="HS-T-1", docDate="2026-11-03", poNumber="PO-1", pxkNo="00000287", folder=None)
    first["folder"] = store.new_record_folder(first)
    store.records.append(first)
    second = dict(seed["tesa"], id="HS-T-2", docDate="2026-11-03", poNumber="PO-2", pxkNo="00000288", folder=None)
    assert store.get_record_folder_path(second).endswith(os.path.join("2026_Thang_11", "2026-11-03_00000288"))
    assert store.get_record_folder_path(first).endswith(os.path.join("2026_Thang_11", "2026-11-03_00000287"))
    # cùng ngày + cùng số PXK thì lưu chung một thư mục (không tách _2); chưa có số PXK thì chỉ ngày
    same = dict(second, id="HS-T-3", pxkNo="00000287")
    assert store.get_record_folder_path(same).endswith(os.path.join("2026_Thang_11", "2026-11-03_00000287"))
    assert store.get_record_folder_path(dict(second, id="HS-T-4", pxkNo="")).endswith(os.path.join("2026_Thang_11", "2026-11-03"))
    # cùng khách + cùng PO thì mở lại đúng thư mục cũ
    again = dict(first, folder=None)
    assert store.get_record_folder_path(again) == store.get_record_folder_path(first)


def test_same_day_same_po_but_other_pxk_is_a_new_record_and_folder(store, seed):
    """Bộ 330 cùng ngày, cùng PO với bộ 327: là hồ sơ và thư mục mới, không dùng chung thư mục 327."""
    a = dict(seed["tesa"], id="HS-A", docDate="2026-11-09", poNumber="PO-1", pxkNo="00000327", folder=None)
    a["folder"] = store.new_record_folder(a)
    store.records.append(a)
    b = dict(a, id=None, pxkNo="00000330", folder=None)
    assert store.find_record(b) == -1
    assert store.get_record_folder_path(b).endswith(os.path.join("2026_Thang_11", "2026-11-09_00000330"))
    c = dict(a, id=None, folder=None)  # cùng PXK 327: đúng hồ sơ cũ, đúng thư mục cũ
    assert store.find_record(c) == len(store.records) - 1 and store.get_record_folder_path(c) == store.get_record_folder_path(a)

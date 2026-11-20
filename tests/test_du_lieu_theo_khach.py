"""Mỗi khách một file dữ liệu (HAI_QUAN/<Khách>/DU_LIEU_<MÃ>.json) + phần dùng chung trong HAI_QUAN/_HE_THONG:
chuyển từ 3 file chung cũ có xem trước, sao lưu, hoàn tác; nhiều máy lưu không đè nhau; ghi đúng file của khách."""
import json
import os

import hongthien_desktop_app as app


def make_store(data_dir, tmp_path, name):
    s = app.DedicatedDataStore(base_dir=str(data_dir))
    s.config_file = str(tmp_path / f"config_{name}.json")
    return s


def add_dt(store):
    store.data_tong += [
        {"khach": "ARIZON", "ten": "Ống giấy phi 76.2 x 5 x 85", "ma_hang": "FG10496-004-00000", "kg": 0.091, "ts": "1"},
        {"khach": "Arizon", "ten": "ống 76x5x85, T.nâu", "ma_hang": "FG10496-004-00000", "kg": 0.089, "ts": "1"},
        {"khach": "CÔNG TY TNHH FUJIDAN VIỆT NAM", "ten": "Lõi A", "kg": 0.1, "ts": "1"},
        {"khach": "Fujidan", "ten": "Lõi B", "kg": 0.2, "ts": "1"},
        {"khach": "Tesa", "ten": "Ống tesa 1", "ma_hang": "39753-91390-00", "kg": 0.876, "ts": "1"},
    ]
    store.dt_save()


def test_ten_khach_chuan_gom_cac_cach_ghi():
    assert app.ten_khach_chuan("CÔNG TY TNHH FUJIDAN VIỆT NAM") == app.ten_khach_chuan("Fujidan") == "fujidan"
    assert app.ten_khach_chuan("ARIZON") == app.ten_khach_chuan("Arizon")
    assert app.ten_khach_chuan("Bao bì Đông Đô") == app.ten_khach_chuan("CÔNG TY CỔ PHẦN BAO BÌ ĐÔNG ĐÔ")


def test_preview_does_not_write_and_lists_problems(store):
    add_dt(store)
    store.records.insert(0, {"id": "HS-1-ABLE", "customer": "kodi", "docDate": "2026-11-11", "pxkNo": "00000334", "updatedAt": "1"})
    store.records.insert(0, {"id": "HS-1-TESA", "customer": "tesa", "docDate": "2026-11-11", "pxkNo": "00000334", "updatedAt": "1"})
    before = sorted(os.listdir(store.customs_root()))
    pv = store.chuyen_doi_xem_truoc()
    assert sorted(os.listdir(store.customs_root())) == before and not store.theo_khach()
    keys = {r["khach"] for r in pv["files"]}
    assert {"", "kodi", "tesa", "shirai", "fujidan"} <= keys
    fuji = next(r for r in pv["files"] if r["khach"] == "fujidan")
    assert fuji["data_tong"] == 2 and len(fuji["ten_goi"]) == 2  # hai cách ghi tên gộp về một khách
    assert any(x["pxk"] == "00000334" for x in pv["pxk_trung"])
    assert any(x["ma"] == "FG10496-004-00000" for x in pv["kg_lech"])  # chỉ báo, không tự sửa


def test_migrate_then_reload_same_data_and_old_files_kept(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    add_dt(a)
    n_rec, n_dt = len(a.records), len(a.data_tong)
    kodi_items = [dict(x) for x in a.kodi_items]
    res = a.chuyen_doi_thuc_hien()
    assert a.theo_khach() and res["ho_so"] == n_rec and res["data_tong"] == n_dt
    root = a.customs_root()
    assert os.path.isfile(os.path.join(root, "_HE_THONG", "he_thong.json"))
    assert os.path.isfile(a._khach_path("kodi")) and os.path.basename(a._khach_path("kodi")) == "DU_LIEU_KODI.json"
    assert os.path.isfile(os.path.join(res["sao_luu"], "master_catalog.json"))  # bản sao lưu nguyên vẹn
    assert os.path.isfile(os.path.splitext(a.catalog_file)[0] + ".DA_CHUYEN.json") and not os.path.exists(a.catalog_file)  # đổi tên, không xóa
    b = make_store(data_dir, tmp_path, "b")  # máy khác mở: đọc từ file khách
    assert b.theo_khach() and len(b.records) == n_rec and len(b.data_tong) == n_dt
    assert b.kodi_items == kodi_items
    assert {r["id"] for r in b.records} == {r["id"] for r in a.records}
    data = json.load(open(a._khach_path("kodi"), encoding="utf-8"))
    assert data["loai"] == "DU_LIEU_KHACH" and all("items" not in e for e in data["ho_so"])  # chi tiết hồ sơ nằm ở thẻ lô
    # thư mục khách chỉ có file dữ liệu không bị coi là thư mục tờ khai
    assert all(not o["path"].endswith(os.sep + "Fujidan") for o in b.declaration_folders())


def test_saving_one_customer_only_writes_that_customer_file(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    add_dt(a)
    a.chuyen_doi_thuc_hien()
    tesa, kodi = a._khach_path("tesa"), a._khach_path("kodi")
    t0, k0 = os.stat(tesa).st_mtime_ns, os.stat(kodi).st_mtime_ns
    os.utime(tesa, ns=(t0 - 10**9, t0 - 10**9))
    a._sigs[tesa] = a._sig(tesa)
    a.kodi_items.append({"name": "Mã mới", "code": "K-NEW", "div": 10, "kg": 1})
    a.save_catalog()
    assert os.stat(kodi).st_mtime_ns != k0
    assert os.stat(tesa).st_mtime_ns == t0 - 10**9  # file khách khác không bị ghi
    assert any(x.get("code") == "K-NEW" for x in make_store(data_dir, tmp_path, "c").kodi_items)


def test_two_machines_same_customer_different_records_both_kept(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.chuyen_doi_thuc_hien()
    b = make_store(data_dir, tmp_path, "b")
    a.records.insert(0, {"id": "A1", "customer": "kodi", "poNumber": "PO-A", "docDate": "2026-11-02", "items": [], "files": {}, "updatedAt": "2026-11-02 10:00"})
    a.save_records()
    b.records.insert(0, {"id": "B1", "customer": "kodi", "poNumber": "PO-B", "docDate": "2026-11-03", "items": [], "files": {}, "updatedAt": "2026-11-03 10:00"})
    b.save_records()  # B chưa đọc lại A1 mà đã lưu: gộp, không đè
    fresh = make_store(data_dir, tmp_path, "c")
    assert {"A1", "B1"} <= {r["id"] for r in fresh.records}


def test_new_customer_file_from_other_machine_is_seen(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.chuyen_doi_thuc_hien()
    b = make_store(data_dir, tmp_path, "b")
    a.data_tong.append({"khach": "Minh Anh", "ten": "Ống X", "kg": 0.5, "ts": "2"})
    a.dt_save()
    assert os.path.isfile(a._khach_path("minh_anh"))
    assert b.changed_on_disk() and b.sync()
    assert any(r.get("ten") == "Ống X" for r in b.data_tong)


def test_undo_restores_old_files(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    add_dt(a)
    n_dt = len(a.data_tong)
    a.chuyen_doi_thuc_hien()
    a.chuyen_doi_hoan_tac()
    assert not a.theo_khach() and os.path.isfile(a.catalog_file) and os.path.isfile(a.dt_path())
    assert len(make_store(data_dir, tmp_path, "b").data_tong) == n_dt


def test_conflict_copy_of_customer_file_is_merged(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.chuyen_doi_thuc_hien()
    path = a._khach_path("kodi")
    data = json.load(open(path, encoding="utf-8"))
    data["danh_muc"]["kodi_items"].append({"name": "Từ máy KETOANBH", "code": "K-CONF", "div": 1, "kg": 1})
    json.dump(data, open(path[:-5] + "-KETOANBH.json", "w", encoding="utf-8"), ensure_ascii=False)
    a.sync()
    assert any(x.get("code") == "K-CONF" for x in a.kodi_items)
    assert not os.path.exists(path[:-5] + "-KETOANBH.json")
    assert os.listdir(os.path.join(a.backup_root(), "xung_dot"))


def migrated_with_dt(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    add_dt(a)
    a.data_tong += [{"khach": "FUJIDAN", "ten": "Lõi A", "kg": 0.15, "kg_nguon": "tay", "ts": "2"},  # trùng tên hàng với dòng Fujidan cũ
                    {"khach": "Fujidan", "ten": "Lõi A", "kien": 50, "ts": "0"}]
    a.dt_save()
    a.chuyen_doi_thuc_hien()
    return a


def test_sap_xep_preview_then_apply_unifies_names_and_drops_duplicate_rows(data_dir, tmp_path):
    a = migrated_with_dt(data_dir, tmp_path)
    pv = a.sap_xep_xem_truoc()
    assert pv["dong_trung"] == 2 and pv["doi_ten"] >= 2 and "fujidan" in pv["ten_goi"]
    assert any(x["ma"] == "FG10496-004-00000" for x in pv["kg_lech"])  # chỉ báo
    n = len(a.data_tong)
    st = a.sap_xep_thuc_hien()
    assert st["dong_trung"] == 2 and len(a.data_tong) == n - 2
    fuji = [r for r in a.data_tong if a.dt_khach_key(r) == "fujidan"]
    assert len({r["khach"] for r in fuji}) == 1  # một tên khách
    loi_a = next(r for r in fuji if r["ten"] == "Lõi A")
    assert loi_a["kg"] == 0.15 and loi_a["kien"] == 50  # giữ dòng sửa tay, ô trống lấy từ dòng bỏ
    assert {x["ma"] for x in a.sap_xep_xem_truoc()["kg_lech"]} >= {"FG10496-004-00000"}  # cùng mã khác kg: không tự chọn
    b = make_store(data_dir, tmp_path, "b")
    assert len(b.data_tong) == n - 2


def test_sap_xep_merges_old_files_written_by_old_app_and_misplaced_customer_file(data_dir, tmp_path):
    a = migrated_with_dt(data_dir, tmp_path)
    # bản phần mềm cũ ở máy khác ghi lại master_catalog.json với một mã mới
    json.dump({"kodi_items": a.kodi_items + [{"name": "Từ bản cũ", "code": "OLD-1", "div": 1, "kg": 1}]},
              open(a.catalog_file, "w", encoding="utf-8"), ensure_ascii=False)
    # file khách Tesa bị kéo nhầm sang thư mục khác
    old = a._khach_path("tesa")
    wrong = os.path.join(a.customs_root(), "Nham", os.path.basename(old))
    os.makedirs(os.path.dirname(wrong))
    os.replace(old, wrong)
    a._sigs = {}
    a.load_all()
    pv = a.sap_xep_xem_truoc()
    assert pv["file_cu"] and pv["sai_cho"]
    a.sap_xep_thuc_hien()
    assert any(x.get("code") == "OLD-1" for x in a.kodi_items)
    assert not os.path.exists(a.catalog_file) and os.path.isfile(old) and not os.path.exists(wrong)
    assert any(x.get("code") == "OLD-1" for x in make_store(data_dir, tmp_path, "c").kodi_items)


def test_sap_xep_undo_restores_everything(data_dir, tmp_path):
    a = migrated_with_dt(data_dir, tmp_path)
    n = len(a.data_tong)
    a.sap_xep_thuc_hien()
    assert len(a.data_tong) == n - 2
    a.sap_xep_hoan_tac()
    assert len(a.data_tong) == n and len(make_store(data_dir, tmp_path, "d").data_tong) == n


def test_sap_xep_needs_migration_first(store):
    import pytest
    with pytest.raises(ValueError, match="chưa chuyển"):
        store.sap_xep_xem_truoc()

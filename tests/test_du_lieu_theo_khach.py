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
    assert {"", "kodi", "tesa", "shirai"} <= keys
    assert "fujidan" not in keys and "arizon" not in keys  # khách chưa có trong app: không có file riêng
    fuji = pv["chua_co"]["fujidan"]
    assert fuji["dong"] == 2 and len(fuji["ten"]) == 2  # liệt kê để người dùng chọn thêm vào app
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
    # khách chưa có trong app: không tạo thư mục, dòng Kg & kiện nằm ở phần dùng chung
    made = set(os.listdir(root))
    assert not any("fujidan" in d.lower() or "arizon" in d.lower() for d in made)
    ht = json.load(open(os.path.join(root, "_HE_THONG", "he_thong.json"), encoding="utf-8"))
    assert sum(1 for r in ht["data_tong"] if "ujidan" in r["khach"].lower()) == 2


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
    a.save_learned_customer("minhanh", {"name": "CÔNG TY MINH ANH", "label": "Minh Anh", "mst": "0100000001", "addr": "HN", "unit": "chiếc"},
                            [{"name": "Ống X", "code": "MA-1", "price": 1, "div": 10, "kg": 0.5}])
    assert os.path.isfile(a._khach_path("minhanh")) and os.path.basename(os.path.dirname(a._khach_path("minhanh"))) == "Minh Anh"
    assert b.changed_on_disk() and b.sync()
    assert any(x.get("code") == "MA-1" for x in b.custom_items.get("minhanh", []))


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
    a.data_tong += [{"khach": "TESA", "ten": "Ống tesa 1", "kg": 0.9, "kg_nguon": "tay", "ts": "2"},  # trùng tên hàng với dòng Tesa cũ
                    {"khach": "tesa", "ten": "Ống tesa 1", "kien": 50, "ts": "0"},
                    {"khach": "FUJIDAN", "ten": "Lõi A", "kg": 0.15, "ts": "2"}]  # khách chưa có trong app: không đụng
    a.dt_save()
    a.chuyen_doi_thuc_hien()
    return a


def test_sap_xep_preview_then_apply_unifies_names_and_drops_duplicate_rows(data_dir, tmp_path):
    a = migrated_with_dt(data_dir, tmp_path)
    pv = a.sap_xep_xem_truoc()
    assert pv["dong_trung"] == 2 and pv["doi_ten"] >= 2 and "tesa" in pv["ten_goi"] and "fujidan" not in pv["ten_goi"]
    assert "fujidan" in pv["chua_co"]  # liệt kê, không sắp xếp
    assert any(x["ma"] == "FG10496-004-00000" for x in pv["kg_lech"])  # chỉ báo
    n = len(a.data_tong)
    st = a.sap_xep_thuc_hien()
    assert st["dong_trung"] == 2 and len(a.data_tong) == n - 2
    tesa = [r for r in a.data_tong if a.dt_khach_key(r) == "tesa"]
    assert len({r["khach"] for r in tesa}) == 1  # một tên khách
    ong = next(r for r in tesa if r["ten"] == "Ống tesa 1")
    assert ong["kg"] == 0.9 and ong["kien"] == 50  # giữ dòng sửa tay, ô trống lấy từ dòng bỏ
    fuji = [r for r in a.data_tong if a.dt_khach_key(r) == "fujidan"]
    assert len(fuji) == 3 and len({r["khach"] for r in fuji}) == 3  # khách chưa có trong app: để nguyên
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


def test_sap_xep_moves_files_of_customers_not_in_app_back_to_shared_data(data_dir, tmp_path):
    """Bản trước lỡ tạo DU_LIEU_<tên>.json (và thư mục) cho tên khách chỉ có trong dữ liệu: Sắp xếp cất file đó, dữ liệu về
    phần dùng chung, thư mục chỉ còn trống thì bỏ; thư mục khách có file khác của người dùng giữ nguyên."""
    a = migrated_with_dt(data_dir, tmp_path)
    root = a.customs_root()
    ht = os.path.join(root, "_HE_THONG", "he_thong.json")
    data = json.load(open(ht, encoding="utf-8"))
    fuji_rows = [r for r in data["data_tong"] if "ujidan" in r["khach"].lower()]
    data["data_tong"] = [r for r in data["data_tong"] if r not in fuji_rows]
    json.dump(data, open(ht, "w", encoding="utf-8"), ensure_ascii=False)
    os.makedirs(os.path.join(root, "Fujidan"))
    json.dump({"loai": "DU_LIEU_KHACH", "khach": "fujidan", "data_tong": fuji_rows}, open(os.path.join(root, "Fujidan", "DU_LIEU_FUJIDAN.json"), "w", encoding="utf-8"))
    os.makedirs(os.path.join(root, "CN Mr.Tuan", "2026_Thang_11"))  # thư mục khách của người dùng, có hồ sơ
    json.dump({"loai": "DU_LIEU_KHACH", "khach": "cn_mr_tuan", "data_tong": [{"khach": "CN Mr.Tuan", "ten": "Ống T", "kg": 1, "ts": "1"}]},
              open(os.path.join(root, "CN Mr.Tuan", "DU_LIEU_CN_MR_TUAN.json"), "w", encoding="utf-8"))
    b = make_store(data_dir, tmp_path, "b")
    n = len(b.data_tong)
    assert sum(1 for r in b.data_tong if "ujidan" in r["khach"].lower()) == 3  # bản cũ vẫn đọc được
    pv = b.sap_xep_xem_truoc()
    assert len(pv["file_la"]) == 2 and pv["thu_muc_trong"] == ["Fujidan"]
    st = b.sap_xep_thuc_hien()
    assert st["file_la"] == 2 and st["thu_muc_xoa"] == 1
    assert not os.path.exists(os.path.join(root, "Fujidan"))
    assert os.path.isdir(os.path.join(root, "CN Mr.Tuan", "2026_Thang_11")) and not os.path.exists(os.path.join(root, "CN Mr.Tuan", "DU_LIEU_CN_MR_TUAN.json"))
    c = make_store(data_dir, tmp_path, "c")
    assert len(c.data_tong) == n - st["dong_trung"]  # không mất dòng nào (ngoài các dòng Tesa trùng đã gộp)
    assert sum(1 for r in json.load(open(ht, encoding="utf-8"))["data_tong"] if "ujidan" in r["khach"].lower()) == 3
    c.sap_xep_hoan_tac()
    assert os.path.isfile(os.path.join(root, "Fujidan", "DU_LIEU_FUJIDAN.json"))
    assert len(make_store(data_dir, tmp_path, "d").data_tong) == n


def test_choosing_customs_folder_itself_still_finds_customers_in_parent(tmp_path):
    """Chọn thư mục HAI_QUAN làm thư mục chung trong khi master_catalog.json nằm ở thư mục cha: vẫn thấy khách đã thêm."""
    shared = tmp_path / "chung"
    a = make_store(shared, tmp_path, "a")
    a.save_learned_customer("minhanh", {"name": "CÔNG TY MINH ANH", "label": "Minh Anh"}, [{"name": "Ống A", "code": "A1"}])
    assert (shared / "master_catalog.json").is_file()
    b = make_store(shared / "HAI_QUAN", tmp_path, "b")
    assert "minhanh" in b.custom_profiles and os.path.normcase(b.base_dir) == os.path.normcase(str(shared))
    a.chuyen_doi_thuc_hien()  # đã chuyển sang mỗi khách một file: chọn HAI_QUAN vẫn đọc đúng
    c = make_store(shared / "HAI_QUAN", tmp_path, "c")
    assert c.theo_khach() and "minhanh" in c.custom_profiles
    # HAI_QUAN tự có danh mục khách riêng thì giữ nguyên
    own = tmp_path / "rieng" / "HAI_QUAN"
    d = make_store(own, tmp_path, "d")
    assert os.path.normcase(d.base_dir) == os.path.normcase(str(own))


def test_orphan_customer_files_without_he_thong_are_read_not_lost(data_dir, tmp_path):
    """Chuyển dở dang / đã hoàn tác mà file khách còn lại (không có he_thong.json): khách vẫn hiện, không ghi/xóa gì."""
    a = make_store(data_dir, tmp_path, "a")
    a.save_learned_customer("minhanh", {"name": "CÔNG TY MINH ANH", "label": "Minh Anh"}, [{"name": "Ống A", "code": "A1"}])
    a.data_tong += [{"khach": "Minh Anh", "ten": "Ống A", "ma_hang": "A1", "kg": 0.5, "ts": "1"}]
    a.dt_save()
    a.records.insert(0, {"id": "HS-ORPHAN-1", "customer": "minhanh", "docDate": "2026-11-10", "pxkNo": "00000777", "updatedAt": "5"})
    a.save_records()
    a.chuyen_doi_thuc_hien()
    ht = a.he_thong_path()
    os.remove(ht)  # mô phỏng: he_thong.json biến mất (hoàn tác / đồng bộ lỗi)
    # file cũ trong thư mục chung chỉ có Shirai/Tesa/Kodi
    for n in ("master_catalog", "hongthien_records"):
        old = os.path.join(str(data_dir), n + ".DA_CHUYEN.json")
        if os.path.isfile(old):
            os.remove(old)
    du = a._khach_path("minhanh")
    before = open(du, "rb").read()
    b = make_store(data_dir, tmp_path, "b")
    assert not b.theo_khach() and b.orphan_files >= 1
    assert "minhanh" in b.custom_profiles and "minhanh" in app.PROFILES
    assert any(r["id"] == "HS-ORPHAN-1" for r in b.records)
    assert any(r.get("ma_hang") == "A1" for r in b.data_tong) and sum(1 for r in b.data_tong if r.get("ma_hang") == "A1") == 1
    assert open(du, "rb").read() == before  # chỉ đọc, file khách nguyên vẹn
    res = b.chuyen_doi_thuc_hien()  # bấm chuyển để hoàn tất: file khách có sẵn được sao lưu trước
    assert b.theo_khach() and os.path.isfile(os.path.join(res["sao_luu"], "file_khach_co_san", os.path.basename(du)))
    c = make_store(data_dir, tmp_path, "c")
    assert "minhanh" in c.custom_profiles and any(r["id"] == "HS-ORPHAN-1" for r in c.records)


def test_customs_folder_with_own_records_is_not_redirected_to_parent(tmp_path):
    shared = tmp_path / "chung"
    a = make_store(shared, tmp_path, "a")
    a.save_records()
    own = shared / "HAI_QUAN"
    (own).mkdir(exist_ok=True)
    (own / "hongthien_records.json").write_text("[]", encoding="utf-8")
    b = make_store(own, tmp_path, "b")
    assert os.path.normcase(b.base_dir) == os.path.normcase(str(own))


def test_reorganize_never_moves_customer_data_files(data_dir, tmp_path):
    """'Sắp xếp lại thư mục' (theo ngày) không được đưa DU_LIEU_<MÃ>.json vào thư mục ngày lô."""
    a = make_store(data_dir, tmp_path, "a")
    a.save_learned_customer("minhanh", {"name": "CÔNG TY MINH ANH", "label": "Minh Anh"}, [{"name": "Ống A", "code": "A1"}])
    a.chuyen_doi_thuc_hien()
    cdir = os.path.dirname(a._khach_path("minhanh"))
    os.makedirs(os.path.join(cdir, "2026_Thang_11", "2026-11-10"))  # đã có thư mục lô: trước đây file lẻ bị gom vào ngày
    plan = a.plan_reorganize()
    assert not any(os.path.basename(it["src"]).startswith("DU_LIEU_") for it in plan)

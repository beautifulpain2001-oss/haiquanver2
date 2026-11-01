"""Nhiều máy dùng chung một thư mục dữ liệu (không máy chủ): đọc thấy nhau, lưu không đè nhau."""
import hongthien_desktop_app as app


def make_store(data_dir, tmp_path, name):
    s = app.DedicatedDataStore(base_dir=str(data_dir))
    s.config_file = str(tmp_path / f"config_{name}.json")
    return s


def rec(rid, po, day="2026-11-02"):
    return {"id": rid, "customer": "kodi", "poNumber": po, "docDate": day, "items": [], "files": {}, "updatedAt": "2026-11-02 10:00"}


def test_two_machines_see_and_keep_each_others_records(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    b = make_store(data_dir, tmp_path, "b")
    a.records.insert(0, rec("A1", "PO-A"))
    a.save_records()
    assert b.changed_on_disk() and b.sync()  # máy B thấy hồ sơ vừa lưu ở máy A
    assert any(r["id"] == "A1" for r in b.records)
    b.records.insert(0, rec("B1", "PO-B"))
    b.save_records()
    a.records.insert(0, rec("A2", "PO-A2"))  # máy A chưa đọc lại hồ sơ B1 mà đã lưu tiếp
    a.save_records()
    fresh = make_store(data_dir, tmp_path, "c")
    assert {"A1", "B1", "A2"} <= {r["id"] for r in fresh.records}  # không ai đè mất của ai


def test_delete_on_one_machine_is_not_undone_by_save(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.records.insert(0, rec("X1", "PO-X"))
    a.save_records()
    a.records = [r for r in a.records if r["id"] != "X1"]
    a.save_records()
    assert "X1" not in {r["id"] for r in make_store(data_dir, tmp_path, "b").records}


def test_catalog_changes_from_two_machines_are_merged(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    b = make_store(data_dir, tmp_path, "b")
    a.item_mem["Hàng A"] = {"div": 10, "kg": 1, "hs": ""}
    a.save_catalog()
    b.item_mem["Hàng B"] = {"div": 20, "kg": 2, "hs": ""}  # máy B chưa đọc lại bản của A
    b.save_catalog()
    c = make_store(data_dir, tmp_path, "c")
    assert {"Hàng A", "Hàng B"} <= set(c.item_mem)


def test_lock_file_is_removed_and_stale_lock_is_ignored(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    lock = data_dir / ".khoa_ghi"
    a.save_records()
    assert not lock.exists()
    lock.write_text("")
    import os
    os.utime(lock, (0, 0))  # khóa cũ do máy tắt đột ngột
    a.save_records()
    assert not lock.exists()


def test_declaration_folders_scan_disk_and_match_records(data_dir, tmp_path):
    s = make_store(data_dir, tmp_path, "a")
    r = rec("R1", "PO-R1", "2026-11-02")
    r["folder"] = "HAI_QUAN/Kodi/2026_Thang_11/2026-11-02"
    r["tkNo"] = "TK-123"
    s.records.insert(0, r)
    (data_dir / "HAI_QUAN" / "Kodi" / "2026_Thang_11" / "2026-11-02").mkdir(parents=True)
    (data_dir / "HAI_QUAN" / "Kodi" / "2026_Thang_11" / "2026-11-02" / "invoice.xlsx").write_text("x")
    (data_dir / "HAI_QUAN" / "Best" / "2026_Thang_10" / "2026-10-29").mkdir(parents=True)  # máy khác tạo, chưa có hồ sơ
    (data_dir / "HAI_QUAN" / "_KIEM_TRA").mkdir(parents=True)  # thư mục kiểm tra nội bộ: bỏ qua
    got = {o["customer"]: o for o in s.declaration_folders() if o["customer"] in ("Kodi", "Best")}
    assert got["Kodi"]["record"]["tkNo"] == "TK-123" and got["Kodi"]["files"] == 1
    assert got["Best"]["record"] is None and got["Best"]["day"] == "2026-10-29"
    assert not any(o["customer"] == "_KIEM_TRA" for o in s.declaration_folders())
    days = [o["day"] for o in s.declaration_folders()]
    assert days.index("2026-11-02") < days.index("2026-10-29")  # mới nhất trước


def test_folder_activity_reads_status_from_file_names(tmp_path):
    f = tmp_path / "d"
    f.mkdir()
    S = app.DedicatedDataStore
    assert S.folder_activity(str(f))["status"] == "Thư mục trống"
    for n in ("invoice_best_00000300_26.10.xlsx", "DongGoi_best_26.10.xlsx", "00_HO_SO_abc.json"):
        (f / n).write_text("x")
    a = S.folder_activity(str(f))
    assert a["status"] == "Đã chuẩn bị 3 chứng từ · chờ khai" and not a["other"]
    (f / "ghi chu.txt").write_text("x")
    assert S.folder_activity(str(f))["status"].startswith("Máy khác đã thêm file: ghi chu.txt")
    (f / "ToKhai_306891234560_Xanh.pdf").write_text("x")  # tờ khai do máy làm hải quan thêm
    a = S.folder_activity(str(f))
    assert a["tk"] == "306891234560" and a["status"] == "Đã khai · số tờ khai 306891234560"

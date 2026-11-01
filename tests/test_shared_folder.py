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

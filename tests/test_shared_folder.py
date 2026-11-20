"""Nhiều máy dùng chung một thư mục dữ liệu (không máy chủ): đọc thấy nhau, lưu không đè nhau."""
import os
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


def test_folder_activity_reads_status_and_checklist_from_file_names(tmp_path):
    f = tmp_path / "d"
    (f / "DO_PHAN_MEM_TAO").mkdir(parents=True)
    S = app.DedicatedDataStore
    modes = ["PKL", "VAT", "PXK", "PLX"]  # bộ của khách kiểu Arizon
    assert S.folder_activity(str(f), modes)["status"] == "Thư mục trống"
    for n in ("invoice_arz_00000243_21.09.xlsx", "Hoa_Don_VAT_BKAV_arz.xlsx", "PXK_KVCNB_BKAV_arz.xlsx", "PLX_arz.xlsx", "PO_goc_poarz243.pdf", "00_HO_SO_abc.json"):
        (f / "DO_PHAN_MEM_TAO" / n).write_text("x")
    a = S.folder_activity(str(f), modes)
    assert a["status"].startswith("Thiếu: PO (scan), Invoice (scan), PLX (scan), Hóa đơn Bkav (PDF)") and not a["other"]
    for n in ("poarz243.pdf", "ivarz.pdf", "PLXarizon243.pdf", "C26TAA-00003505-LXGEO7ZJ06E-DPH.pdf", "C26NAA-00000243-TXGELS33KO6-DPH.pdf", "dsh 243.xls"):
        (f / n).write_text("x")
    a = S.folder_activity(str(f), modes)
    assert a["missing"] == ["Tờ khai"] and a["status"] == "Thiếu: Tờ khai"
    (f / "ToKhaiHQ7N_QDTQ_108648746030.xlsx").write_text("x")  # tờ khai do máy làm hải quan thêm
    a = S.folder_activity(str(f), modes)
    assert a["tk"] == "108648746030" and a["status"] == "Đã khai · số tờ khai 108648746030 · Đủ bộ hồ sơ"


def test_declaration_folders_find_legacy_customer_folders_and_nested_hai_quan(data_dir, tmp_path):
    """Thư mục dữ liệu là HAI_QUAN: thư mục khách cũ (tên tự đặt, không có _Thang_) vẫn được liệt kê; HAI_QUAN lồng bên trong cũng được quét."""
    hq = tmp_path / "HAI_QUAN"
    (hq / "Tesa" / "Lo 30.10").mkdir(parents=True)
    (hq / "Tesa" / "Lo 30.10" / "306891234560_tokhai.pdf").write_text("x")
    (hq / "HAI_QUAN" / "Arizon" / "2026_Thang_11" / "2026-11-02").mkdir(parents=True)
    (hq / "MAU_CHUNG_TU" / "x").mkdir(parents=True)
    (hq / "MAU_CHUNG_TU" / "x" / "m.xlsx").write_text("x")
    s = make_store(hq, tmp_path / "w", "n")
    got = {o["customer"]: o for o in s.declaration_folders()}
    assert got["Tesa"]["day"] == "Lo 30.10" and got["Tesa"]["tk"] == "306891234560"
    assert "Arizon" in got and "MAU_CHUNG_TU" not in got and "HAI_QUAN" not in got


def test_reorganize_old_customer_folders_preview_move_and_undo(data_dir, tmp_path):
    hq = tmp_path / "HAI_QUAN"
    (hq / "Tesa" / "lo 30.10.2026").mkdir(parents=True)
    (hq / "Tesa" / "lo 30.10.2026" / "po.pdf").write_text("x")
    (hq / "Best" / "dot a").mkdir(parents=True)
    (hq / "Best" / "dot a" / "invoice_20261005.xlsx").write_text("y")
    (hq / "Best" / "2026_Thang_10" / "2026-10-01").mkdir(parents=True)  # đã đúng chỗ
    (hq / "Best" / "2026_Thang_10" / "2026-10-01" / "a.xlsx").write_text("z")
    (hq / "Best" / "le.pdf").write_text("loose")
    s = make_store(hq, tmp_path / "w", "ro")
    plan = s.plan_reorganize()
    dsts = {os.path.basename(p["src"]): p for p in plan}
    assert "a.xlsx" not in dsts and "2026-10-01" not in dsts
    assert dsts["lo 30.10.2026"]["date"] == "2026-10-30" and dsts["lo 30.10.2026"]["nguon"] == "tên thư mục"
    assert dsts["dot a"]["date"] == "2026-10-05" and dsts["dot a"]["nguon"] == "tên file"
    assert os.path.isdir(hq / "Tesa" / "lo 30.10.2026")  # xem trước chưa làm gì
    n, log = s.apply_reorganize(plan)
    assert n == len(plan) >= 3
    assert (hq / "Tesa" / "2026_Thang_10" / "2026-10-30" / "po.pdf").exists() and not (hq / "Tesa" / "lo 30.10.2026").exists()
    assert (hq / "Best" / "2026_Thang_10" / "2026-10-05" / "invoice_20261005.xlsx").exists()
    again = s.plan_reorganize()  # thư mục chuẩn có số PXK (hồ sơ/tên file) thì đổi tên thành <ngày>_<số PXK>; còn lại đã thống nhất
    assert all(os.path.basename(p["dst"]).startswith(os.path.basename(p["src"]) + "_") for p in again)
    assert s.undo_reorganize() == n
    assert (hq / "Tesa" / "lo 30.10.2026" / "po.pdf").exists() and (hq / "Best" / "le.pdf").exists()


def test_add_files_renames_pdfs_by_pxk_number_and_splits_folders(tmp_path):
    """Thả file vào hồ sơ: PDF Bkav đặt tên theo số phiếu xuất kho, tờ khai giữ tên, Excel/PO gốc cùng thư mục ngày."""
    src = tmp_path / "src"
    src.mkdir()
    pdfs = {}
    try:
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        font = next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",) if os.path.exists(f)), None)
        if font:
            pdfmetrics.registerFont(TTFont("DJ", font))
            c = canvas.Canvas(str(src / "bkav_pxk.pdf"))
            c.setFont("DJ", 12)
            c.drawString(50, 800, "PHIẾU XUẤT KHO KIÊM VẬN CHUYỂN NỘI BỘ")
            c.drawString(50, 780, "Số: 000000247   Ngày: 21/9/2026")
            c.save()
            pdfs["bkav_pxk.pdf"] = "PXK 247.pdf"
    except ImportError:
        pass
    for n in ("00000113_308389723740.xls", "dsh113.xlsx", "HĐ 00000008.pdf", "IV PK.xlsx", "ivable113.pdf", "poable113.pdf", "1.4.2026.zip"):
        (src / n).write_text("x")
    root = tmp_path / "HAI_QUAN"
    no, plan = app.plan_add_files(str(root), "Able", "2026-04-01", [str(src / n) for n in sorted(os.listdir(src))], "")
    by = {os.path.basename(p["src"]): p for p in plan}
    assert no == ("247" if pdfs else "113")
    if pdfs:
        assert by["bkav_pxk.pdf"]["new_name"] == "PXK 247.pdf"
    assert by["HĐ 00000008.pdf"]["new_name"] == f"HĐ {no}.pdf" and by["ivable113.pdf"]["new_name"] == f"Invoice {no}.pdf"
    assert by["00000113_308389723740.xls"]["new_name"] == "00000113_308389723740.xls" and by["00000113_308389723740.xls"]["area"] == "ngoai"
    assert by["dsh113.xlsx"]["area"] == "ngoai" and by["1.4.2026.zip"]["area"] == "ngoai"
    assert by["IV PK.xlsx"]["area"] == "tao" and by["poable113.pdf"]["new_name"] == "PO_goc_poable113.pdf"
    done = app.apply_add_files(plan)
    day = root / "Able" / "2026_Thang_04" / "2026-04-01"
    assert (day / f"HĐ {no}.pdf").exists() and (day / "invoice_IV PK.xlsx").exists() and len(done) == len(plan)
    again = app.apply_add_files(app.plan_add_files(str(root), "Able", "2026-04-01", [str(src / "ivable113.pdf")], "")[1])
    assert os.path.basename(again[0]) == f"Invoice {no}_2.pdf"  # không ghi đè


def test_reorganize_renames_standard_folder_to_date_and_pxk(tmp_path):
    hq = tmp_path / "HAI_QUAN"
    d = hq / "Arizon" / "2026_Thang_11" / "2026-11-03_02"
    d.mkdir(parents=True)
    (d / "C26NAA-00000316-ABC-DPH.pdf").write_text("x")
    s = make_store(hq, tmp_path / "w", "rn")
    plan = s.plan_reorganize()
    assert [(os.path.basename(p["src"]), os.path.basename(p["dst"])) for p in plan] == [("2026-11-03_02", "2026-11-03_00000316")]
    s.apply_reorganize(plan)
    assert (hq / "Arizon" / "2026_Thang_11" / "2026-11-03_00000316" / "C26NAA-00000316-ABC-DPH.pdf").exists() and s.plan_reorganize() == []


# ---- Gộp 3 bên, sao lưu, mang dữ liệu sang thư mục chung, bản xung đột OneDrive/Drive --------------------------------
def test_stale_machine_does_not_overwrite_newer_settings(data_dir, tmp_path):
    """Máy B mở từ trước, máy A đổi danh sách lái xe; B lưu việc khác thì KHÔNG được ghi đè danh sách mới của A."""
    a = make_store(data_dir, tmp_path, "a")
    b = make_store(data_dir, tmp_path, "b")
    a.vehicles = [{"driver": "Lái A", "plate": "29C-111.11"}]
    a.item_mem["Hàng cũ"] = {"div": 300, "kg": 1, "hs": ""}
    a.save_catalog()
    b.item_mem["Hàng B"] = {"div": 20, "kg": 2, "hs": ""}  # B chưa đọc lại
    b.save_catalog()
    c = make_store(data_dir, tmp_path, "c")
    assert c.vehicles == [{"driver": "Lái A", "plate": "29C-111.11"}]
    assert c.item_mem["Hàng cũ"]["div"] == 300 and "Hàng B" in c.item_mem


def test_deleted_entry_is_not_brought_back_by_other_machine(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.item_mem["Xóa đi"] = {"div": 1, "kg": 1, "hs": ""}
    a.save_catalog()
    b = make_store(data_dir, tmp_path, "b")
    del a.item_mem["Xóa đi"]
    a.save_catalog()
    b.item_mem["Hàng B"] = {"div": 2, "kg": 2, "hs": ""}  # B vẫn còn "Xóa đi" trong bộ nhớ
    b.save_catalog()
    c = make_store(data_dir, tmp_path, "c")
    assert "Xóa đi" not in c.item_mem and "Hàng B" in c.item_mem


def _cust(store, key="khachx", rows=None):
    store.custom_profiles[key] = {"label": "Khách X", "name": "CONG TY X"}
    store.custom_items[key] = rows or [{"code": "M1", "name": "Hàng 1", "div": 100, "kg": 1.0},
                                       {"code": "M2", "name": "Hàng 2", "div": 50, "kg": 2.0}]
    store.save_catalog()


def test_kg_kien_rows_merge_by_code_and_locked_row_wins(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    _cust(a)
    b = make_store(data_dir, tmp_path, "b")
    # A sửa tay M1 (🔒), B (chưa đọc lại) học lại M1 = 250 không khóa và sửa M2
    a.custom_items["khachx"][0].update(div=300, khoa=True)
    a.save_catalog()
    b.custom_items["khachx"][0].update(div=250)
    b.custom_items["khachx"][1].update(kg=2.5)
    b.custom_items["khachx"].append({"code": "M3", "name": "Hàng 3", "div": 10, "kg": 3.0})
    b.save_catalog()
    rows = {r["code"]: r for r in make_store(data_dir, tmp_path, "c").custom_items["khachx"]}
    assert rows["M1"]["div"] == 300 and rows["M1"]["khoa"]  # dòng 🔒 thắng
    assert rows["M2"]["kg"] == 2.5 and rows["M3"]["div"] == 10  # sửa/thêm của B vẫn còn
    assert b.custom_items["khachx"][0]["div"] == 300  # máy B cũng nhận ngay bản đã gộp


def test_backup_before_overwrite_and_throttle(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.save_catalog()
    a.save_catalog()
    bk = data_dir / "_SAO_LUU" / "master_catalog"
    n = len(list(bk.glob("*.json")))
    assert n >= 1
    a.save_catalog()
    assert len(list(bk.glob("*.json"))) == n  # tối đa 1 bản / 30 phút
    a.BACKUP_EVERY = 0
    a.save_records()
    assert list((data_dir / "_SAO_LUU" / "hongthien_records").glob("*.json"))
    assert not any(o["customer"] == "_SAO_LUU" for o in a.declaration_folders())


def test_join_empty_shared_folder_copies_everything(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    _cust(a)
    a.vehicles = [{"driver": "Lái A", "plate": "29C-111.11"}]
    a.save_catalog()
    a.records.insert(0, rec("A1", "PO-A"))
    a.save_records()
    (data_dir / "HAI_QUAN" / "Kodi" / "2026_Thang_11" / "2026-11-02").mkdir(parents=True)
    (data_dir / "HAI_QUAN" / "Kodi" / "2026_Thang_11" / "2026-11-02" / "po.pdf").write_text("x")
    shared = tmp_path / "OneDrive" / "HongThien"
    st = a.change_base_dir(str(shared), mang_theo=True)
    assert st["che_do"] == "chep" and st["file"] >= 1
    c = make_store(shared, tmp_path, "c")
    assert "khachx" in c.custom_items and c.vehicles[0]["driver"] == "Lái A" and any(r["id"] == "A1" for r in c.records)
    assert (shared / "HAI_QUAN" / "Kodi" / "2026_Thang_11" / "2026-11-02" / "po.pdf").exists()
    assert (data_dir / "master_catalog.json").exists()  # thư mục cũ giữ nguyên


def test_join_shared_folder_with_data_merges_and_keeps_user_name(data_dir, tmp_path):
    shared = tmp_path / "chung"
    a = make_store(shared, tmp_path, "a")  # máy A đã dùng thư mục chung
    _cust(a)
    a.records.insert(0, rec("A1", "PO-A"))
    a.save_records()
    b = make_store(data_dir, tmp_path, "b")  # máy B còn dữ liệu riêng
    b.set_user_name("Lan")
    _cust(b, rows=[{"code": "M1", "name": "Hàng 1", "div": 999, "kg": 1.0},
                   {"code": "M2", "name": "Hàng 2", "div": 75, "kg": 2.0, "khoa": True},
                   {"code": "M9", "name": "Hàng 9", "div": 9, "kg": 9.0}])
    b.records.insert(0, rec("B1", "PO-B"))
    b.save_records()
    st = b.change_base_dir(str(shared), mang_theo=True)
    assert st["che_do"] == "gop" and st["ho_so"] >= 1 and st["sao_luu"]
    assert b.user_name() == "Lan" and os.path.normcase(b.base_dir) == os.path.normcase(str(shared))
    rows = {r["code"]: r for r in make_store(shared, tmp_path, "c").custom_items["khachx"]}
    assert rows["M1"]["div"] == 100  # trùng: giữ bản trong thư mục chung
    assert rows["M2"]["div"] == 75 and rows["M2"]["khoa"]  # dòng 🔒 của máy B thắng
    assert rows["M9"]["div"] == 9  # mã chỉ máy B có: thêm vào
    ids = {r["id"] for r in make_store(shared, tmp_path, "d").records}
    assert {"A1", "B1"} <= ids


def test_onedrive_conflict_copy_is_merged_and_moved(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    _cust(a)
    import json
    other = json.loads((data_dir / "master_catalog.json").read_text(encoding="utf-8"))
    other["item_mem"]["Hàng máy kia"] = {"div": 40, "kg": 4, "hs": ""}
    other["custom_items"]["khachx"].append({"code": "M7", "name": "Hàng 7", "div": 7, "kg": 7.0})
    (data_dir / "master_catalog-PC-KHO.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    (data_dir / "hongthien_records (1).json").write_text(json.dumps([rec("Z1", "PO-Z")]), encoding="utf-8")
    assert a.sync()
    assert "Hàng máy kia" in a.item_mem and any(r["code"] == "M7" for r in a.custom_items["khachx"])
    assert any(r["id"] == "Z1" for r in a.records)
    assert not (data_dir / "master_catalog-PC-KHO.json").exists()
    assert len(list((data_dir / "_SAO_LUU" / "xung_dot").iterdir())) == 2
    assert app.DedicatedDataStore.conflict_copies(str(data_dir / "master_catalog.json")) == []

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
    assert s.plan_reorganize() == []  # đã thống nhất
    assert s.undo_reorganize() == n
    assert (hq / "Tesa" / "lo 30.10.2026" / "po.pdf").exists() and (hq / "Best" / "le.pdf").exists()


def test_add_files_renames_pdfs_by_pxk_number_and_splits_folders(tmp_path):
    """Thả file vào hồ sơ: PDF Bkav đặt tên theo số phiếu xuất kho, tờ khai giữ tên, Excel/PO gốc vào DO_PHAN_MEM_TAO."""
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
    assert (day / f"HĐ {no}.pdf").exists() and (day / "DO_PHAN_MEM_TAO" / "invoice_IV PK.xlsx").exists() and len(done) == len(plan)
    again = app.apply_add_files(app.plan_add_files(str(root), "Able", "2026-04-01", [str(src / "ivable113.pdf")], "")[1])
    assert os.path.basename(again[0]) == f"Invoice {no}_2.pdf"  # không ghi đè

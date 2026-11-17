"""Thư mục lô: thẻ hồ sơ 00_HO_SO.json, hàm chọn thư mục lô dùng chung (lot_folder_for) và chỉ mục quét nhanh.
Kế hoạch: ke_hoach/KE_HOACH_LUU_CHUNG_TU_THEO_KHACH.md, phần L1. Mọi test chạy trên thư mục tạm."""

import json
import os
import time

import pytest

import hongthien_desktop_app as app


def form_of(rec):
    return {
        "customer": rec["customer"], "doc_date": rec["docDate"], "po": rec["poNumber"],
        "po_date": rec.get("poDate", ""), "pxk": rec.get("pxkNo", ""), "hd": rec.get("hdNo", ""),
        "tk": rec.get("tkNo", ""), "luong": rec.get("luong", "Xanh"), "xe": rec.get("xeNo", ""),
        "driver": rec.get("driver", ""), "ldd": rec.get("lddSeq", ""), "po_dates": rec.get("poDates"),
        "pay_days": rec.get("payDays", ""), "delivery": rec.get("deliveryDate", ""),
    }


def new_rec(store, seed, po, day, pxk, cust="kodi"):
    src = seed[cust]
    return app.lot_build_record(store, form_of(src) | {"po": po, "doc_date": day, "pxk": pxk}, src["items"])


def age(path, seconds=3600):
    """Lùi giờ sửa của thư mục/file (để chỉ mục được phép nhớ: thư mục vừa sửa trong 2 giây không nhớ)."""
    t = time.time() - seconds
    for dp, ds, fs in os.walk(path, topdown=False):
        for n in fs + ds:
            os.utime(os.path.join(dp, n), (t, t))
    os.utime(path, (t, t))


def kodi_month(store, ym="2026_Thang_11"):
    return os.path.join(store.customs_root(), "Kodi", ym)


@pytest.fixture(autouse=True)
def no_error_file_next_to_app(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "get_app_dir", lambda: str(tmp_path / "app"))
    (tmp_path / "app").mkdir()


# ---- hàm chọn thư mục lô dùng chung -----------------------------------------------------------------------------
def test_two_exports_same_day_same_pxk_share_one_folder(store, seed):
    a = app.lot_export(store, new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318"), "PKL")
    b = app.lot_export(store, new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318"), "VAT")
    assert os.path.dirname(a["path"]) == os.path.dirname(b["path"]) == os.path.join(kodi_month(store), "2026-11-03_000318")
    assert sorted(os.listdir(kodi_month(store))) == ["2026-11-03_000318"]


def test_different_pxk_same_day_get_two_folders(store, seed):
    a = app.lot_export(store, new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318"), "PKL")
    b = app.lot_export(store, new_rec(store, seed, "PO-L1-B", "2026-11-03", "000319"), "PKL")
    assert os.path.dirname(a["path"]) != os.path.dirname(b["path"])
    assert sorted(os.listdir(kodi_month(store))) == ["2026-11-03_000318", "2026-11-03_000319"]


def test_pxk_written_without_leading_zeros_is_the_same_lot(store):
    folder = os.path.join(kodi_month(store), "2026-11-03_000318")
    os.makedirs(folder)
    assert store.lot_folder_for("kodi", "2026-11-03", "318") == folder


def test_day_only_folder_of_same_lot_is_reused_and_renamed(store, seed):
    """Thư mục <ngày> (VD do 'Thêm file vào hồ sơ' bản cũ tạo, có PXK 318.pdf) là của lô 318: xuất lô 318 thì dùng lại, đổi tên thành <ngày>_<PXK>."""
    plain = os.path.join(kodi_month(store), "2026-11-03")
    os.makedirs(plain)
    open(os.path.join(plain, "PXK 318.pdf"), "w").write("x")
    assert store.lot_folder_for("kodi", "2026-11-03", "000318") == plain  # chỉ tính: chưa đổi gì
    assert os.path.isdir(plain)
    res = app.lot_export(store, new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318"), "PKL")
    folder = os.path.join(kodi_month(store), "2026-11-03_000318")
    assert os.path.dirname(res["path"]) == folder and not os.path.exists(plain)
    assert "PXK 318.pdf" in os.listdir(folder)


def test_day_only_folder_of_another_lot_is_not_taken(store, seed):
    plain = os.path.join(kodi_month(store), "2026-11-03")
    os.makedirs(plain)
    open(os.path.join(plain, "PXK 317.pdf"), "w").write("x")  # lô khác (PXK 317)
    res = app.lot_export(store, new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318"), "PKL")
    assert os.path.dirname(res["path"]) == os.path.join(kodi_month(store), "2026-11-03_000318")
    assert os.listdir(plain) == ["PXK 317.pdf"]


def test_day_only_folder_with_card_of_other_pxk_is_not_taken(store):
    plain = os.path.join(kodi_month(store), "2026-11-03")
    store.write_lot_card({"id": "HS-X", "customer": "kodi", "docDate": "2026-11-03", "poNumber": "PO-X", "pxkNo": "000317"}, plain)
    assert store.lot_folder_for("kodi", "2026-11-03", "000318") == os.path.join(kodi_month(store), "2026-11-03_000318")


def test_new_record_folder_uses_shared_function(store, seed):
    rec = new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318")
    rel = store.new_record_folder(rec)
    assert store.rel_to_abs(rel) == store.lot_folder_for("kodi", "2026-11-03", "000318")
    assert rel.split(os.sep)[0] == app.CUSTOMS_ROOT


# ---- thẻ hồ sơ ---------------------------------------------------------------------------------------------------
def test_export_and_save_write_card(store, seed):
    rec = new_rec(store, seed, "PO-A + PO-B", "2026-11-03", "000318")
    res = app.lot_export(store, rec, "PKL")
    folder = os.path.dirname(res["path"])
    card = json.load(open(os.path.join(folder, app.LOT_CARD), encoding="utf-8"))
    assert card["id"] == rec["id"] and card["customer"] == "kodi" and card["pxkNo"] == "000318"
    assert card["poNumbers"] == ["PO-A", "PO-B"] and res["fname"] in card["files"]
    created = card["createdAt"]
    saved = app.lot_save_new(store, rec, {})
    card = json.load(open(os.path.join(folder, app.LOT_CARD), encoding="utf-8"))
    assert card["id"] == saved["id"] and card["createdAt"] == created and card["record"]["poNumber"] == "PO-A + PO-B"
    assert not [n for n in os.listdir(folder) if n.endswith(".tmp")]


def test_export_each_writes_card_once_with_all_files(store, seed):
    rec = new_rec(store, seed, "PO-L1-A", "2026-11-03", "000318")
    res = app.lot_export_each(store, rec)
    folder = os.path.dirname(res["files"][0]["path"])
    card = json.load(open(os.path.join(folder, app.LOT_CARD), encoding="utf-8"))
    assert set(f["name"] for f in res["files"]) <= set(card["files"])


def test_card_is_not_counted_as_a_document(store, tmp_path):
    folder = tmp_path / "lo"
    store.write_lot_card({"id": "HS-1", "customer": "kodi", "docDate": "2026-11-03"}, str(folder))
    a = app.DedicatedDataStore.folder_activity(str(folder), ["PKL"])
    assert a["other"] == [] and a["prepared"] == [] and a["status"] == "Thư mục trống"


def test_card_write_error_does_not_block_and_is_logged(store, tmp_path):
    blocker = tmp_path / "file_not_dir"
    blocker.write_text("x")
    assert store.write_lot_card({"id": "HS-1"}, str(blocker / "lo")) is False
    log = (tmp_path / "app" / "LOI_PHAN_MEM.txt").read_text(encoding="utf-8")
    assert app.LOT_CARD in log


# ---- ghép hồ sơ với thư mục qua thẻ ---------------------------------------------------------------------------------
def test_moved_lot_folder_is_still_matched_by_card(store, seed):
    rec = app.lot_save_new(store, new_rec(store, seed, "PO-MOVE", "2026-11-03", "000318"), {})
    app.lot_export(store, rec, "PKL")
    old = store.get_record_folder_path(rec)
    new = os.path.join(store.customs_root(), "Kodi", "Lo da chuyen", "lo 318")
    os.makedirs(os.path.dirname(new))
    os.rename(old, new)  # người dùng chuyển bằng Explorer
    got = [o for o in store.declaration_folders() if o["record"] and o["record"].get("id") == rec["id"]]
    assert [o["path"] for o in got] == [new]
    assert store.get_record_folder_path(rec) == new  # mở thư mục / xuất tiếp vào đúng chỗ mới


def test_lots_with_card_are_listed_without_records_file(store, seed, data_dir, tmp_path):
    rec = app.lot_save_new(store, new_rec(store, seed, "PO-LOST", "2026-11-03", "000318"), {})
    app.lot_export(store, rec, "PKL")
    os.remove(store.records_file)
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    again.config_file = str(tmp_path / "config_desktop.json")
    again.records = []
    got = [o for o in again.declaration_folders() if o["record"] and o["record"].get("id") == rec["id"]]
    assert len(got) == 1 and got[0]["record"]["poNumber"] == "PO-LOST" and got[0]["record"]["_fromCard"]
    ent = [e for e in again.declaration_entries() if e.get("id") == rec["id"]]
    assert ent and ent[0]["customer"] == "kodi" and ent[0]["pxkNo"] == "000318"


def test_old_step2_meta_file_is_read_as_card(store, tmp_path):
    folder = os.path.join(kodi_month(store), "2026-11-05_000400")
    os.makedirs(folder)
    with open(os.path.join(folder, "00_HO_SO_HS-OLD.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "HS-OLD", "customer": "kodi", "docDate": "2026-11-05", "poNumber": "PO-OLD", "pxkNo": "000400"}, f)
    got = [o for o in store.declaration_folders() if o["path"] == folder]
    assert got[0]["record"]["poNumber"] == "PO-OLD"


# ---- chỉ mục quét nhanh -----------------------------------------------------------------------------------------
def make_many_lots(store, n=2000):
    root = store.customs_root()
    for i in range(n):
        cust = f"Khach {i % 10}"
        y, m = 2020 + (i // 300) % 7, (i % 12) + 1
        d = os.path.join(root, cust, f"{y}_Thang_{m:02d}", f"{y}-{m:02d}-{(i % 28) + 1:02d}_{i:06d}")
        os.makedirs(d, exist_ok=True)
        for name in (f"invoice_k_{i:06d}_01.11.xlsx", "Hoa_Don_VAT_BKAV_k.xlsx", "PXK_KVCNB_BKAV_k.xlsx", f"PXK {i}.pdf", f"HĐ {i}.pdf", "po.pdf"):
            open(os.path.join(d, name), "w").close()
    age(root)


def test_second_scan_of_2000_lots_is_at_least_5x_faster(store):
    make_many_lots(store)
    t0 = time.perf_counter()
    first = store.declaration_folders()
    t1 = time.perf_counter()
    again = []
    for _ in range(3):  # lấy lần nhanh nhất để máy chạy test bận việc khác không làm test chập chờn
        s = time.perf_counter()
        second = store.declaration_folders()
        again.append(time.perf_counter() - s)
    assert len(first) == len(second) == 2000
    assert [o["status"] for o in first] == [o["status"] for o in second]
    assert (t1 - t0) >= 5 * min(again), f"lần đầu {t1 - t0:.3f}s, lần sau {min(again):.3f}s"


def test_index_notices_new_file_and_new_folder(store):
    folder = os.path.join(kodi_month(store), "2026-11-03_000318")
    os.makedirs(folder)
    open(os.path.join(folder, "invoice_kodi_000318_03.11.xlsx"), "w").close()
    age(store.customs_root())
    before = {o["path"]: o for o in store.declaration_folders()}
    assert "Tờ khai" not in before[folder]["have"]
    sig = store.folders_signature()
    open(os.path.join(folder, "ToKhai_307123456789.pdf"), "w").close()
    other = os.path.join(kodi_month(store), "2026-11-04_000319")
    os.makedirs(other)
    open(os.path.join(other, "po.pdf"), "w").close()
    assert store.folders_signature() != sig
    after = {o["path"]: o for o in store.declaration_folders()}
    assert after[folder]["tk"] == "307123456789" and other in after


def test_signature_skips_months_older_than_last_year(store):
    old = os.path.join(store.customs_root(), "Kodi", "2019_Thang_01", "2019-01-02_000001")
    os.makedirs(old)
    paths = [p for p, _m in store.folders_signature()]
    assert os.path.join(store.customs_root(), "Kodi") in paths and not any("2019_Thang_01" in p for p in paths)
    assert any(o["path"] == old for o in store.declaration_folders())  # mở danh sách vẫn thấy năm cũ

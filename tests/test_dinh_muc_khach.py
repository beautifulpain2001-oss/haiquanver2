"""Bảng kg & kiện theo khách: số sửa tay được giữ, học Invoice đúng sửa được số cũ học sai (Quang Ích 250 -> 300). Dữ liệu giả."""

import os

import openpyxl
import pytest

import hongthien_desktop_app as app

QI = {"name": "CÔNG TY TNHH CÔNG NGHIỆP BAO BÌ QUANG ÍCH VIỆT NAM", "label": "Quang Ích", "mst": "0202266122", "addr": "Hải Phòng", "unit": "Chiếc"}
NAME = "Ống giấy OPP TAPE đỏ, ngoài trắng,trong in 77x2.5x1265mm"
NAME2 = "Ống giấy 3K tapes in màu đỏ, ngoài trắng, trong in 77x2.5x1265mm"


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


def invoice(path, div=300):
    """Invoice kiểu Quang Ích: mã chung ô với tên, Số kiện là công thức =ROUNDUP((F/300),0) (1000 chiếc -> 4 kiện)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "INVOICE"
    ws.append(["STT", "Tên Hàng", "PO", "ĐVT", "Số Lượng", "Trọng lượng(kg)", "Trọng lượng cả bì(kg)", "Trọng lượng tịnh(kg)", "Số kiện", "Đơn Giá VND", "Thành Tiền VND"])
    for i, (code, name) in enumerate((("2V01PRB000002", NAME), ("2V01PRB000004", NAME2)), 2):
        ws.append([i - 1, f"{code} {name}", "20261020005", "Chiếc", 1000, 0.696, f"=H{i}+1", f"=E{i}*F{i}", f"=ROUNDUP((E{i}/{div}),0)", 12800, f"=E{i}*J{i}"])
    wb.save(path)
    return str(path)


def seed_quangich_250(store):
    """Tình trạng trên máy Huy: Quang Ích đã học bằng bản cũ (chia ngược 1000/4 = 250), số cũ nằm cả ở bộ nhớ định mức và Data tổng (nguồn 'tay' do xuất lô)."""
    store.save_learned_customer("quangich", dict(QI), [{"name": NAME, "code": "2V01PRB000002", "price": 12800, "div": 250, "kg": 0.696, "unit": "Chiếc"},
                                                       {"name": NAME2, "code": "2V01PRB000004", "price": 12800, "div": 250, "kg": 0.696, "unit": "Chiếc"}])
    store.dt_learn_items("quangich", [{"ten_sp": NAME, "ma_sp": "2V01PRB000002", "kg": 0.696, "div": 250}])
    assert store.get_item_norm(NAME)["div"] == 250


def test_hoc_lai_invoice_vao_khach_da_co_sua_so_cu(store, tmp_path):
    """Lỗi Huy báo: học Invoice đúng (=ROUNDUP(F14/300,0)) vào Quang Ích đã có mà SL/kiện vẫn 250, vì gộp chỉ điền ô trống."""
    seed_quangich_250(store)
    draft = app.learn_customer_from_documents([invoice(tmp_path / "inv.xlsx")])
    assert {it["code"]: it["div"] for it in draft["items"]} == {"2V01PRB000002": 300, "2V01PRB000004": 300}
    items = app.merge_learned_items(store.custom_items["quangich"], draft["items"])[0]
    store.save_learned_customer("quangich", dict(app.PROFILES["quangich"]), items)
    store.dinh_muc_dong_bo("quangich", draft["items"])
    assert {it["code"]: it["div"] for it in store.custom_items["quangich"]} == {"2V01PRB000002": 300, "2V01PRB000004": 300}
    assert store.get_item_norm(NAME)["div"] == 300
    assert app.lot_lookup_code(store, "quangich", "2V01PRB000002")["div"] == 300  # Data tổng 'tay' 250 cũ không còn thắng
    assert [h["div"] for h in app.lot_search_items(store, "quangich", "PRB000002")] == [300]


def test_merge_khong_ghi_de_dong_da_khoa():
    out, _a, filled = app.merge_learned_items([{"code": "A", "name": "Hàng A", "div": 250, "kg": 0.5, "khoa": True, "price": 1}, {"code": "B", "name": "Hàng B", "div": 250}],
                                              [{"code": "A", "name": "Hàng A", "div": 300, "kg": 0.7, "price": 9}, {"code": "B", "name": "Hàng B", "div": 300}])
    assert (out[0]["div"], out[0]["kg"], out[0]["price"]) == (250, 0.5, 1)  # khóa: giữ số sửa tay; giá vẫn chỉ điền ô trống
    assert out[1]["div"] == 300 and filled == 1


def test_bang_kg_kien_sua_tay_luu_dong_bo_va_giu_khi_hoc_invoice(store, tmp_path):
    seed_quangich_250(store)
    assert ("quangich", "Quang Ích") in store.dinh_muc_customers()
    rows = store.dinh_muc_rows("quangich")
    assert [(r["code"], r["div"], r["kg"]) for r in rows] == [("2V01PRB000002", 250, 0.696), ("2V01PRB000004", 250, 0.696)]
    for r in rows:
        r["_orig"] = {"code": r["code"], "name": r["name"]}
    rows[0].update(div=320, khoa=True)  # sửa tay 1 mã
    res = store.set_dinh_muc("quangich", rows, bi="1")
    assert res == {"sua": 1, "them": 0, "xoa": 0}
    assert app.PROFILES["quangich"]["tare"] == 1.0 and store.dinh_muc_bi("quangich") == 1.0
    assert app.lot_lookup_code(store, "quangich", "2V01PRB000002")["div"] == 320
    # học Invoice đúng sau đó: mã đã khóa giữ 320, mã chưa khóa lấy 300 theo công thức
    inv, errs = store.dinh_muc_tu_invoice([invoice(tmp_path / "inv.xlsx")])
    assert not errs and inv["2V01PRB000002"]["div"] == 300
    rows = store.dinh_muc_rows("quangich")
    res = app.dinh_muc_ap_invoice(rows, inv)
    assert [x[0] for x in res["doi"]] == ["2V01PRB000004"] and res["giu"] == [("2V01PRB000002", "div", 320, 300)]
    store.set_dinh_muc("quangich", rows)
    assert {r["code"]: r["div"] for r in store.dinh_muc_rows("quangich")} == {"2V01PRB000002": 320, "2V01PRB000004": 300}
    # học khách từ chứng từ (Học khách mới → lưu vào khách đã có) cũng không đè mã đã khóa
    draft = app.learn_customer_from_documents([invoice(tmp_path / "inv2.xlsx", div=150)])
    items = app.merge_learned_items(store.custom_items["quangich"], draft["items"])[0]
    store.save_learned_customer("quangich", dict(app.PROFILES["quangich"]), items)
    store.dinh_muc_dong_bo("quangich", draft["items"])
    assert {r["code"]: r["div"] for r in store.dinh_muc_rows("quangich")} == {"2V01PRB000002": 320, "2V01PRB000004": 150}
    # lưu xong mở lại phần mềm vẫn còn
    s2 = app.DedicatedDataStore(base_dir=store.base_dir)
    assert {(it["code"], it["div"], bool(it.get("khoa"))) for it in s2.custom_items["quangich"]} == {("2V01PRB000002", 320, True), ("2V01PRB000004", 150, False)}


def test_bang_kg_kien_them_xoa_va_kiem_tra_so(store):
    seed_quangich_250(store)
    rows = [dict(r, _orig={"code": r["code"], "name": r["name"]}) for r in store.dinh_muc_rows("quangich")][:1]  # bỏ mã thứ 2 = xóa
    rows.append({"code": "2V01NEP00001", "name": "Nẹp góc chữ V 50x50x5", "unit": "Chiếc", "div": 20, "kg": 0.1, "khoa": True, "_orig": None})
    assert store.set_dinh_muc("quangich", rows) == {"sua": 0, "them": 1, "xoa": 1}
    assert [it["code"] for it in store.custom_items["quangich"]] == ["2V01PRB000002", "2V01NEP00001"]
    with pytest.raises(ValueError, match="phải là số"):
        store.set_dinh_muc("quangich", [{"code": "X", "name": "Y", "div": "abc"}])
    with pytest.raises(ValueError, match="trùng"):
        store.set_dinh_muc("quangich", [{"code": "X", "name": "Y"}, {"code": "X", "name": "Z"}])


def test_hop_thoai_kg_kien(qapp, store, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from ui_qt import widgets
    from ui_qt.dinh_muc import DinhMucDialog
    monkeypatch.setattr(widgets, "ask", lambda *a, **k: True)
    monkeypatch.setattr(widgets, "warn", lambda *a, **k: None)
    seed_quangich_250(store)
    dlg = DinhMucDialog(app, store, "quangich")
    assert dlg.key == "quangich" and dlg.table.rowCount() == 2 and dlg.table.item(0, 3).text() == "250"
    dlg.table.item(1, 3).setText("280")  # sửa tay -> tự khóa
    assert dlg.rows[1]["div"] == 280 and dlg.rows[1]["khoa"] and dlg.table.item(1, 5).checkState() == Qt.Checked
    dlg.load_invoice([invoice(tmp_path / "inv.xlsx")])
    assert dlg.table.item(0, 3).text() == "300" and dlg.table.item(1, 3).text() == "280"
    assert "Giữ nguyên 1 ô" in dlg.msg.text()
    dlg.save()
    assert {r["code"]: r["div"] for r in store.dinh_muc_rows("quangich")} == {"2V01PRB000002": 300, "2V01PRB000004": 280}
    assert not dlg.dirty
    dlg.close()

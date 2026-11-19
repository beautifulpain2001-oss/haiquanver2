"""Quang Ích: tên hàng 'mã + tên' trên Hóa đơn VAT và PXK Bkav; số kiện luôn dùng ROUNDUP; cập nhật SL/kiện theo mã (Arizon, sheet CN). Dữ liệu giả."""

import json

import openpyxl
import pytest

import hongthien_desktop_app as app

QI = {"name": "CÔNG TY TNHH CÔNG NGHIỆP BAO BÌ QUANG ÍCH VIỆT NAM", "label": "Quang Ích", "mst": "0202266122", "addr": "Hải Phòng", "unit": "ống", "poInDocs": True, "linePo": True}
ITEMS = [{"name": "Ống giấy OPP TAPE đỏ, ngoài trắng,trong in 77x2.5x1265mm", "code": "2V01PRB000002", "unit": "ống", "price": 12800, "div": 0, "kg": 0.696}]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


def make_rec(store, key, items, **form):
    f = {"customer": key, "doc_date": "2026-11-06", "po": "20261030001", "pxk": "00000321", "hd": "00001"}
    f.update(form)
    return app.lot_build_record(store, f, items)


def test_quangich_vat_and_pxk_name_is_code_plus_name(store):
    store.save_learned_customer("quangich", dict(QI), [dict(x) for x in ITEMS])
    item = {"stt": 1, "po": "20261030001", "ma_sp": "2V01PRB000002", "ten_sp": ITEMS[0]["name"], "unit": "ống", "qty": 2500, "price": 12800, "amount": 32000000, "div": 0, "kg": 0.696, "kien": 0, "net": 1740, "gross": 1741}
    rec = make_rec(store, "quangich", [item])
    expected = "2V01PRB000002 " + ITEMS[0]["name"]
    for mode, col, row in (("PXK", "E", 3), ("VAT", "C", 6)):
        ws = openpyxl.load_workbook(app.lot_export(store, rec, mode)["path"]).active
        assert ws[f"{col}{row}"].value == expected, mode
    # khách khác không bị đổi
    store.save_learned_customer("khac", {"name": "CÔNG TY KHÁC", "label": "Khac", "mst": "0100000001", "addr": "BN", "unit": "ống"}, [dict(ITEMS[0])])
    ws = openpyxl.load_workbook(app.lot_export(store, make_rec(store, "khac", [item]), "PXK")["path"]).active
    assert ws["E3"].value == ITEMS[0]["name"]


def test_so_kien_is_roundup_formula_in_standard_invoice(store):
    store.save_learned_customer("kien1", {"name": "CÔNG TY KIEN", "label": "Kien", "mst": "0100000002", "addr": "BN", "unit": "chiếc"}, [{"name": "Ống A", "code": "A1", "price": 10, "div": 75, "kg": 0.5}])
    item = {"stt": 1, "po": "P", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 1000, "price": 10, "amount": 10000, "div": 75, "kg": 0.5, "kien": 14, "net": 500, "gross": 501}
    rec = make_rec(store, "kien1", [item])
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "PKL")["path"]).active
    kien = [c.value for row in ws.iter_rows(min_row=13, max_row=13) for c in row if isinstance(c.value, str) and "ROUNDUP(E13/" in c.value]
    assert kien == ["=ROUNDUP(E13/75,0)"]  # 1000/75 = 13,33 -> 14


def test_cap_nhat_kien_from_cn_sheet_updates_div_by_code(store):
    store.save_learned_customer("arz9", {"name": "CÔNG TY TNHH CÔNG NGHỆ ARIZON (VIỆT NAM)", "label": "Arizon", "mst": "0901155231", "addr": "Hưng Yên", "unit": "Chiếc"},
                                [{"name": "Ống giấy phi 76.2 x 5 x 62", "code": "3609100620001", "price": 2954, "div": 100, "kg": 0.1}, {"name": "Ống 153x5x100", "code": "3609301000001", "price": 1, "div": 0, "kg": 1}])
    data = {"version": "hongthien-hoc-v1", "cap_nhat_kien": {"khach": "Arizon", "so_ong_moi_kien": {"3609100620001": 196, "3609301000001": 36, "9999999999999": 5}}}
    res = store.import_learned(data)
    assert res["kien"] == 2 and res["kien_thieu"] == ["9999999999999"]
    divs = {it["code"]: it["div"] for it in store.custom_items["arz9"]}
    assert divs == {"3609100620001": 196, "3609301000001": 36} and store.get_item_norm("Ống giấy phi 76.2 x 5 x 62")["div"] == 196
    with pytest.raises(ValueError, match="chưa có khách"):
        store.import_learned({"cap_nhat_kien": {"khach": "Khong co", "so_ong_moi_kien": {"1": 2}}})


def test_read_report_shown_for_text_layer_po_and_new_item_is_ok(store):
    """PO có lớp chữ cũng báo 'đọc được hay không'; mặt hàng mới chưa có trong danh mục là ĐỌC ĐƯỢC (ghi chú cần nhập kg/kiện), không phải 'phải suy ra'."""
    from ui_qt.state import Lot
    store.save_learned_customer("arzpo", {"name": "CÔNG TY TNHH ARIZON THỬ", "label": "ArzPo", "mst": "0100000010", "addr": "HY", "unit": "Chiếc", "po_pattern": r"VN-\d{4}-\d{12}"},
                                [{"name": "Ống giấy phi 76.2 x 5 x 57mm", "code": "3609100570001", "price": 2716, "div": 196, "kg": 0.057}])
    items = [{"stt": 1, "po": "VN-3501-202611050004", "ma_sp": "3609100570001", "ten_sp": "Ống giấy phi 76.2 x 5 x 57mm", "unit": "Chiếc", "qty": 200, "price": 2716, "amount": 543200, "div": 196, "kg": 0.057, "kien": 2, "net": 11.4, "gross": 12.4},
             {"stt": 2, "po": "VN-3501-202611050004", "ma_sp": "3607000000003", "ten_sp": "Nắp nhựa 163*32", "unit": "Chiếc", "qty": 2000, "price": 6880, "amount": 13760000, "div": 0, "kg": 0, "kien": 0, "net": 0, "gross": 0}]
    lot = Lot(app, store)
    lot.select_customer("arzpo")
    lot.apply_po({"ok": True, "customer": "arzpo", "po": "VN-3501-202611050004", "po_date": "", "po_dates": {}, "items": items, "msg": "x", "schedules": None, "schedule_key": "", "doc_date": ""})
    assert [it["read"] for it in lot.items] == ["ok", "ok"] and lot.items[1]["new_item"]
    assert lot.read_text.startswith("PO VN-3501-202611050004: ✅ Đã đọc đủ 2/2 dòng.") and "Dòng 2 là mặt hàng mới" in lot.read_text


def test_unify_pxk_leaves_only_current_number():
    import mau_chung_tu
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["I2"], ws["A5"], ws["B7"], ws["C1"] = "PXKKVCNB : 00000299", "Số PXK: 00000250 (cũ)", "PXKKVCNB: 00000250", "Số ĐĐH: POS26999"
    assert mau_chung_tu.unify_pxk(ws, "00000301") == 3
    assert [ws[a].value for a in ("I2", "A5", "B7", "C1")] == ["PXKKVCNB : 00000301", "Số PXK: 00000301 (cũ)", "PXKKVCNB: 00000301", "Số ĐĐH: POS26999"]


def test_edit_so_kien_and_kg_applies_to_export_and_is_remembered_by_code(store):
    """Sửa SL/kiện 50 -> 60 và kg/chiếc ở một dòng: file xuất ra dùng số mới ở MỌI dòng cùng mã; danh mục khách ghi lại theo MÃ (kể cả khi tên trên PO khác tên danh mục)."""
    from ui_qt.state import Lot
    store.save_learned_customer("arzed", {"name": "CÔNG TY TNHH ARIZON SỬA", "label": "ArzEd", "mst": "0100000020", "addr": "HY", "unit": "Chiếc"},
                                [{"name": "Ống catalog 76.2 x 5 x 57", "code": "3609100570001", "price": 2716, "div": 50, "kg": 0.1}])
    base = {"po": "P1", "ma_sp": "3609100570001", "ten_sp": "Ống theo tên trên PO", "hs": "", "unit": "Chiếc", "qty": 1000, "price": 2716, "amount": 2716000, "div": 50, "kg": 0.1, "kien": 20, "net": 100.0, "gross": 101.0, "tare": 1.0}
    lot = Lot(app, store)
    lot.select_customer("arzed")
    lot.items = [dict(base), dict(base, po="P2", qty=500, amount=1358000, kien=10, net=50.0, gross=51.0)]
    lot.form.update(po="P1 + P2", pxk="0000999", hd="1")
    lot.save_item({"po": "P1", "ma_sp": "3609100570001", "ten_sp": "Ống theo tên trên PO", "hs": "", "unit": "Chiếc", "qty": "1000", "price": "2716", "div": "60", "kg": "0.2"}, 0)
    assert [(i["div"], i["kg"], i["kien"], i["net"]) for i in lot.items] == [(60.0, 0.2, 17, 200.0), (60.0, 0.2, 9, 100.0)]  # dòng cùng mã được đồng bộ và tính lại (làm tròn lên)
    ws = openpyxl.load_workbook(lot.export("PKL")["files"][0]["path"]).active
    formulas = [c.value for row in ws.iter_rows(min_row=13, max_row=14) for c in row if isinstance(c.value, str) and "/60" in c.value]
    assert formulas == ["=ROUNDUP(E13/60,0)", "=ROUNDUP(E14/60,0)"]
    cat = store.items_for_customer("arzed")[0]  # tên danh mục khác tên trên PO: vẫn được cập nhật theo mã để dùng cho lần sau
    assert (cat["div"], cat["kg"]) == (60.0, 0.2) and store.get_item_norm("Ống catalog 76.2 x 5 x 57")["div"] == 60.0


def test_item_dialog_does_not_overwrite_edited_numbers_when_code_field_loses_focus(qapp, store):
    """Sửa SL/kiện và kg rồi rời/quay lại ô Mã hàng: số vừa sửa không bị điền lại bằng số cũ trong danh mục; đổi sang mã khác thì mới tự điền."""
    from ui_qt.dialogs import ItemDialog
    from ui_qt.state import Lot
    store.save_learned_customer("arzd", {"name": "CÔNG TY TNHH ARIZON DLG", "label": "ArzDlg", "mst": "0100000030", "addr": "HY", "unit": "Chiếc"},
                                [{"name": "Ống A", "code": "A1", "price": 10, "div": 50, "kg": 0.1}, {"name": "Ống B", "code": "B2", "price": 20, "div": 70, "kg": 0.3}])
    lot = Lot(app, store)
    lot.select_customer("arzd")
    lot.items = [{"po": "P", "ma_sp": "A1", "ten_sp": "Ống A", "hs": "", "unit": "Chiếc", "qty": 1000, "price": 10, "amount": 10000, "div": 50, "kg": 0.1, "kien": 20, "net": 100.0, "gross": 101.0}]
    dlg = ItemDialog(lot, 0)
    dlg.edits["div"].setText("60")
    dlg.edits["kg"].setText("0.2")
    dlg.edits["ma_sp"].editingFinished.emit()  # rời ô Mã hàng, mã vẫn là A1
    assert (dlg.edits["div"].text(), dlg.edits["kg"].text()) == ("60", "0.2")
    dlg.save()
    assert (lot.items[0]["div"], lot.items[0]["kg"], lot.items[0]["kien"]) == (60.0, 0.2, 17)
    dlg2 = ItemDialog(lot, 0)
    dlg2.edits["ma_sp"].setText("B2")
    dlg2.edits["ma_sp"].editingFinished.emit()  # đổi sang mã khác: tự điền theo danh mục
    assert (dlg2.edits["ten_sp"].text(), dlg2.edits["div"].text()) == ("Ống B", "70")
    dlg.close()
    dlg2.close()


def test_merge_duplicate_codes_and_split_back(qapp, store):
    """Gộp dòng cùng mã + cùng giá (cộng SL, tính lại kiện), nhớ dòng gốc; khung PO chia ô theo PO; tách lại về như cũ."""
    from ui_qt.pages_lot import ItemsStep
    from ui_qt.state import Lot
    store.save_learned_customer("arzm", {"name": "CÔNG TY TNHH ARIZON M", "label": "ArzM", "mst": "0100000031", "addr": "HY", "unit": "Chiếc"},
                                [{"name": "Ống A", "code": "A1", "price": 10, "div": 50, "kg": 0.1}])
    lot = Lot(app, store)
    lot.select_customer("arzm")
    base = {"ma_sp": "A1", "ten_sp": "Ống A", "hs": "", "unit": "Chiếc", "price": 10, "div": 50, "kg": 0.1, "page": 1}
    lot.items = [dict(base, po="P1", qty=100, po_file="a.pdf", box=[(0, 0), (1, 0), (1, .1), (0, .1)]),
                 dict(base, po="P2", qty=60, po_file="b.pdf", box=[(0, .2), (1, .2), (1, .3), (0, .3)]),
                 dict(base, ma_sp="B2", ten_sp="Ống B", po="P1", qty=5, po_file="a.pdf"),
                 dict(base, po="P1", qty=40, price=12, po_file="a.pdf")]
    lot.recalc()
    assert lot.can_merge() and lot.merge_duplicates() == 1
    assert [(x["ma_sp"], x["qty"]) for x in lot.items] == [("A1", 160.0), ("B2", 5), ("A1", 40)]
    m = lot.items[0]
    assert (m["po"], m["kien"], len(m["parts"])) == ("P1 + P2", 4, 2)
    page = ItemsStep(lot)
    specs = page.specs_of(0)
    assert [s[0] for s in specs] == ["a.pdf", "b.pdf"] and all(s[2] for s in specs)
    assert len(page.specs_of(1)) == 1
    lot.split_merged()
    assert [x["qty"] for x in lot.items] == [100, 60, 5, 40] and not lot.has_merged()
    page.close()


def test_merged_lot_refreshes_and_exports(qapp, store, tmp_path):
    from ui_qt.pages_lot import ItemsStep
    from ui_qt.state import Lot
    lot = Lot(app, store)
    lot.select_customer("tesa")
    it = {"ma_sp": "X1", "ten_sp": "Băng keo", "hs": "48229090", "unit": "ống", "price": 5, "div": 10, "kg": 0.1, "po": "P1", "qty": 100}
    lot.items = [dict(it), dict(it, qty=25)]
    lot.recalc()
    page = ItemsStep(lot)
    lot.merge_duplicates()
    page.refresh()
    assert page.table.rowCount() == 1 and "Gộp 2 dòng" in page.table.item(0, 14).text() and "Tách" in page.merge_btn.text()
    page.table.selectRow(0)
    page.show_viewer()
    assert lot.record()["items"][0]["qty"] == 125
    page.merge()
    assert page.table.rowCount() == 2
    page.close()


def test_code_links_erp_and_customer_entries(store):
    """Cùng mã khách: mục ERP (70g, mã ERP) và mục học từ invoice (67g, SL/kiện) gộp một; số khai theo invoice (ưu tiên hơn ERP), ERP chỉ để đối chiếu; sửa tay thắng cả hai."""
    store.save_learned_customer("arzl", {"name": "CÔNG TY TNHH ARIZON L", "label": "ArzL", "mst": "0100000032", "addr": "HY", "unit": "Chiếc"},
                                [{"name": "Ống giấy 76x5x67", "code": "3609100670001", "price": 10, "div": 0, "kg": 0.067}])
    store._dt_upsert("ArzL", "Ống giấy 76x5x67", ma_hang="3609100670001", kg=0.067, kg_nguon="invoice", kien=200, kien_nguon="invoice", exact=True)
    store._dt_upsert("ArzL", "ống 76x5x67, T.nâu", ma_erp="FG10496-010-00000", kg=0.07, kg_nguon="erp", exact=True, ma_kh="3609100670001")
    m = store.dt_merged("arzl", "FG10496-010-00000")  # tra bằng mã ERP cũng ra mục kia
    assert (m["kg"], m["kien"], m["ma_erp"], m["ma_hang"]) == (0.067, 200, "FG10496-010-00000", "3609100670001")
    line = {"ma_sp": "3609100670001", "ten_sp": "Ống giấy 76x5x67", "qty": 1000, "kg": 0.067, "div": 0, "tare": 0}
    assert store.dt_fill_lines("arzl", [line]) == 1
    assert (line["kg"], line["div"], line["kien"], line["net"], line["ma_erp"]) == (0.067, 200.0, 5, 67.0, "FG10496-010-00000")
    assert "ERP" not in str(line.get("read_note") or "")
    erp = app.lot_erp_info(store, "arzl", line)  # nút "Hiện dữ liệu ERP": vẫn xem được số ERP
    assert (erp["ma_erp"], erp["kg"], erp["ten_erp"]) == ("FG10496-010-00000", 0.07, "ống 76x5x67, T.nâu")
    hit = app.lot_lookup_code(store, "arzl", "FG10496-010-00000")
    assert (hit["kg"], hit["div"], hit["ma_erp"]) == (0.067, 200, "FG10496-010-00000")
    # dòng chưa có kg (invoice không ghi): ERP điền chỗ trống
    empty = {"ma_sp": "FG10496-010-00000", "ten_sp": "x", "qty": 1000, "kg": 0, "div": 0, "tare": 0}
    store._dt_upsert("ArzL", "Ống giấy 76x5x67", ma_hang="3609100670001", kg=0, exact=True)
    store.dt_fill_lines("arzl", [empty])
    assert empty["kg"] > 0
    # sửa tay (đã xác nhận) thắng cả invoice lẫn ERP
    store.dt_confirm_item("arzl", "Ống giấy 76x5x67", "3609100670001", 0.068, 200)
    line2 = {"ma_sp": "3609100670001", "ten_sp": "Ống giấy 76x5x67", "qty": 1000, "kg": 0.067, "div": 200, "tare": 0}
    store.dt_fill_lines("arzl", [line2])
    assert line2["kg"] == 0.068


def test_gross_uses_tare_field_for_every_invoice(qapp, store):
    """Ô 'Bì cộng thêm mỗi dòng' ở bước ④ quyết định cả bì = tịnh + bì trên mọi invoice, kể cả dòng đã đọc với bì khác."""
    from ui_qt.state import Lot
    lot = Lot(app, store)
    lot.select_customer("tesa")
    lot.items = [{"po": "P", "ma_sp": "X", "ten_sp": "Ống", "hs": "", "unit": "ống", "qty": 100, "price": 5, "div": 10, "kg": 0.25, "tare": 1.0, "net": 25.0, "gross": 26.0}]
    lot.form["tare"] = "0.5"
    rec = lot.record()
    assert (rec["items"][0]["net"], rec["items"][0]["gross"], rec["items"][0]["tare"]) == (25.0, 25.5, 0.5)
    ws = openpyxl.load_workbook(app.lot_export(store, dict(rec, docDate="2026-11-05"), "PKL")["path"]).active
    assert any(c.value == "=F13+0.5" or c.value == "=H13+0.5" for row in ws.iter_rows(min_row=13, max_row=13) for c in row)


def test_bkav_vat_and_pxk_merge_identical_lines(store):
    store.save_learned_customer("mg1", {"name": "CÔNG TY MG", "label": "Mg", "mst": "0100000033", "addr": "BN", "unit": "chiếc"}, [{"name": "Ống A", "code": "A1", "price": 10, "div": 50, "kg": 0.1}])
    base = {"po": "P", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "price": 10, "div": 50, "kg": 0.1}
    items = [dict(base, qty=100, amount=1000), dict(base, ma_sp="B2", ten_sp="Ống B", qty=5, amount=50), dict(base, qty=60, amount=600), dict(base, qty=7, price=12, amount=84)]
    rec = make_rec(store, "mg1", items)
    for mode, col_qty in (("VAT", "F"), ("PXK", "G")):
        ws = openpyxl.load_workbook(app.lot_export(store, rec, mode)["path"]).active
        first = 6 if mode == "VAT" else 3
        qtys = [ws[f"{col_qty}{r}"].value for r in range(first, first + 5) if ws[f"{col_qty}{r}"].value is not None]
        assert qtys == [160, 5, 7], (mode, qtys)


def test_m22_and_lam_san_forms_only_when_due(qapp, store, tmp_path):
    """Arizon có Mẫu số 22 (điền số tờ khai); Tesa chỉ có bảng kê lâm sản khi lô có pallet."""
    import mau_rieng
    store.save_learned_customer("arz22", {"name": "CÔNG TY TNHH CÔNG NGHỆ ARIZON (VIỆT NAM)", "label": "Arz22", "mst": "0901155231", "addr": "HY", "unit": "Chiếc"},
                                [{"name": "Ống A", "code": "A1", "price": 10, "div": 50, "kg": 0.1}])
    item = {"stt": 1, "po": "P", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 100, "price": 10, "amount": 1000, "div": 50, "kg": 0.1, "kien": 2, "net": 10.0, "gross": 11.0}
    rec = dict(make_rec(store, "arz22", [item]), tkNo="308800000001", tkNhap="108500000002", docDate="2026-11-09")
    assert "M22" in app.lot_bundle_modes(rec)
    # Arizon đã ghi sẵn "PLX,DNTT,BBGH" ở chứng từ làm thêm: vẫn phải có Mẫu số 22
    assert "M22" in app.customer_extra_docs({"name": "CÔNG TY TNHH CÔNG NGHỆ ARIZON (VIỆT NAM)", "extraDocs": "PLX,DNTT,BBGH"})
    res = app.lot_export(store, rec, "M22")
    text = mau_rieng.preview("docx", open(res["path"], "rb").read())["text"]
    assert "308800000001" in text and "108500000002" in text and "9/11/2026" in text and "308829221060" not in text
    # Tesa: ống không có bảng kê lâm sản, pallet thì có
    tube = dict(item, ma_sp="X", ten_sp="Ống lõi giấy phi 76")
    pallet = dict(item, ma_sp="39776-90000-00", ten_sp="Pallet bằng gỗ", unit="cái", qty=180, kg=21.0, net=3780.0, gross=3780.0, hs="44152000")
    assert "BKLS" not in app.lot_bundle_modes(dict(make_rec(store, "tesa", [tube]), items=[tube]))
    rec_p = dict(make_rec(store, "tesa", [pallet]), docDate="2026-11-02")
    assert "BKLS" in app.lot_bundle_modes(rec_p)
    with pytest.raises(ValueError, match="pallet"):
        app.lot_export(store, dict(rec_p, items=[tube]), "BKLS")
    res = app.lot_export(store, rec_p, "BKLS")
    text = mau_rieng.preview("docx", open(res["path"], "rb").read())["text"]
    assert "3.780" in text and "180" in text and "2026.02.11" in text and "7.560" not in text


def test_bilingual_po_duplicate_line_is_not_a_new_item(store):
    """PO song ngữ: dòng chữ Hán OCR lặp lại quy cách (không có giá/thành tiền) không được đọc thành dòng hàng thứ ba."""
    cat = [{"name": "Ống lõi giấy 78 x 6 x 1002mm", "code": "", "price": 32023, "div": 5, "kg": 1.366, "unit": "Cái"},
           {"name": "Ống lõi giấy 78 x 6 x 1030mm", "code": "", "price": 33000, "div": 5, "kg": 0, "unit": "Cái"}]
    text = ("Số 28102026-01 HT-SS\nSTT Tên Hàng DVT\nOng lõi giấy quy cách Cái\n01 | 78*6*1002mm 18 2000 32.023 64.046.000\n"
            "Z4 BLAS 78%6*1002mm__|\nÔng lõi giấy quy cách Cái\n02 | 78*6*1030mm ez 200 33.000 6.600.000 | mau đã\nRRS BF ALA 78*6*1030mm h-\n")
    _po, _d, lines = app.parse_generic_po_text(text, {"po_pattern": r"\d{8}-\d{2}\s*HT-SS", "unit": "cái"}, cat)
    assert [(x["ten_sp"][-6:], x["qty"], x["price"]) for x in lines] == [("1002mm", 2000, 32023), ("1030mm", 200, 33000)]


def test_kho_mau_lists_m22_for_arizon_and_lam_san_for_tesa(store):
    store.save_learned_customer("arz22b", {"name": "CÔNG TY TNHH CÔNG NGHỆ ARIZON (VIỆT NAM)", "label": "Arz22b", "mst": "0901155231", "addr": "HY", "unit": "Chiếc"}, [])
    docs = {d["mode"]: d for d in store.customer_docs("arz22b")}
    assert docs["M22"]["ext"] == "docx" and docs["M22"]["kind"] == "fixed"
    assert {d["mode"]: d["ext"] for d in store.customer_docs("tesa")}["BKLS"] == "docx"
    for key, mode in (("arz22b", "M22"), ("tesa", "BKLS")):
        ext, data, _w = app.form_from_builtin(store, key, mode, tokenize=False)
        assert ext == "docx" and data[:2] == b"PK"


def test_invoice_total_weights_are_not_rounded(store, tmp_path):
    """Dòng Tổng cộng của invoice: tổng trọng lượng là công thức SUM của các dòng trên, hiện đủ 3 số lẻ (không làm tròn 2 số)."""
    store.save_learned_customer("tot1", {"name": "CÔNG TY TOT", "label": "Tot", "mst": "0100000034", "addr": "BN", "unit": "chiếc"}, [{"name": "Ống A", "code": "A1", "price": 10, "div": 50, "kg": 0.0903}])
    item = {"stt": 1, "po": "P", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 150, "price": 10, "amount": 1500, "div": 50, "kg": 0.0903, "kien": 3, "net": 13.545, "gross": 14.545}
    ws = openpyxl.load_workbook(app.lot_export(store, make_rec(store, "tot1", [item]), "PKL")["path"]).active
    totals = [c for row in ws.iter_rows(min_row=14, max_row=14) for c in row if isinstance(c.value, str) and c.value.upper().startswith(("=SUM(", "=SUBTOTAL("))]
    weights = [c for c in totals if c.column_letter in "GH"]
    assert weights and all(c.number_format == app.WT2 for c in weights)
    # mẫu Arizon của khách: ô tổng trọng lượng cũng đủ 3 số lẻ
    import mau_chung_tu
    t = openpyxl.Workbook()
    w = t.active
    w.title = "9.2"
    w["A24"] = "x"
    w.print_area = "A1:N24"
    w["I21"], w["K21"] = "=SUM(I13:I20)", "=SUM(K13:K20)"
    w["I21"].number_format = w["K21"].number_format = "#,##0.00"
    path = tmp_path / "arz.xlsx"
    t.save(path)
    out = mau_chung_tu.fill_pkl_arizon(app, openpyxl.Workbook(), {"docDate": "2026-11-05", "pxkNo": "1", "items": [item]}, {"name": "ARZ", "addr": "HY", "unit": "chiếc"}, mau_chung_tu.load_template(str(path)), "Inv")
    tot = [c for row in out.iter_rows(min_row=14) for c in row if isinstance(c.value, str) and c.value.upper().startswith("=SUM(") and c.column_letter in "IK"]
    assert len(tot) == 2 and all(c.number_format == app.WT2 for c in tot)


def test_code_plus_name_never_repeats_the_code(store):
    """Khách 'mã + tên' (Quang Ích): mọi chứng từ ghi '<mã> <tên>' đúng một lần, kể cả khi tên đã có mã ở đầu."""
    assert app.strip_leading_code("2V01PRK000013 2V01PRK000013 Ống giấy trắng 77 x 3 x 1120 mm", "2V01PRK000013") == "Ống giấy trắng 77 x 3 x 1120 mm"
    assert app.strip_leading_code("2v01prk000013Ống giấy", "2V01PRK000013") == "Ống giấy"
    prof = {"name": "CÔNG TY TNHH CÔNG NGHIỆP BAO BÌ QUANG ÍCH VIỆT NAM", "custom": True}
    expect = "2V01PRK000013 Ống giấy trắng 77 x 3 x 1120 mm"
    for name in ("Ống giấy trắng 77 x 3 x 1120 mm", "2V01PRK000013 Ống giấy trắng 77 x 3 x 1120 mm", "2V01PRK000013\n2V01PRK000013 Ống giấy trắng 77 x 3 x 1120 mm"):
        it = {"ma_sp": "2V01PRK000013", "ten_sp": name, "ten_hq": ""}
        assert app.with_code(prof, it, name) == expect and app.invoice_item_name(prof, it) == expect
    other = {"name": "CÔNG TY KHÁC", "custom": True}
    assert app.invoice_item_name(other, {"ma_sp": "A1", "ten_sp": "A1 Ống", "ten_hq": ""}) == "A1\nỐng"


def test_invoice_weights_round_up_to_two_decimals_gross_is_net_plus_tare():
    """Trọng lượng tịnh tối đa 2 số lẻ làm tròn LÊN (.346 -> .35); cả bì = tịnh + bì (1 + .35 = 1.35); dòng tổng cộng các dòng đã làm tròn."""
    assert app.round_up(0.346) == 0.35 and app.round_up(804.52) == 804.52 and app.round_up(13.545) == 13.55 and app.round_up(2.0) == 2.0
    assert app.lot_gross(0.35, "1") == 1.35
    lines = [{"qty": 1000, "kg": 0.346}, {"qty": 3, "kg": 0.1234}]
    app.lot_recalc(lines, "tesa", "1")
    assert [(x["net"], x["gross"]) for x in lines] == [(346.0, 347.0), (0.38, 1.38)]  # 3 x 0.1234 = 0.3702 -> 0.38
    assert round(sum(x["net"] for x in lines), 2) == 346.38  # tổng = cộng các dòng, không làm tròn lên thêm


def test_deli_two_factories_share_one_item_catalog(store):
    """Deli Hải Dương và Deli Bắc Ninh dùng chung danh mục mã hàng; thêm mã ở nhà nào thì nhà kia cũng có."""
    base = {"unit": "chiếc", "mst": "0100000040", "addr": "HD"}
    store.save_learned_customer("delihd", dict(base, name="CÔNG TY TNHH DELI HẢI DƯƠNG", label="Deli Hải Dương"), [{"name": "Ống A", "code": "340025128", "price": 1, "div": 5, "kg": 0.78}])
    store.save_learned_customer("delibn", dict(base, name="CÔNG TY TNHH DELI BẮC NINH", label="Deli Bắc Ninh"), [{"name": "Ống B", "code": "340025472", "price": 2, "div": 20, "kg": 0.378}])
    assert {x["code"] for x in store.items_for_customer("delihd")} == {"340025128", "340025472"}
    assert store.items_for_customer("delibn") is store.items_for_customer("delihd")
    store.save_learned_customer("delibn", dict(base, name="CÔNG TY TNHH DELI BẮC NINH", label="Deli Bắc Ninh"), [{"name": "Ống C", "code": "340015528", "price": 3, "div": 5, "kg": 0.78}])
    assert "340015528" in {x["code"] for x in store.items_for_customer("delihd")}
    reloaded = app.DedicatedDataStore(base_dir=store.base_dir)
    assert {x["code"] for x in reloaded.items_for_customer("delibn")} == {"340025128", "340025472", "340015528"}
    # khách khác không bị gộp; khách chọn 'dùng chung với' khách khác thì chung
    store.save_learned_customer("riengx", dict(base, name="CÔNG TY KHÁC X", label="X"), [{"name": "Ống Z", "code": "Z1", "price": 1}])
    assert "Z1" not in {x["code"] for x in store.items_for_customer("delihd")}
    store.save_learned_customer("riengy", dict(base, name="CÔNG TY KHÁC Y", label="Y", shareItems="riengx"), [{"name": "Ống W", "code": "W1", "price": 1}])
    assert {x["code"] for x in store.items_for_customer("riengx")} == {"Z1", "W1"} == {x["code"] for x in store.items_for_customer("riengy")}


def test_able_bundle_has_dccn_in_the_customers_own_template(store):
    """Able có Bảng đối chiếu công nợ đúng mẫu khách đưa: các dòng hàng nhân theo lô, tổng bằng SUM, tổng bằng chữ, ký tên khách; không sinh 16.000 cột."""
    store.save_learned_customer("able2", {"name": "CÔNG TY TNHH BAO BÌ ĐÓNG GÓI ABLE", "label": "Able2", "mst": "0202226426", "addr": "Khu A1 Lô 1", "unit": "chiếc"},
                                [{"name": "Thùng 38*5*460 250g", "code": "A1", "price": 10, "div": 5, "kg": 0.1}])
    items = [{"stt": i + 1, "po": f"0000{3872 + i}", "ma_sp": "A1", "ten_sp": f"Ống giấy 38*5*{460 + i} 250g", "unit": "chiếc", "qty": 1000, "price": 1500, "amount": 1500000,
              "div": 5, "kg": 0.1, "kien": 2, "net": 1, "gross": 2, "tare": 1, "read": "ok"} for i in range(15)]
    rec = app.lot_build_record(store, {"customer": "able2", "po": "A", "pxk": "1", "doc_date": "2026-11-11"}, items)
    assert "DCCN" in app.lot_bundle_modes(rec)
    ws = openpyxl.load_workbook(app.lot_export(store, rec, "DCCN")["path"]).active
    assert "ĐỐI CHIẾU CÔNG NỢ" in ws["B1"].value and ws["K1"].value is None and len(ws.column_dimensions) < 40
    assert [ws[f"B{r}"].value for r in (12, 26)] == [1, 15] and ws["D26"].value == "000038 86".replace(" ", "") and ws["I26"].value == 1000
    tot = next(r for r in range(27, 32) if str(ws[f"B{r}"].value).startswith("Tổng :"))
    assert ws[f"K{tot}"].value == "=SUM(K12:K26)" and "Tổng tiền bằng chữ" in str(ws[f"B{tot + 3}"].value) and "hai mươi hai" in str(ws[f"B{tot + 3}"].value).lower()
    assert any(str(c.value or "").upper() == "CÔNG TY TNHH BAO BÌ ĐÓNG GÓI ABLE" for row in ws.iter_rows(min_row=tot) for c in row)


def test_able_invoice_name_does_not_repeat_spec_code(store):
    """Able: mã hàng (38*5*315*150g) chỉ là quy cách của tên; Invoice chỉ ghi tên 'Ống giấy phi 38 x 5 x 315mm x150g in', không ghi mã lần nữa."""
    name = "Ống giấy phi 38 x 5 x 315mm x150g in"
    store.save_learned_customer("able3", {"name": "CÔNG TY TNHH BAO BÌ ĐÓNG GÓI ABLE", "label": "Able3", "mst": "0202226426", "addr": "Khu A1 Lô 1", "unit": "Chiếc"},
                                [{"name": name, "code": "38*5*315*150g", "price": 2807, "div": 84, "kg": 0.15}])
    items = [{"stt": 1, "po": "00003038", "ma_sp": "38*5*315*150g", "ten_sp": name, "unit": "Chiếc", "qty": 2592, "price": 2807, "amount": 7275744,
              "div": 84, "kg": 0.15, "kien": 31, "net": 388.8, "gross": 389.8, "tare": 1, "read": "ok"}]
    rec = app.lot_build_record(store, {"customer": "able3", "po": "A", "pxk": "1", "doc_date": "2026-11-17"}, items)
    assert app.invoice_item_name(app.PROFILES["able3"], items[0]) == name
    wb = openpyxl.load_workbook(app.lot_export(store, rec, "ALL")["path"])
    cells = [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str) and "315" in c.value]
    assert cells and not [v for v in cells if "38*5*315*150g" in v]
    # khách có mã hàng riêng thật (không phải quy cách) vẫn ghi mã trước tên
    assert app.invoice_item_name({"custom": True}, {"ma_sp": "3609100670001", "ten_sp": "Ống 38x5x315"}) == "3609100670001\nỐng 38x5x315"


def test_able_dccn_is_a_monthly_statement_of_all_lots(store):
    """Able: Bảng đối chiếu công nợ là bảng của cả tháng (như file khách: lô 06/10 PO 00003872 + lô 20/10 PO 00004249, ngày bảng 31/10):
    gộp mọi lô Able đã lưu cùng tháng với lô đang làm, mỗi dòng ghi ngày giao và PO của lô đó, tổng bằng chữ là tổng cả tháng."""
    store.save_learned_customer("able4", {"name": "CÔNG TY TNHH BAO BÌ ĐÓNG GÓI ABLE", "label": "Able4", "mst": "0202226426", "addr": "Khu A1 Lô 1", "unit": "chiếc"},
                                [{"name": "Ống giấy phi 38 x 5 x 315mm x150g in", "code": "38*5*315*150g", "price": 2807, "div": 84, "kg": 0.15}])

    def lot(po, day, rows):
        items = [{"stt": i + 1, "po": po, "ma_sp": "", "ten_sp": n, "unit": "chiếc", "qty": q, "price": p, "amount": q * p,
                  "div": 1, "kg": 0.1, "kien": 1, "net": 1, "gross": 2, "tare": 1, "read": "ok"} for i, (n, q, p) in enumerate(rows)]
        return app.lot_build_record(store, {"customer": "able4", "po": po, "pxk": "1", "doc_date": f"2026-10-{day:02d}"}, items)

    first = lot("00003872", 6, [("Ống giấy phi 38 x 5 x 315mm x150g in", 4320, 2807), ("Ống giấy phi 38 x 5 x 315mm x170g in", 4320, 3181)])
    store.records.append(first)
    store.records.append(dict(lot("00001111", 2, [("Ống khác", 1, 1)]), customer="khac"))  # khách khác: không lấy
    store.records.append(lot("00000999", 3, [("Ống tháng trước", 1, 1)]) | {"docDate": "2026-09-30"})  # tháng khác: không lấy
    second = lot("00004249", 20, [("Ống giấy phi 38 x 5 x 467mm x280g in", 3120, 5239)])
    ws = openpyxl.load_workbook(app.lot_export(store, second, "DCCN")["path"]).active
    assert ws["B2"].value == "Ngày日31 tháng月10 năm年 2026"
    got = [(ws[f"C{r}"].value.date().isoformat(), ws[f"D{r}"].value, ws[f"F{r}"].value, ws[f"I{r}"].value, ws[f"J{r}"].value) for r in (12, 13, 14)]
    assert got == [("2026-10-06", "00003872", "Ống giấy phi 38 x 5 x 315mm x150g in", 4320, 2807),
                   ("2026-10-06", "00003872", "Ống giấy phi 38 x 5 x 315mm x170g in", 4320, 3181),
                   ("2026-10-20", "00004249", "Ống giấy phi 38 x 5 x 467mm x280g in", 3120, 5239)]
    tot = next(r for r in range(14, 30) if str(ws[f"B{r}"].value).startswith("Tổng :"))
    assert tot == 15 and ws[f"K{tot}"].value == "=SUM(K12:K14)"
    total = 4320 * 2807 + 4320 * 3181 + 3120 * 5239
    assert app.num_to_vn_words(total) in str(ws[f"B{tot + 3}"].value)


def test_cap_nhat_ma_sets_unit_kien_kg_by_code_and_adds_missing(store):
    """File dữ liệu chuẩn Quang Ích: theo MÃ HÀNG ghi đè ĐVT, SL/kiện, kg/chiếc (giữ tên, đơn giá); mã chưa có thì thêm; ĐVT mặc định của khách đổi theo file."""
    store.save_learned_customer("quangich", dict(QI), [dict(x) for x in ITEMS])
    data = {"version": "hongthien-hoc-v1", "cap_nhat_ma": {"khach": "Quang Ích", "don_vi": "Chiếc", "bi": 1, "ma": {
        "2V01PRB000002": {"name": "Tên khác", "unit": "Chiếc", "div": 250, "kg": 0.7, "price": 1},
        "2V1004P000001": {"name": "Thanh nẹp góc giấy carton chữ V 50 x 50 x 5 x 1000 mm", "unit": "Chiếc", "div": 20, "kg": 0.03, "price": 5800}}}}
    res = store.import_learned(data)
    assert (res["ma_sua"], res["ma_them"]) == (1, 1)
    items = {it["code"]: it for it in store.custom_items["quangich"]}
    old = items["2V01PRB000002"]
    assert (old["name"], old["price"], old["unit"], old["div"], old["kg"]) == (ITEMS[0]["name"], 12800, "Chiếc", 250, 0.7)
    new = items["2V1004P000001"]
    assert (new["unit"], new["div"], new["kg"], new["price"]) == ("Chiếc", 20, 0.03, 5800)
    assert app.PROFILES["quangich"]["unit"] == "Chiếc" and store.get_item_norm(ITEMS[0]["name"])["div"] == 250
    assert app.lot_defaults("quangich")["tare"] == "1.0"  # cả bì = tịnh + 1 kg mỗi dòng
    lines = [{"qty": 1000, "div": 250, "kg": 0.696}]
    app.lot_recalc(lines, "quangich", app.lot_defaults("quangich")["tare"])
    assert (lines[0]["kien"], lines[0]["net"], lines[0]["gross"]) == (4, 696, 697)
    with pytest.raises(ValueError, match="chưa có khách"):
        store.import_learned({"cap_nhat_ma": {"khach": "Khong co", "ma": {}}})



def test_items_step_erp_button_shows_erp_columns_without_changing_invoice_numbers(qapp, store):
    """Bước kiểm tra dòng: cột ERP ẩn mặc định; bấm "Hiện dữ liệu ERP" thì hiện mã/tên/kg ERP để đối chiếu, số khai vẫn theo invoice."""
    from ui_qt.pages_lot import C_ERP, COLS, ItemsStep
    from ui_qt.state import Lot
    store.save_learned_customer("arzn", {"name": "CÔNG TY TNHH ARIZON N", "label": "ArzN", "mst": "0100000033", "addr": "HY", "unit": "Chiếc"},
                                [{"name": "Ống giấy 76x5x67", "code": "3609100670009", "price": 10, "div": 200, "kg": 0.067}])
    store._dt_upsert("ArzN", "ống 76x5x67, T.nâu", ma_erp="FG10496-010-00009", kg=0.07, kg_nguon="erp", exact=True, ma_kh="3609100670009")
    lot = Lot(app, store)
    lot.select_customer("arzn")
    lot.items = [{"po": "P", "ma_sp": "3609100670009", "ten_sp": "Ống giấy 76x5x67", "hs": "", "unit": "Chiếc", "qty": 1000, "price": 10, "div": 200, "kg": 0.067}]
    lot.recalc()
    page = ItemsStep(lot)
    page.refresh()
    assert all(page.table.isColumnHidden(c) for c in range(C_ERP, len(COLS)))
    page.erp_btn.click()
    assert not any(page.table.isColumnHidden(c) for c in range(C_ERP, len(COLS))) and "Ẩn" in page.erp_btn.text()
    assert page.table.item(0, C_ERP).text() == "FG10496-010-00009" and page.table.item(0, len(COLS) - 1).text() == "0.07"
    assert "invoice" in page.table.item(0, len(COLS) - 1).toolTip()
    assert page.table.item(0, 10).text() == "0.067" and lot.items[0]["kg"] == 0.067
    page.erp_btn.click()
    assert page.table.isColumnHidden(C_ERP)
    page.close()

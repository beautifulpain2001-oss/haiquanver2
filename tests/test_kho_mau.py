"""Kho mẫu chung: mẫu Word/Excel dùng lại giữa các khách, đặt tên LOẠI_Khách_số; mượn mẫu khi tạo khách mới; xem mẫu. Dữ liệu giả."""

import io
import os
import zipfile

import openpyxl
import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {"name": "CÔNG TY TNHH KHO MẪU THỬ", "label": "KhoThu", "mst": "0100000088", "addr": "Lô Z, KCN Thử, Hải Phòng", "unit": "chiếc", "tare": 1.0, "payDays": 30}
ITEMS = [{"code": "A1", "name": "Ống lõi giấy phi 50 x 55 x 40mm (A1)", "unit": "chiếc", "price": 1000, "div": 50, "kg": 0.03}]


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def rec(store):
    store.save_learned_customer("khothu", dict(FAKE), [dict(x) for x in ITEMS])
    items = [{"stt": 1, "po": "P1", "ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 21212, "price": 1060, "amount": 22484720, "div": 50, "kg": 0.04, "kien": 425, "net": 848.48, "gross": 849.48, "hs": "48229090"},
             {"stt": 2, "po": "P1", "ma_sp": "A2", "ten_sp": "Ống B", "unit": "chiếc", "qty": 100, "price": 500, "amount": 50000, "div": 50, "kg": 0.1, "kien": 2, "net": 10, "gross": 11, "hs": "48229090"}]
    return app.lot_build_record(store, {"customer": "khothu", "doc_date": "2026-11-05", "po": "P1", "po_date": "01/11/2026", "pxk": "00000321", "hd": "00001", "tk": "3000"}, items)


def test_kho_is_seeded_once_and_names_follow_convention(store):
    names = [(m["file"], m["loai"], m["khach"], m["so"], m["ext"]) for m in store.kho_list()]
    assert ("PLX_Arizon_01.xlsx", "PLX", "Arizon", "01", "xlsx") in names and ("PLX_Sunlu_01.docx", "PLX", "Sunlu", "01", "docx") in names
    assert all(not m["unknown"] and m["tokens"] for m in store.kho_list())
    store.kho_remove("PLX_Sunlu_01.docx")
    assert "PLX_Sunlu_01.docx" not in [m["file"] for m in store.kho_list()]  # xóa rồi không bị gieo lại


def test_kho_add_numbers_up_and_validates(store, tmp_path):
    src = tmp_path / "x.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "{{so_po}}"
    wb.save(src)
    assert store.kho_add(str(src), "plx", "Arizon")[0] == "PLX_Arizon_02.xlsx"
    assert store.kho_add(str(src), "BBGH", "Sun lu")[0] == "BBGH_Sunlu_01.xlsx"
    empty = tmp_path / "e.xlsx"
    openpyxl.Workbook().save(empty)
    with pytest.raises(ValueError, match="ô thay thế"):
        store.kho_add(str(empty), "PLX", "Arizon")
    with pytest.raises(ValueError, match="Word"):
        store.kho_add(str(tmp_path / "y.txt"), "PLX", "Arizon")


def test_borrow_arizon_excel_and_sunlu_word_then_export(store, rec):
    store.kho_list()
    store.kho_borrow("khothu", "PLX_Arizon_01.xlsx")
    store.kho_borrow("khothu", "PLX_Sunlu_01.docx")
    assert store.custom_forms("khothu") == ["PLX_Arizon_01.xlsx", "PLX_Sunlu_01.docx"]
    res = app.lot_export(store, rec, "R:PLX_Arizon_01.xlsx")
    ws = openpyxl.load_workbook(res["path"]).active
    assert ws["A4"].value == f"Tên nhà sản xuất: {app.HT_NAME}" and ws["C6"].value == "21.312" and "00001" in ws["A8"].value
    assert [ws[f"C{r}"].value for r in (11, 12)] == ["Ống A", "Ống B"] and [ws[f"D{r}"].value for r in (11, 12)] == [21212, 100]  # dòng hàng nhân lên, số thật
    assert "Khai tại văn bản này" in ws["A14"].value  # đoạn cam kết bị đẩy xuống đúng chỗ
    res = app.lot_export(store, rec, "R:PLX_Sunlu_01.docx")
    texts = mau_rieng.preview("docx", open(res["path"], "rb").read())["text"].split("\n")
    assert texts[6] == "Số lượng: 21.312 PCS , Ống A; Ống B , trị giá DAP 22.534.720  VND"
    assert "Hóa Đơn Số: 00001 ngày 05/11/2026" in texts[7] and texts[12].strip() == "Bắc Ninh, ngày 05 tháng 11  năm 2026"
    # đưa mẫu riêng của khách vào kho chung với tên theo khách
    name, _k, _u = store.kho_publish("khothu", "PLX_Arizon_01.xlsx", "PLX")
    assert name == "PLX_KhoThu_01.xlsx"


def test_preview_shapes(store):
    store.kho_list()
    word = mau_rieng.preview("docx", store.kho_read("PLX_Sunlu_01.docx"))
    assert word["kind"] == "text" and "Phụ lục X" in word["text"] and "{{tong_sl}}" in word["text"]
    grid = mau_rieng.preview("xlsx", store.kho_read("PLX_Arizon_01.xlsx"))
    assert grid["kind"] == "grid" and grid["rows"][0][0] == "PHỤ LỤC X" and grid["rows"][10][:4] == ["{{stt}}", "{{ma}}", "{{ten}}", "{{sl}}"]


def test_kho_page_image_left_list_right_and_edit_tool(qapp, store):
    """Tab Kho mẫu: hình bên trái (vừa khung), danh sách có thanh cuộn bên phải; công cụ sửa mẫu đổi chữ thành ô, hoàn tác, lưu vào kho."""
    from PySide6.QtCore import Qt
    from ui_qt.pages_kho import EditTemplateDialog, MauPage
    page = MauPage(app, store)
    page.resize(1200, 800)
    page.show()
    page.refresh()
    names = [it["file"] for it in page.items]
    assert {"PLX_Arizon_01.xlsx", "PLX_Sunlu_01.docx"} <= set(names) and not hasattr(page, "use_btn")
    assert page.listw.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn and page.listw.x() > page.view.x()  # danh sách bên phải, hình bên trái
    assert not page.listw.item(0).icon().isNull()
    page.listw.setCurrentRow(names.index("PLX_Sunlu_01.docx"))
    assert page.view.pages and "PLX_Sunlu_01" in page.title.text() and page.view.badge.text() == f"1 / {len(page.view.pages)}"  # trang A4, ô báo số trang
    w0 = page.view.labels[0].pixmap().width()
    page.view.set_zoom(2.0)
    assert page.view.labels[0].pixmap().width() > w0 * 1.8  # zoom
    page.view.fit_width()
    assert page.view.labels[0].pixmap().width() == w0
    page.listw.setCurrentRow(names.index("PLX_Arizon_01.xlsx"))
    assert page.view.pages
    dlg = EditTemplateDialog(app, store, "PLX_Sunlu_01.docx")
    dlg.find.setText("Bắc Ninh")
    dlg.token.setCurrentIndex(dlg.token.findData("khach_ten"))
    dlg.apply()
    assert dlg.dirty and "Đã đổi 1 chỗ" in dlg.msg.text() and dlg.save_btn.isEnabled()
    dlg.undo()
    assert not dlg.dirty and not dlg.undo_btn.isEnabled()
    dlg.find.setText("không có chữ này")
    dlg.apply()
    assert "Không thấy chữ" in dlg.msg.text()
    dlg.find.setText("Bắc Ninh")
    dlg.apply()
    dlg.save()
    assert "{{khach_ten}}" in __import__("mau_rieng").preview("docx", store.kho_read("PLX_Sunlu_01.docx"))["text"]
    dlg.close()
    page.close()


def test_replace_text_tool_word_and_excel(store):
    word = mau_rieng.replace_text("docx", store.kho_read("PLX_Sunlu_01.docx") if store.kho_list() else b"", "PCS", "dvt")
    assert word[1] == 1 and "{{dvt}}" in mau_rieng.preview("docx", word[0])["text"]
    xl, n = mau_rieng.replace_text("xlsx", store.kho_read("PLX_Arizon_01.xlsx"), "VNĐ", "dvt")
    assert n == 1 and openpyxl.load_workbook(io.BytesIO(xl)).active["D7"].value == "{{dvt}}"
    with pytest.raises(ValueError):
        mau_rieng.replace_text("xlsx", xl, "", "dvt")


def test_new_customer_flow_three_files_then_pick_template(qapp, store, tmp_path):
    from ui_qt.dialogs import LearnCustomerDialog, LearnFilesDialog
    dlg = LearnFilesDialog()
    assert not dlg.go.isEnabled()
    dlg.set_path("invoice", "/x/iv.xlsx")
    dlg.set_path("hoadon", "/x/vat.xml")
    assert not dlg.go.isEnabled()
    dlg.set_path("pxk", "/x/pxk.xml")
    assert dlg.go.isEnabled() and dlg.file_list() == ["/x/iv.xlsx", "/x/vat.xml", "/x/pxk.xml"]
    dlg.close()
    draft = {"profile": {"name": "CÔNG TY MỚI ABC", "mst": "0100000055", "addr": "Hải Phòng"}, "items": [{"code": "Z1", "name": "Hàng Z", "unit": "chiếc", "price": 10, "div": 5, "kg": 0.1}],
             "errors": [], "sample_po": "", "tare": 0.0, "po_text": ""}
    d = LearnCustomerDialog(app, store, [], draft=draft)
    d.edits["key"].setText("abcmoi")
    d.edits["label"].setText("AbcMoi")
    d.kho.flow.set_current([it["file"] for it in d.kho.items].index("PLX_Arizon_01.xlsx"), animate=False)
    assert "Chọn mẫu này" in d.kho.pick_btn.text()
    d.kho.toggle_current()
    assert d.kho.pick_btn.text().startswith("✖") and "PLX_Arizon_01" in d.kho.chosen_label.text()
    d.save()
    assert d.key == "abcmoi" and store.custom_forms("abcmoi") == ["PLX_Arizon_01.xlsx"]
    assert app.lot_bundle_modes({"customer": "abcmoi"}) == ["PKL", "VAT", "PXK", "R:PLX_Arizon_01.xlsx"]
    d.close()


def test_coverflow_navigation_and_hit_test(qapp, store):
    from PySide6.QtCore import QPointF
    from ui_qt.pages_kho import CoverFlow, kho_cards
    flow = CoverFlow()
    flow.resize(900, 300)
    flow.set_cards(kho_cards(store.kho_list()) + [{"title": "X", "code": "KHAC", "color": "#64748B", "lines": [], "foot": ""}] * 2, 1)
    seen = []
    flow.current_changed.connect(seen.append)
    flow.step(1)
    flow.step(-1)
    flow.step(-1)
    flow.step(-1)  # quay vòng về cuối
    assert seen == [2, 1, 0, 3]
    flow.set_current(1, animate=False)
    assert flow.card_at(QPointF(450, 140)) == 1 and flow.card_at(QPointF(5, 5)) is None
    right = flow._card_rect(1).center()
    flow.mousePressEvent(type("E", (), {"position": lambda self, p=right: p})())  # bấm thẻ bên phải: chuyển sang thẻ đó
    assert flow.index == 2
    assert not flow.grab().isNull()  # vẽ được không lỗi
    flow.close()


def make_filled_workbook(path):
    """Chứng từ ĐÃ ĐIỀN SẴN (dữ liệu giả) có cấu trúc giống file thật: 3 sheet, bảng hàng có dòng mẫu thừa, ô tổng cộng, số PO, ngày, tên công ty."""
    wb = openpyxl.Workbook()
    po = wb.active
    po.title = "Đơn đặt hàng"
    po["A1"] = "CÔNG TY TNHH KHO MẪU THỬ"
    po["D3"] = "Ngày 03 tháng  06 năm 2026"
    po["A5"] = "Số:YNCGDD2606030001"
    po["A6"] = f"Kính gửi: {app.HT_NAME}"
    for col, h in zip("ABCDEF", ("STT", "TÊN SẢN PHẨM", "ĐVT", "SỐ LƯỢNG", "ĐƠN GIÁ", "THÀNH TIỀN")):
        po[f"{col}9"] = h
    po["A10"], po["B10"], po["C10"], po["D10"], po["E10"], po["F10"] = 1, "Ống lõi giấy phi 50x55x40mm", "chiếc", 32000, 1060, "=D10*E10"
    for r in range(11, 16):
        po[f"C{r}"] = "ống"
    po["B16"], po["D16"], po["F16"] = "Tổng cộng", "=SUM(D10:D10)", "=SUM(F10:F10)"
    po["A17"] = "Thời gian giao hàng: vào ngày 19/06/2026"
    po["A19"] = "Ghi chú cuối"
    po.merge_cells("A19:F19")
    bb = wb.create_sheet("BBGH")
    bb["A2"] = "Số:06/2026SL"
    bb["A13"], bb["B13"], bb["C13"], bb["E13"], bb["F13"], bb["G13"] = "Ngày hạch toán", "Số  hóa đơn", "Diễn giải", "Số lượng", "Đơn giá", "Số Tiền"
    bb["A15"], bb["B15"], bb["C15"], bb["E15"], bb["F15"], bb["G15"] = "19/06/2026", "00001558", "Ống A", 32000, 1060, "=E15*F15"
    for r in range(16, 20):
        bb[f"B{r}"] = "00002149"
    bb["A20"], bb["G20"] = "Cộng", "=SUM(G15:G19)"
    bb["A22"] = "Ký tên"
    wb.create_sheet("invoice")["A1"] = "Invoice dùng chung"
    wb.save(path)


def test_detect_proposes_changeable_spots_and_user_decides(tmp_path):
    import mau_detect
    src = tmp_path / "chung_tu.xlsx"
    make_filled_workbook(src)
    data = src.read_bytes()
    ctx = {"seller": {"name": app.HT_NAME, "addr": app.ADDR_HT, "mst": app.MST_HT}, "customer": {"name": "CÔNG TY TNHH KHO MẪU THỬ", "addr": "", "mst": ""}}
    c = {d["id"]: d for d in mau_detect.detect_xlsx(data, ctx, "Đơn đặt hàng")}
    assert c["Đơn đặt hàng!A5#0"]["token"] == "so_po" and c["Đơn đặt hàng!A5#0"]["value"] == "YNCGDD2606030001"
    assert [c[f"Đơn đặt hàng!{x}10"]["token"] for x in "ABCDEF"] == ["stt", "ten", "dvt", "sl", "gia", "thanh_tien"]
    assert c["Đơn đặt hàng!D16"]["token"] == "tong_sl" and c["Đơn đặt hàng!F16"]["token"] == "tong_tri_gia" and c["Đơn đặt hàng!drop"]["count"] == 5
    assert c["Đơn đặt hàng!A1#0"]["token"] == "khach_ten" and c["Đơn đặt hàng!A6#0"]["token"] == "ben_ban_ten"
    assert [c[f"Đơn đặt hàng!D3#{k}"]["token"] for k in range(3)] == ["dd", "mm", "yyyy"] and c["Đơn đặt hàng!A17#0"]["token"] == "ngay"
    bb = {d["id"]: d for d in mau_detect.detect_xlsx(data, ctx, "BBGH")}
    assert bb["BBGH!B15"]["token"] == "so_hd" and bb["BBGH!A15"]["token"] == "ngay" and bb["BBGH!drop"]["count"] == 4  # dòng trống dưới tiêu đề vẫn tìm đúng dòng hàng đầu
    assert [bb[f"BBGH!A2#{k}"]["token"] for k in range(2)] == ["mm", "yyyy"]
    # người dùng quyết định: chỉ chọn số PO và tên hàng, các chỗ khác giữ nguyên chữ
    out = mau_detect.apply_xlsx(data, {"Đơn đặt hàng!A5#0": "so_po", "Đơn đặt hàng!B10": "ten"}, "Đơn đặt hàng", ctx)
    wb = openpyxl.load_workbook(io.BytesIO(out))
    assert wb.sheetnames == ["Đơn đặt hàng"] and wb.active["A5"].value == "Số:{{so_po}}" and wb.active["B10"].value == "{{ten}}" and wb.active["D10"].value == 32000


def test_detect_full_convert_then_fill_with_lot_data(store, tmp_path):
    """Chấp nhận mọi gợi ý: bảng hàng nhân lên theo số mặt hàng, dòng mẫu thừa bị xóa, công thức bên dưới dời đúng chỗ."""
    import mau_detect
    src = tmp_path / "chung_tu.xlsx"
    make_filled_workbook(src)
    data = src.read_bytes()
    ctx = store.detect_context("")
    ch = {d["id"]: d["token"] for d in mau_detect.detect_xlsx(data, ctx, "Đơn đặt hàng") if d["token"]}
    tpl = mau_detect.apply_xlsx(data, ch, "Đơn đặt hàng", ctx)
    ws = openpyxl.load_workbook(io.BytesIO(tpl)).active
    assert ws["A10"].value == "{{stt}}" and ws["D11"].value == "{{tong_sl}}" and ws["A12"].value == "Thời gian giao hàng: vào ngày {{ngay}}" and ws.max_row < 20  # đã xóa 5 dòng thừa
    assert any(str(r) == "A14:F14" for r in ws.merged_cells.ranges)  # ô gộp phía dưới dời lên theo
    rec_items = [{"ma_sp": "A1", "ten_sp": "Ống A", "unit": "chiếc", "qty": 100, "price": 10, "amount": 1000}, {"ma_sp": "A2", "ten_sp": "Ống B", "unit": "chiếc", "qty": 50, "price": 20, "amount": 1000}]
    prof = {"name": "KHÁCH X", "addr": "ĐC", "mst": "0100000001"}
    consts = {"name": app.HT_NAME, "addr": app.ADDR_HT, "mst": app.MST_HT, "date": app._iso_to_date, "words": app.num_to_vn_words}
    rec = {"docDate": "2026-11-05", "poNumber": "PO-NEW", "items": rec_items}
    out, unknown = mau_rieng.fill_xlsx(tpl, mau_rieng.batch_values(rec, prof, consts), mau_rieng.item_values(rec))
    ws = openpyxl.load_workbook(io.BytesIO(out)).active
    assert unknown == [] and ws["A5"].value == "Số:PO-NEW" and [ws[f"B{r}"].value for r in (10, 11)] == ["Ống A", "Ống B"]
    assert ws["D12"].value == "150" and ws["A13"].value.endswith("05/11/2026")  # tổng cộng và dòng bên dưới dời xuống đúng chỗ khi thêm dòng hàng


def test_detect_dialog_adds_each_sheet_as_named_template(qapp, store, tmp_path):
    from PySide6.QtCore import Qt
    from ui_qt.pages_kho import DetectDialog
    src = tmp_path / "chung_tu.xlsx"
    make_filled_workbook(src)
    dlg = DetectDialog(None, store, str(src), "Sunlu")
    names = [pg["sheet"] for pg in dlg.pages]
    assert names == ["Đơn đặt hàng", "BBGH", "invoice"] and [pg["inc"].isChecked() for pg in dlg.pages] == [True, True, False]  # Invoice dùng chung: mặc định không nạp
    assert [pg["loai"].currentData() for pg in dlg.pages] == ["PO", "BBGH", "KHAC"]
    po = dlg.pages[0]
    assert po["table"].verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn and po["table"].rowCount() >= 12
    assert "3 mẫu" not in dlg.ok.text() and "2 mẫu" in dlg.ok.text()
    # người dùng bỏ tích một chỗ và đổi một chỗ sang ô khác
    ids = [d["id"] for d in po["cands"]]
    i_po = ids.index("Đơn đặt hàng!A5#0")
    po["table"].item(i_po, 0).setCheckState(Qt.Unchecked)
    i_ten = ids.index("Đơn đặt hàng!B10")
    po["combos"][i_ten].setCurrentIndex(po["combos"][i_ten].findData("ma_hang"))
    assert po["table"].item(i_ten, 0).checkState() == Qt.Checked
    dlg.accept()
    assert dlg.names == ["PO_Sunlu_01.xlsx", "BBGH_Sunlu_01.xlsx"]
    ws = openpyxl.load_workbook(io.BytesIO(store.kho_read("PO_Sunlu_01.xlsx"))).active
    assert ws["A5"].value == "Số:YNCGDD2606030001" and ws["B10"].value == "{{ma_hang}}" and ws["D10"].value == "{{sl}}"  # chỗ bỏ tích giữ nguyên chữ
    assert "BBGH_Sunlu_01.xlsx" in [m["file"] for m in store.kho_list()]
    dlg.close()


def test_detect_dialog_blocks_empty_template(qapp, store, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from ui_qt import pages_kho
    shown = []
    monkeypatch.setattr(pages_kho.widgets, "warn", lambda parent, title, text: shown.append(text))
    src = tmp_path / "chung_tu.xlsx"
    make_filled_workbook(src)
    dlg = pages_kho.DetectDialog(None, store, str(src), "Sunlu")
    for pg in dlg.pages:
        for i in range(pg["table"].rowCount()):
            pg["table"].item(i, 0).setCheckState(Qt.Unchecked)
    dlg.accept()
    assert dlg.names == [] and shown and "ô thay thế" in shown[0]
    dlg.close()


def test_detect_docx_candidates_and_apply():
    import kho_mau
    import mau_detect
    filled = mau_rieng.fill_docx(kho_mau.plx_sunlu_docx(), {"tong_sl": "20.000", "ten_hang": "ống A", "tong_tri_gia": "21.200.000", "so_tk": "308935585730", "ngay": "09/10/2026", "so_hd": "00003964",
                                                            "ben_ban_ten": app.HT_NAME, "dd": "09", "mm": "10", "yyyy": "2026", "hs": "48229090", "ben_ban_dia_chi": "Lô CN-15.1, KCN Thuận Thành II, Bắc Ninh"}, [])[0]
    ctx = {"seller": {"name": app.HT_NAME, "addr": app.ADDR_HT, "mst": app.MST_HT}, "customer": None}
    c = {d["value"]: d for d in mau_detect.detect_docx(filled, ctx)}
    assert c["308935585730"]["token"] == "so_tk" and c["00003964"]["token"] == "so_hd" and c["20.000"]["token"] == "tong_sl" and c["21.200.000"]["token"] == "tong_tri_gia"
    out = mau_detect.apply_docx(filled, {d["id"]: d["token"] for d in c.values() if d["token"] in ("so_tk", "tong_sl")}, ctx)
    text = mau_rieng.preview("docx", out)["text"]
    assert "{{so_tk}}" in text and "{{tong_sl}}" in text and "21.200.000" in text  # chỉ đổi chỗ đã chọn


def test_customers_page_search_note_and_make_lot(qapp, store):
    """Trang Khách hàng: ô tìm lọc dòng, lưu ý đặc thù hiện hộp vàng và nhắc ở bước xuất, nút Tạo bộ hồ sơ chuyển sang Làm chứng từ với khách đó."""
    from ui_qt import main_window as mw
    store.save_learned_customer("ghichu", {"name": "CÔNG TY GHI CHÚ", "label": "GhiChu", "mst": "0100000066", "note": "Ghi rõ Net/Gross", "extraDocs": "PLX"}, [{"name": "Hàng", "code": "A1", "price": 10, "div": 5, "kg": 0.1}])
    win = mw.MainWindow(app, store)
    pg = win.customers
    pg.refresh()
    pg.search.setText("ghichu")
    assert [r for r in range(pg.table.rowCount()) if not pg.table.isRowHidden(r)] == [pg.keys.index("ghichu")]
    pg.table.selectRow(pg.keys.index("ghichu"))
    assert pg.form.edits["note"].text() == "Ghi rõ Net/Gross" and pg.title.text() == "CÔNG TY GHI CHÚ"
    assert "PLX" in pg.forms_lay.itemAt(0).widget().text()
    pg.search.setText("")
    from ui_qt.state import Lot
    lot = Lot(app, store)
    lot.select_customer("ghichu")
    lot.items = [{"stt": 1, "po": "P", "ma_sp": "A1", "ten_sp": "Hàng", "unit": "chiếc", "qty": 10, "price": 10, "amount": 100, "div": 5, "kg": 0.1, "kien": 2, "net": 1, "gross": 2, "tare": 1}]
    lot.form["po"] = "P"
    assert lot.validate()[1][0] == "Lưu ý khách này: Ghi rõ Net/Gross"
    pg.make_btn.click()
    assert win.nav.currentRow() == 0 and win.lot.lot.customer == "ghichu"
    win.close()

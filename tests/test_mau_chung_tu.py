"""Chứng từ theo file mẫu của khách: nhân dòng hàng, dời hàng cuối, sửa công thức tổng (dữ liệu giả)."""
import openpyxl

import hongthien_desktop_app as app
import mau_chung_tu as mct


def fake_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "TIÊU ĐỀ"
    ws.merge_cells("A1:D1")
    ws["B2"] = "Số ĐĐH: X"
    ws.row_dimensions[3].height = 33
    for r in (4, 5):  # hai dòng hàng mẫu
        ws[f"A{r}"] = r - 3
        ws[f"C{r}"] = 10
        ws[f"D{r}"] = f"=C{r}*2"
        ws.merge_cells(f"A{r}:B{r}")
        ws[f"C{r}"].number_format = "#,##0"
    ws["C6"] = "=SUM(C4:C5)"
    ws["D6"] = "=SUM(D4:D5)"
    ws["A8"] = "=C6"
    ws["A9"] = "Chữ ký"
    ws.print_area = "A1:D9"
    return ws


def test_clone_sheet_expands_rows_and_fixes_formulas():
    out = openpyxl.Workbook()
    ws, pl = mct.clone_sheet(out, fake_template(), "Mau", [(4, 5, 5)])
    assert ws["A4"].value == 1 and ws["D8"].value == "=C8*2"  # 5 dòng hàng: 4..8
    assert ws["C9"].value == "=SUM(C4:C8)" and ws["D9"].value == "=SUM(D4:D8)"  # tổng dời xuống và mở rộng
    assert ws["A11"].value == "=C9" and ws["A12"].value == "Chữ ký"
    assert ws["C8"].number_format == "#,##0" and ws.row_dimensions[3].height == 33
    assert {"A1:D1", "A4:B4", "A8:B8"} <= {str(m) for m in ws.merged_cells.ranges}
    assert ws.print_area.endswith("$D$12") and pl.last[4] == 8


def test_clone_sheet_shrinks_to_one_row():
    out = openpyxl.Workbook()
    ws, _ = mct.clone_sheet(out, fake_template(), "Mau", [(4, 5, 1)])
    assert ws["C5"].value == "=SUM(C4:C4)" and ws["A7"].value == "=C5"


def test_autofit_wraps_long_text_and_raises_row_height():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 10
    ws["A1"] = "Lô đất số IN4.1.1 KCN Cẩm Điền - Lương Điền, Xã Cẩm Giàng, Thành phố Hải Phòng, Việt Nam."
    ws.merge_cells("A1:B1")
    ws["A3"] = "Người xuất khẩu rất dài nhưng bên phải còn ô trống nên không phải xuống dòng"
    ws["L9"] = "x"  # có nhiều cột trống bên phải A3
    ws["A5"] = 123456789.5
    ws["A5"].number_format = "#,##0.00"
    mct.autofit_workbook(wb)
    assert ws["A1"].alignment.wrap_text and ws.row_dimensions[1].height >= 4 * 11 * 1.33  # 3+ dòng hiện đủ
    assert not ws["A3"].alignment.wrap_text  # tràn sang ô trống bên phải thì giữ một dòng
    assert ws.column_dimensions["A"].width >= len("123,456,789.50")  # số quá rộng thì nới cột


def test_arizon_invoice_hides_b_and_j_and_shows_h(tmp_path):
    import openpyxl
    import hongthien_desktop_app as core
    import mau_chung_tu
    t = openpyxl.Workbook()
    ws = t.active
    ws.title = "9.2"
    for col in "ABCDEFGHIJKLMN":
        ws[f"{col}12"] = col
    ws.column_dimensions["H"].hidden = True
    ws.column_dimensions["B"].width = 6
    ws["A24"] = "x"
    ws.print_area = "A1:N24"
    path = tmp_path / "arz.xlsx"
    t.save(path)
    wb = openpyxl.Workbook()
    rec = {"docDate": "2026-11-05", "pxkNo": "1", "items": [{"ma_sp": "A", "ten_sp": "x", "po": "P", "unit": "chiếc", "qty": 10, "kg": 0.1, "div": 5, "price": 3}]}
    out = mau_chung_tu.fill_pkl_arizon(core, wb, rec, {"name": "ARZ", "addr": "HY", "unit": "chiếc"}, mau_chung_tu.load_template(str(path)), "Inv")
    d = out.column_dimensions
    assert d["B"].hidden and d["J"].hidden and not d["H"].hidden


def _pack_template():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "CHI TIẾT ĐÓNG GÓI"
    ws["D2"], ws["F2"] = "PXKKVCNB : 00000111", "Ngày: 01/01/2026"
    ws["A3"], ws["D3"], ws["F3"] = "TÊN CŨ", "Số ĐĐH: POSCU0000001", "Ngày: 01/01/2026"
    ws["D4"], ws["F4"] = "Số ĐĐH: POSCU0000002", "Ngày: 02/01/2026"
    ws["A6"], ws["A7"] = "Địa chỉ cũ", "Tel cũ"
    ws["A17"] = "STT"
    for r in range(18, 30):
        ws[f"A{r}"] = r - 17
    ws["A30"], ws["D30"] = "TOTAL:", "=SUM(D18:D29)"
    ws["A32"], ws["B32"], ws["C32"] = "Tổng", "=ROUNDUP(D30/20,0)", "kiện"
    return ws


def test_best_pack_template_writes_one_po_row_without_old_po():
    """Mẫu khách có 2 dòng Số ĐĐH: lô 1 PO không còn dòng PO cũ của mẫu, lô 2 PO nối 'PO1 + PO2' trên một dòng."""
    prof = {"name": "KHÁCH THỬ", "addr": "Xã Thử, Thành phố Hải Phòng", "customs": {"incoterm": "DAP"}}
    items = [{"ten_sp": "Ống A", "qty": 100, "kg": 0.5, "tare": 1, "div": 20, "po": "POS1"},
             {"ten_sp": "Ống B", "qty": 50, "kg": 0.5, "tare": 1, "div": 20, "po": "POS2"}]
    for its, po_txt, dates in ((items[:1], "Số ĐĐH: POS1", "Ngày: 03/11/2026"), (items, "Số ĐĐH: POS1 + POS2", "Ngày: 03/11/2026 + 04/11/2026")):
        rec = {"items": its, "docDate": "2026-11-18", "pxkNo": "00000340", "poDates": {"POS1": "03/11/2026", "POS2": "04/11/2026"}}
        wb = openpyxl.Workbook()
        ws = mct.fill_pack(app, wb, rec, prof, _pack_template(), "DG")
        vals = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
        assert ws["D3"].value == po_txt and ws["F3"].value.strip() == dates
        assert sum(v.startswith("Số ĐĐH") for v in vals) == 1 and not any("POSCU" in v for v in vals)
        assert ws["A5"].value == app.ADDR_HT.rstrip(".")  # hàng PO thứ 2 (trống bên trái) đã bỏ: địa chỉ lên ngay dưới


def test_best_dccn_template_invoice_number_follows_first_row():
    """ĐCCN theo file mẫu khách: ô số hóa đơn dòng đầu ghi số (chữ), các dòng dưới là công thức theo ô đầu."""
    tws = openpyxl.Workbook().active
    for r in range(1, 32):
        tws[f"A{r}"] = None
    tws["A1"] = "对 账 单"
    tws["A31"] = "hết"
    prof = {"name": "KHÁCH THỬ"}
    items = [{"ten_sp": f"Ống {i}", "qty": 10, "price": 1000, "po": "POS1"} for i in range(3)]
    rec = {"items": items, "docDate": "2026-11-18", "hdNo": "00004938", "payDays": 60}
    ws = mct.fill_dccn(app, openpyxl.Workbook(), rec, prof, tws, "DCCN")
    assert (ws["B9"].value, ws["B9"].number_format) == ("00004938", "@")
    assert [ws[f"B{r}"].value for r in (10, 11)] == ['=IF($B$9="","",$B$9)'] * 2

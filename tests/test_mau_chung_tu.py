"""Chứng từ theo file mẫu của khách: nhân dòng hàng, dời hàng cuối, sửa công thức tổng (dữ liệu giả)."""
import openpyxl

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

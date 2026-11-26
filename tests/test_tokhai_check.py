"""Bước ⑤ Kiểm tra tờ khai: đọc tờ khai nháp ECUS và đối chiếu với Invoice / Hóa đơn VAT / PXK của lô.

Mẫu thật: tests/fixtures/tokhai_nhap_shirai_mau.xlsx là sheet ToKhai của file Check_hang_XML_vs_ERP.xlsm Huy gửi,
tokhai_shirai_invoice.json là sheet Invoice cùng file. Macro ModToKhai trên bộ này cho: 33 dòng khớp, 3 dòng lệch TL tịnh
(TK1-<31>, <34>, <36>), phần đầu sai Gross, PO, số hóa đơn, ghi chú PXK.
"""

import csv
import json
from pathlib import Path

import openpyxl
import pytest

import hongthien_desktop_app as app
import tokhai_check as tc

FIX = Path(__file__).parent / "fixtures"
TK_FILE = FIX / "tokhai_nhap_shirai_mau.xlsx"


def shirai_rec(**kw):
    items = json.loads((FIX / "tokhai_shirai_invoice.json").read_text(encoding="utf-8"))["items"]
    rec = {"customer": "shirai", "docDate": "2026-11-20", "pxkNo": "00000345", "poNumber": "202639HT", "scheduleKey": "20.11",
           "items": items}
    rec.update(kw)
    return rec


def tk_rows():
    return tc.rows_from_file(str(TK_FILE), app)


def run(rec, rows=None, tol=0.0):
    wb, res = tc.build_workbook(app, rec, [("tk.xlsx", rows if rows is not None else tk_rows())], tol)
    return wb, res


def find_row(rows, needle):
    """Chỉ số hàng (0-based) có ô cột C bằng `needle`."""
    return next(i for i, r in enumerate(rows) if len(r) > 2 and tc.cell_text(r[2]) == needle)


def set_cell(rows, r, c, v):
    row = list(rows[r]) + [None] * max(0, c + 1 - len(rows[r]))
    row[c] = v
    rows[r] = tuple(row)


# ---------------------------------------------------------------- hàm nhỏ
def test_parse_vn_num():
    assert tc.parse_vn_num("6.331.208") == 6331208
    assert tc.parse_vn_num("106,08") == pytest.approx(106.08)
    assert tc.parse_vn_num("1.234,5") == pytest.approx(1234.5)
    assert tc.parse_vn_num("-") == 0
    assert tc.parse_vn_num("") == 0
    assert tc.parse_vn_num(12.48) == pytest.approx(12.48)  # ô đã là số: giữ nguyên, không bỏ dấu chấm


def test_clean_desc_key_po():
    d = "Thùng Carton Box NTI-LS0019060SDHWH(W998xD171xH371) Po.No 202639HT . Hàng mới 100%"
    assert tc.clean_tk_desc(d) == "Thùng Carton Box NTI-LS0019060SDHWH(W998xD171xH371)"
    assert tc.extract_po(d) == "202639HT"
    assert tc.norm_tk_key("Giấy tổ ong  Tấm  lót") == "TẤM LÓT"
    assert tc.clean_po("Po No 202641HT") == "202641HT"
    assert tc.extract_pxk("Phuong thuc thanh toan: TT .PXKKVCNB số: 00000345. Ky hieu") == "00000345"


def test_levenshtein_diff():
    assert tc.levenshtein("AF_1", "AF_1A") == 1
    assert tc.describe_name_diff("Pad (AF_1:W290)", "Pad (AF_1A:W290)") == '":" ≠ "A"'  # như macro: phần trống thì lấy 1 ký tự
    p, e1, e2 = tc.diff_span("Pad AF_1:W290", "Pad AF_2:W290")
    assert ("Pad AF_1:W290"[p:e1], "Pad AF_2:W290"[p:e2]) == ("1", "2")


# ---------------------------------------------------------------- đọc tờ khai
def test_read_header_and_items():
    tk = tc.read_tokhai([("tk", tk_rows())])
    h = tk["headers"][0]
    assert h["pk"] == 187 and h["gross"] == pytest.approx(664.11)
    assert h["amount"] == 38321354 and h["taxAmount"] == 38321354
    assert h["lines"] == 37 and h["invNo"] == "00000345"
    assert h["depDate"] == "20/11/2026" and h["invDate"] == "20/11/2026"
    assert "202641HT" in h["po"]
    assert len(tk["items"]) == 36
    first = tk["items"][0]
    assert first["tag"] == "TK1-<01>" and first["qty"] == 104 and first["net"] == pytest.approx(106.08)
    assert first["price"] == 60877 and first["amount"] == 6331208 and first["hs"] == "48191000"
    assert first["u1"] == "PCE" and first["u2"] == "KGM" and first["po"] == "202639HT" and first["origOK"]


def test_csv_reads_same_as_xlsx(tmp_path):
    p = tmp_path / "tk.csv"
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows([[tc.cell_text(v) for v in r] for r in tk_rows()])
    a = tc.read_tokhai([("x", tk_rows())])["items"]
    b = tc.read_tokhai([("c", tc.rows_from_file(str(p)))])["items"]
    assert [(x["tag"], x["qty"], x["net"], x["amount"]) for x in a] == [(x["tag"], x["qty"], x["net"], x["amount"]) for x in b]


def test_paste_tab_text():
    text = "\n".join("\t".join(tc.cell_text(v) for v in r) for r in tk_rows())
    assert len(tc.read_tokhai([("dan", tc.rows_from_paste(text))])["items"]) == 36


# ---------------------------------------------------------------- đối chiếu: giống macro trên mẫu thật
def test_real_sample_matches_macro():
    _wb, res = run(shirai_rec(pxkNo="00000341"))
    s = res["summary"]
    assert (s["nTK"], s["nINV"], s["nOK"], s["nERR"], s["nNotOnTK"]) == (36, 36, 33, 3, 0)
    bad = [r["tk"]["tag"] for r in res["rows"] if r["status"] != "KHỚP"]
    assert bad == ["TK1-<31>", "TK1-<34>", "TK1-<36>"]
    assert all(r["status"] == "LỆCH" and r["bad"] == {"net"} for r in res["rows"] if r["status"] != "KHỚP")
    hd = {h["tag"]: h["ok"] for h in res["header"]}
    assert hd["R40"] and hd["R46"] and hd["R51"] and hd["R53"] and hd["R54"]
    assert not hd["R41"] and not hd["R47"] and not hd["R49"] and not hd["R64"]  # như sheet SoSanh_TK_INV của file xlsm
    assert hd["HĐ VAT"] and hd["PXK"]


def test_pxk_of_lot_matches_tokhai():
    _wb, res = run(shirai_rec())  # lô PXK 00000345 = số trên tờ khai
    hd = {h["tag"]: h["ok"] for h in res["header"]}
    assert hd["R49"] and hd["R64"]


def test_all_match_when_invoice_fixed():
    rec = shirai_rec()
    nets = {31: 10.4, 34: 30.6, 36: 51}
    for it in rec["items"]:
        if it["stt"] in nets:
            it["net"] = nets[it["stt"]]
    _wb, res = run(rec)
    assert res["summary"]["nOK"] == 36 and res["summary"]["nERR"] == 0


def test_qty_price_name_missing_and_origin_errors():
    rows = tk_rows()
    r2 = find_row(rows, "<02>")
    q_row = next(i for i in range(r2, r2 + 10) if any(tc.cell_text(v) == "Số lượng (1)" for v in rows[i]))
    set_cell(rows, q_row, 16, "150")  # cột Q: SL(1) 104 -> 150
    r3 = find_row(rows, "<03>")
    d_row = next(i for i in range(r3, r3 + 6) if tc.cell_text(rows[i][2]) == "Mô tả hàng hóa")
    set_cell(rows, d_row, 5, "Tấm lót Pad NTI-LS0019060SDH(AF_2X:W130xD5xH290) Po.No 202639HT . Hàng mới 100%")  # thêm 1 chữ
    r4 = find_row(rows, "<04>")
    d4 = next(i for i in range(r4, r4 + 6) if tc.cell_text(rows[i][2]) == "Mô tả hàng hóa")
    set_cell(rows, d4, 5, "Tấm lót Pad NTI-LS0019060SDH(AF_1A:W240xD53xH350) Po.No 202639HT")  # bỏ 'Hàng mới'
    r5 = find_row(rows, "<05>")
    set_cell(rows, r5, 2, "")  # xóa thẻ dòng <05>: dòng này không còn trên tờ khai
    _wb, res = run(shirai_rec(), rows)
    by = {r["tk"]["tag"]: r for r in res["rows"] if r["tk"]}
    assert by["TK1-<02>"]["status"] == "LỆCH" and "qty" in by["TK1-<02>"]["bad"]
    assert "SL×ĐG" in by["TK1-<02>"]["internal"]
    assert by["TK1-<03>"]["status"] == "SAI TÊN" and '"X"' in by["TK1-<03>"]["detail"]
    assert by["TK1-<04>"]["status"] == "LỖI TK" and "Hàng mới" in by["TK1-<04>"]["internal"]
    not_on = [r["inv"]["row"] for r in res["rows"] if r["status"] == "CHƯA LÊN TK"]
    assert not_on == [5]


def test_no_tolerance_one_cent_is_flagged():
    """Không cho phép sai số: lệch 0,01 vẫn báo, nhiễu số thực (1.1400000000000001 so 1.14) thì không."""
    assert tc.differs(1.14, 1.15) and not tc.differs(1.1400000000000001, 1.14) and not tc.differs(100, 100)
    rec = shirai_rec()
    rec["items"][2]["net"] = round(rec["items"][2]["net"] + 0.01, 2)
    _wb, res = run(rec)
    by = {r["tk"]["tag"]: r for r in res["rows"] if r["tk"]}
    assert by["TK1-<03>"]["status"] == "LỆCH" and "net" in by["TK1-<03>"]["bad"]
    assert res["summary"]["tol"] == 0


def test_unit_and_hs_by_customer():
    rec = shirai_rec()
    rec["items"][0]["hs"] = "48239099"  # HS hồ sơ khác HS tờ khai 48191000
    rec["items"][1]["unit"] = "ống"  # ống -> PIP, tờ khai ghi PCE
    _wb, res = run(rec)
    by = {r["tk"]["tag"]: r for r in res["rows"] if r["tk"]}
    assert "HS TK 48191000≠HS hồ sơ 48239099" in by["TK1-<01>"]["internal"]
    assert "ĐVT1=PCE≠PIP" in by["TK1-<02>"]["internal"]


def test_two_tokhai_files_numbered_and_summed():
    rows = tk_rows()
    _wb, res = tc.build_workbook(app, shirai_rec(), [("a", rows), ("b", rows)])
    tags = [r["tk"]["tag"] for r in res["rows"] if r["tk"]]
    assert tags[0] == "TK1-<01>" and tags[36] == "TK2-<01>" and len(tags) == 72
    kien = next(h for h in res["header"] if h["tag"] == "R40")
    assert "374 PK" in kien["tk"] and not kien["ok"]  # 2 tờ khai cộng lại 187 + 187


# ---------------------------------------------------------------- file Excel kết quả
def test_workbook_sheets_and_formatting():
    rec = shirai_rec(pxkNo="00000341")
    rows = tk_rows()
    r3 = find_row(rows, "<03>")
    d_row = next(i for i in range(r3, r3 + 6) if tc.cell_text(rows[i][2]) == "Mô tả hàng hóa")
    set_cell(rows, d_row, 5, "Tấm lót Pad NTI-LS0019060SDH(AF_2X:W130xD5xH290) Po.No 202639HT . Hàng mới 100%")
    wb, res = run(rec, rows)
    assert wb.sheetnames == ["KetQua", "ToKhai", "Invoice", "HoaDon_VAT", "PXK"]
    ws = wb["KetQua"]
    assert ws["C3"].value == 0
    assert "PHÁT HIỆN" in ws["H5"].value
    rules = [r for rng in ws.conditional_formatting for r in rng.rules]
    assert rules and all("$C$3" in r.formula[0] for r in rules)
    name_cells = [c for row in ws.iter_rows() for c in row if c.column == 3 and type(c.value).__name__ == "CellRichText"]
    assert name_cells  # phần tên khác nhau tô đỏ trong ô
    assert wb["ToKhai"]["C4"].value == "Số tờ khai"


def test_run_check_writes_into_lot_folder(store, tmp_path, monkeypatch):
    rec = shirai_rec()
    res = app.lot_tokhai_check(store, rec, [str(TK_FILE)])
    folder = store.ensure_lot_folder(rec)
    assert Path(res["path"]).parent == Path(folder) and res["fname"] == "KiemTraToKhai_shirai_20.11.xlsx"
    assert [Path(p).name for p in res["tkFiles"]] == ["ToKhaiNhap_shirai_20.11.xlsx"]
    assert res["lines"][0].startswith("❌")
    # file cũ đang mở trong Excel -> ghi _2
    real_save = openpyxl.Workbook.save

    def locked(self, path):
        if str(path).endswith("KiemTraToKhai_shirai_20.11.xlsx"):
            raise PermissionError("đang mở")
        return real_save(self, path)

    monkeypatch.setattr(openpyxl.Workbook, "save", locked)
    res2 = app.lot_tokhai_check(store, rec, res["tkFiles"])
    assert res2["renamed"] and res2["fname"] == "KiemTraToKhai_shirai_20.11_2.xlsx"


def test_paste_saved_as_csv(store):
    rec = shirai_rec()
    text = "\n".join("\t".join(tc.cell_text(v) for v in r) for r in tk_rows())
    res = app.lot_tokhai_check(store, rec, [], 0.01, paste_text=text)
    assert any(p.endswith("_dan.csv") for p in res["tkFiles"])
    assert res["result"]["summary"]["nTK"] == 36


def test_record_keeps_tokhai_files(store):
    from ui_qt.state import Lot
    lot = Lot(app, store)
    rec = shirai_rec()
    lot.load_record(dict(rec, tkDraftFiles=[str(TK_FILE)], tkTol=0.5))
    assert lot.tk_files == [str(TK_FILE)] and lot.tk_tol == 0  # không còn sai số: bỏ qua tkTol của bản cũ
    r = lot.record()
    assert r["tkDraftFiles"] == [str(TK_FILE)]
    out = lot.check_tokhai()
    assert any(f["mode"] == "TKCHECK" for f in lot.files) and out["result"]["summary"]["nTK"] == 36


def test_no_items_raises(store):
    with pytest.raises(ValueError):
        app.lot_tokhai_check(store, shirai_rec(items=[]), [str(TK_FILE)])


def test_learn_declared_name(store):
    """Học tên khai báo đúng: dòng SAI TÊN -> nhớ tên tờ khai, lô sau Invoice dùng tên đó và khớp."""
    rows = tk_rows()
    r3 = find_row(rows, "<03>")
    d_row = next(i for i in range(r3, r3 + 6) if tc.cell_text(rows[i][2]) == "Mô tả hàng hóa")
    set_cell(rows, d_row, 5, "Tấm lót Pad NTI-LS0019060SDH(AF_2X:W130xD5xH290) Po.No 202639HT . Hàng mới 100%")
    rec = shirai_rec()
    _wb, res = run(rec, rows)
    sai = [r for r in res["rows"] if r["status"] == "SAI TÊN"]
    assert len(sai) == 1
    done = app.lot_learn_tokhai_names(store, rec, res)
    assert len(done) == 1
    items = rec["items"]
    assert items[done[0][0]]["ten_hq"] == done[0][2]
    assert store.ten_khai_bao_for("shirai", items[done[0][0]]) == done[0][2]
    # lô mới: tên đã học được áp lại
    fresh = shirai_rec()
    assert app.lot_apply_ten_khai_bao(store, "shirai", fresh["items"]) == 1
    # kiểm tra lại với tên đã sửa -> hết SAI TÊN
    _wb, res2 = run(rec, rows)
    assert not [r for r in res2["rows"] if r["status"] == "SAI TÊN"]

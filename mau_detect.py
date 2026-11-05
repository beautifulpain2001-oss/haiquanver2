"""Nhận biết các CHỖ CÓ THỂ THAY ĐỔI trong một chứng từ đã điền sẵn (Word/Excel) để biến thành mẫu có ô {{...}}.

Phần mềm chỉ ĐỀ XUẤT; người dùng quyết định chỗ nào thành ô và ô nào (xem hộp thoại ở ui_qt/pages_kho.py).
- `detect(ext, data, ctx)` -> danh sách ứng viên [{id, sheet, where, text, value, token, why, kind, ...}]
- `apply(ext, data, choices, sheet)` -> bytes mới; `choices` = {id: ô thay thế} chỉ gồm những chỗ người dùng đã chọn.
- Excel nhiều sheet: `split_sheets` tách mỗi sheet thành một file riêng (mỗi sheet là một mẫu).

Nhận biết theo mẫu chữ: số PO (YNCGDD2606030001), số PXK, số hóa đơn, số tờ khai, ngày (cả "ngày 19 tháng 06 năm 2026", tháng/năm, 19/06/2026),
số tiền bằng chữ, mã số thuế, tên/địa chỉ bên bán và khách, số lượng/trị giá (số có dấu chấm ngăn nghìn); và theo BẢNG HÀNG (Excel): dòng đầu của bảng,
các ô tổng cộng, các dòng mẫu thừa phía dưới.
"""

import io
import re
import unicodedata
import zipfile
from datetime import date, datetime
from xml.sax.saxutils import escape

import mau_rieng

_UP = lambda s: re.sub(r"\s+", " ", "".join(c for c in unicodedata.normalize("NFD", str(s or "").replace("đ", "d").replace("Đ", "D")) if unicodedata.category(c) != "Mn")).strip().upper()

# (ô, mẫu chữ, mô tả); mẫu có nhóm tên v = chỗ thay; nhiều nhóm tên khác thì mỗi nhóm một ô (ghi trong GROUPS)
_RULES = [
    ("so_po", re.compile(r"(?<![A-Za-z0-9])(?P<v>[A-Z]{3,}\d{8,}(?:\s*\+\s*[A-Z]{3,}\d{8,})*)"), "Giống số PO (chữ + dãy số)"),
    ("so_pxk", re.compile(r"PXK\w*\s*:\s*(?P<v>\d{5,})"), "Số phiếu xuất kho sau chữ PXK…"),
    ("so_hd", re.compile(r"(?:Hóa\s*Đơn\s*Số|số\s*hóa\s*đơn)\s*:?\s*(?P<v>\d{5,})", re.I), "Số hóa đơn"),
    ("so_tk", re.compile(r"(?<!\d)(?P<v>\d{12})(?!\d)"), "Dãy 12 số giống số tờ khai"),
    ("ngay", re.compile(r"(?<!\d)(?P<v>\d{1,2}/\d{1,2}/\d{4})(?!\d)"), "Ngày dd/mm/yyyy"),
    ("bien_ban", re.compile(r"Số\s*:\s*(?P<mm>\d{1,2})/(?P<yyyy>\d{4})"), "Số biên bản: tháng/năm"),
    ("ngay_dai", re.compile(r"ngày\s+(?P<dd>\d{1,2})\s+tháng\s+(?P<mm>\d{1,2})\s+năm\s*\xa0?\s*(?P<yyyy>\d{4})", re.I), "Ngày tháng năm viết chữ"),
    ("thang_nam", re.compile(r"tháng\s+(?P<mm>\d{1,2})/(?P<yyyy>\d{4})", re.I), "Tháng/năm"),
    ("thang_nam_hoa", re.compile(r"(?P<yyyy>\d{4})年(?P<mm>\d{1,2})月"), "Năm/tháng chữ Hán"),
    ("mst", re.compile(r"(?:MST|Mã số thuế)\s*[:：]?\s*[\xa0 ]*(?P<v>\d{10}(?:-\d{3})?)", re.I), "Mã số thuế"),
    ("tien_chu", re.compile(r"(?P<v>[^\n]{12,}đồng)\s*$", re.I), "Số tiền viết bằng chữ"),
    ("so_cham", re.compile(r"(?<![\d.,])(?P<v>\d{1,3}(?:\.\d{3})+)(?![\d.,])"), "Số có dấu chấm ngăn nghìn"),
]
GROUPS = {"ngay_dai": {"dd": "dd", "mm": "mm", "yyyy": "yyyy"}, "bien_ban": {"mm": "mm", "yyyy": "yyyy"}, "thang_nam": {"mm": "mm", "yyyy": "yyyy"},
          "thang_nam_hoa": {"mm": "mm", "yyyy": "yyyy"}}
_DIRECT = {"so_po": "so_po", "so_pxk": "so_pxk", "so_hd": "so_hd", "so_tk": "so_tk", "ngay": "ngay", "tien_chu": "tong_tri_gia_chu"}
_LABELS = [("so luong", "tong_sl"), ("tri gia", "tong_tri_gia"), ("thanh tien", "tong_tri_gia"), ("tong tien", "tong_tri_gia"), ("so kien", "tong_kien"), ("trong luong", "tong_net")]

# tiêu đề cột bảng hàng -> ô theo dòng hàng
_HEADS = [("STT", "stt"), ("MA DON DAT HANG", "ma"), ("MA HANG", "ma"), ("MA LIEU", "ma"), ("TEN HANG", "ten"), ("TEN SAN PHAM", "ten"), ("DIEN GIAI", "ten"),
          ("MO TA", "ten"), ("DVT", "dvt"), ("DON VI", "dvt"), ("SO LUONG", "sl"), ("DON GIA", "gia"), ("THANH TIEN", "thanh_tien"), ("SO TIEN", "thanh_tien"),
          ("CA BI", "gross"), ("TINH", "net"), ("TRONG LUONG", "kg"), ("SO KIEN", "kien"), ("SO HOA DON", "so_hd"), ("NGAY HACH TOAN", "ngay"),
          ("NGAY GIAO HANG", "ngay"), ("NGAY", "ngay")]
_SUM_TOKEN = {"sl": "tong_sl", "thanh_tien": "tong_tri_gia", "kien": "tong_kien", "net": "tong_net", "gross": "tong_gross"}
_TOTAL = ("TONG", "CONG")


def _known(ctx):
    ctx = ctx or {}
    return ctx.get("seller") or {}, ctx.get("customer") or {}


def _party_spans(text, ctx):
    """Tên/địa chỉ/MST bên bán và khách (theo `ctx`, hoặc đoán nếu không có): [(start, end, token, lý do)]."""
    seller, cust = _known(ctx)
    out = []

    def find(s, token, why):
        s = (s or "").strip().rstrip(".")
        if len(s) >= 8:
            for m in re.finditer(re.escape(s), text):
                out.append((m.start(), m.end(), token, why))

    find(seller.get("name"), "ben_ban_ten", "Tên công ty bên bán")
    find(seller.get("addr"), "ben_ban_dia_chi", "Địa chỉ bên bán")
    find(cust.get("name"), "khach_ten", "Tên công ty khách")
    find(cust.get("addr"), "khach_dia_chi", "Địa chỉ khách")
    if seller.get("addr") and not any(t == "ben_ban_dia_chi" for *_a, t, _w in out):
        m = re.search(r"Lô\s*CN-15\.1[^\n]*?Việt\s*Nam\.?", text)
        if m:
            out.append((m.start(), m.end(), "ben_ban_dia_chi", "Địa chỉ bên bán (nhận theo chữ Lô CN-15.1…)"))
    if not cust.get("name"):  # không biết khách: gợi ý các tên công ty viết hoa khác bên bán
        for m in re.finditer(r"CÔNG TY [A-ZÀ-Ỹ0-9 ,.\-]{6,}?(?=\s*(?:\n|$|[:;,.]\s|\s{2,}))", text):
            if not any(t == "ben_ban_ten" and s <= m.start() < e for s, e, t, _w in out):
                out.append((m.start(), m.end(), "khach_ten", "Tên công ty (có thể là khách)"))
    return out


def text_candidates(text, ctx=None):
    """Các chỗ đổi được trong một đoạn chữ: [{start, end, token, why, value}] đã bỏ chỗ chồng nhau (chỗ dài hơn thắng)."""
    seller, cust = _known(ctx)
    found = []
    for s, e, t, why in _party_spans(text, ctx):
        found.append({"start": s, "end": e, "token": t, "why": why})
    for name, rx, why in _RULES:
        for m in rx.finditer(text):
            if name in GROUPS:
                for g, tok in GROUPS[name].items():
                    found.append({"start": m.start(g), "end": m.end(g), "token": tok, "why": why})
            elif name == "mst":
                v = m.group("v")
                token = "ben_ban_mst" if v == str(seller.get("mst") or "") else ("khach_mst" if v == str(cust.get("mst") or "") or True else "")
                found.append({"start": m.start("v"), "end": m.end("v"), "token": token, "why": why})
            elif name == "so_cham":
                near = _UP(text[max(0, m.start() - 40):m.start()])
                token = next((tok for key, tok in _LABELS if key.upper() in near), "")
                found.append({"start": m.start("v"), "end": m.end("v"), "token": token, "why": why + (" (đoán theo chữ đứng trước)" if token else " (chưa rõ là gì)")})
            else:
                found.append({"start": m.start("v"), "end": m.end("v"), "token": _DIRECT.get(name, ""), "why": why})
    found.sort(key=lambda d: (d["start"], -(d["end"] - d["start"])))
    out = []
    for d in found:  # bỏ chỗ chồng lên chỗ đã chọn
        if not any(d["start"] < o["end"] and o["start"] < d["end"] for o in out):
            d["value"] = text[d["start"]:d["end"]]
            out.append(d)
    out.sort(key=lambda d: d["start"])
    return out


# ------------------------------------------------------------------------------------------------ Excel
def _addr(c):
    return c.coordinate


def _table(ws):
    """Bảng hàng đầu tiên của sheet: {header_row, cols{col: token}, first, rows[...], total_row} hoặc None."""
    for row in ws.iter_rows(max_row=min(ws.max_row, 80)):
        cols = {}
        for c in row:
            if isinstance(c.value, str):
                u = _UP(c.value)
                for key, tok in _HEADS:
                    if key in u and (c.column not in cols):
                        if key == "NGAY" and u != "NGAY":
                            continue
                        if key == "TRONG LUONG" and ("CA BI" in u or "TINH" in u):
                            continue
                        cols[c.column] = tok
                        break
        if len(cols) >= 3 and any(t in cols.values() for t in ("ten", "sl", "ma")):
            hr = row[0].row
            first = hr + 1
            while first < ws.max_row and not any(c.value not in (None, "") for c in ws[first]):  # dòng trống ngăn giữa tiêu đề và dòng hàng
                first += 1
            total = None
            for r in range(first, min(ws.max_row, first + 60) + 1):
                lead = " ".join(_UP(ws.cell(row=r, column=c).value) for c in range(1, 4) if isinstance(ws.cell(row=r, column=c).value, str))
                if any(lead.startswith(k) for k in _TOTAL):
                    total = r
                    break
            if total is None or total <= first:
                continue
            return {"header": hr, "cols": cols, "first": first, "total": total}
    return None


def _cell_text(v):
    if isinstance(v, datetime) or isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return "" if v is None else str(v)


def detect_xlsx(data, ctx=None, sheet=None):
    import openpyxl
    from openpyxl.worksheet.formula import ArrayFormula
    wb = openpyxl.load_workbook(io.BytesIO(data))
    out = []
    for ws in wb.worksheets:
        if sheet is not None and ws.title != sheet:
            continue
        tbl = _table(ws)
        skip = set()
        if tbl:
            first = tbl["first"]
            for c in ws[first]:
                if c.value is None:
                    continue
                tok = tbl["cols"].get(c.column, "")
                if isinstance(c.value, str) and mau_rieng._TOKEN.search(c.value):
                    continue
                out.append({"id": f"{ws.title}!{_addr(c)}", "sheet": ws.title, "where": f"{_addr(c)} (dòng hàng đầu tiên)", "text": _cell_text(c.value),
                            "value": _cell_text(c.value), "token": tok, "kind": "cell", "why": "Ô trong dòng hàng của bảng" + ("" if tok else " (chưa rõ là gì)")})
            for c in ws[tbl["total"]]:
                if isinstance(c.value, str) and c.value.upper().startswith("=") and "SUM" in c.value.upper():
                    tok = _SUM_TOKEN.get(tbl["cols"].get(c.column, ""), "")
                    out.append({"id": f"{ws.title}!{_addr(c)}", "sheet": ws.title, "where": f"{_addr(c)} (dòng tổng cộng)", "text": c.value, "value": c.value, "token": tok,
                                "kind": "cell", "why": "Công thức cộng của cột " + (tbl["cols"].get(c.column) or "")})
            extra = [r for r in range(first + 1, tbl["total"]) if any(c.value not in (None, "") and not (isinstance(c.value, str) and c.value.startswith("=")) for c in ws[r])
                     or any(isinstance(c.value, str) and c.value.startswith("=") for c in ws[r])]
            if extra or tbl["total"] - first > 1:
                n = tbl["total"] - first - 1
                out.append({"id": f"{ws.title}!drop", "sheet": ws.title, "where": f"dòng {first + 1}–{tbl['total'] - 1}", "text": f"{n} dòng mẫu thừa dưới dòng hàng đầu",
                            "value": f"{n} dòng", "token": "(xóa)", "kind": "drop_rows", "start": first + 1, "count": n,
                            "why": "Mỗi mặt hàng sẽ được phần mềm tự thêm dòng từ dòng hàng đầu"})
            skip = {(r, c.column) for r in range(first, tbl["total"] + 1) for c in ws[r]}
        for row in ws.iter_rows():
            for c in row:
                if (c.row, c.column) in skip or c.value is None:
                    continue
                v = c.value
                if isinstance(v, ArrayFormula):
                    out.append({"id": f"{ws.title}!{_addr(c)}", "sheet": ws.title, "where": _addr(c), "text": "(công thức đọc số thành chữ)", "value": "(công thức)",
                                "token": "tong_tri_gia_chu", "kind": "cell", "why": "Công thức mảng, thường là số tiền bằng chữ"})
                    continue
                if isinstance(v, (datetime, date)):
                    out.append({"id": f"{ws.title}!{_addr(c)}", "sheet": ws.title, "where": _addr(c), "text": _cell_text(v), "value": _cell_text(v), "token": "ngay",
                                "kind": "cell", "why": "Ô ngày"})
                    continue
                if not isinstance(v, str) or mau_rieng._TOKEN.search(v) or v.startswith("="):
                    continue
                for k, d in enumerate(text_candidates(v, ctx)):
                    out.append({"id": f"{ws.title}!{_addr(c)}#{k}", "sheet": ws.title, "where": _addr(c), "text": v, "value": d["value"], "token": d["token"],
                                "kind": "span", "start": d["start"], "end": d["end"], "why": d["why"]})
    return out


def _delete_rows(ws, start, count):
    """Xóa `count` dòng từ dòng `start`, dời ô gộp và công thức phía dưới lên theo (công thức chỉ dời theo vị trí, như khi kéo ô)."""
    from openpyxl.formula.translate import Translator
    below = [(m.min_row, m.min_col, m.max_row, m.max_col) for m in list(ws.merged_cells.ranges) if m.min_row >= start + count]
    for m in list(ws.merged_cells.ranges):
        if m.min_row >= start:
            ws.unmerge_cells(str(m))
    heights = {r: ws.row_dimensions[r].height for r in range(start + count, ws.max_row + 1)}
    ws.delete_rows(start, count)
    for r, h in heights.items():
        ws.row_dimensions[r - count].height = h
    for r0, c0, r1, c1 in below:
        ws.merge_cells(start_row=r0 - count, start_column=c0, end_row=r1 - count, end_column=c1)
    for row in ws.iter_rows(min_row=start):
        for c in row:
            if isinstance(c.value, str) and c.value.startswith("="):
                c.value = Translator(c.value, origin=f"{c.column_letter}{c.row + count}").translate_formula(c.coordinate)


def apply_xlsx(data, choices, sheet=None, ctx=None):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    cands = {d["id"]: d for d in detect_xlsx(data, ctx, sheet)}
    spans = {}
    drops = []
    for cid, token in choices.items():
        d = cands.get(cid)
        if not d or not token:
            continue
        ws = wb[d["sheet"]]
        if d["kind"] == "drop_rows":
            drops.append((ws, d["start"], d["count"]))
        elif d["kind"] == "cell":
            ws[d["where"].split(" ")[0]].value = "{{" + token + "}}"
        else:
            spans.setdefault((d["sheet"], d["where"]), []).append((d["start"], d["end"], token, d["text"]))
    for (sh, addr), lst in spans.items():
        text = lst[0][3]
        for s, e, tok, _t in sorted(lst, key=lambda x: -x[0]):
            text = text[:s] + "{{" + tok + "}}" + text[e:]
        wb[sh][addr].value = text
    for ws, start, count in sorted(drops, key=lambda x: -x[1]):
        _delete_rows(ws, start, count)
    if sheet is not None:
        for ws in list(wb.worksheets):
            if ws.title != sheet:
                wb.remove(ws)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def sheet_names(data):
    import openpyxl
    return openpyxl.load_workbook(io.BytesIO(data)).sheetnames


def split_sheet(data, sheet):
    """File Excel chỉ giữ lại một sheet."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    for ws in list(wb.worksheets):
        if ws.title != sheet:
            wb.remove(ws)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ------------------------------------------------------------------------------------------------ Word
def detect_docx(data, ctx=None):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for i, p in enumerate(mau_rieng._PARA.findall(xml)):
        text = mau_rieng._para_text(p)
        if not text.strip() or mau_rieng._TOKEN.search(text):
            continue
        for k, d in enumerate(text_candidates(text, ctx)):
            out.append({"id": f"p{i}#{k}", "sheet": "", "where": f"đoạn {i + 1}", "text": text, "value": d["value"], "token": d["token"], "kind": "span",
                        "para": i, "start": d["start"], "end": d["end"], "why": d["why"]})
    return out


def apply_docx(data, choices, ctx=None):
    cands = {d["id"]: d for d in detect_docx(data, ctx)}
    by_para = {}
    for cid, token in choices.items():
        d = cands.get(cid)
        if d and token:
            by_para.setdefault(d["para"], []).append((d["start"], d["end"], token, d["text"]))
    src = zipfile.ZipFile(io.BytesIO(data))
    xml = src.read("word/document.xml").decode("utf-8")
    idx = [0]

    def repl(m):
        i = idx[0]
        idx[0] += 1
        if i not in by_para:
            return m.group(0)
        text = by_para[i][0][3]
        for s, e, tok, _t in sorted(by_para[i], key=lambda x: -x[0]):
            text = text[:s] + "{{" + tok + "}}" + text[e:]
        return mau_rieng._set_para(m.group(0), text)

    new_xml = mau_rieng._PARA.sub(repl, xml)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, new_xml.encode("utf-8") if item.filename == "word/document.xml" else src.read(item.filename))
    return out.getvalue()


# ------------------------------------------------------------------------------------------------ chung
def detect(ext, data, ctx=None, sheet=None):
    ext = ext.lower().lstrip(".")
    if ext == "docx":
        return detect_docx(data, ctx)
    if ext in ("xlsx", "xlsm"):
        return detect_xlsx(data, ctx, sheet)
    raise ValueError("Chỉ nhận file Word (.docx) hoặc Excel (.xlsx).")


def apply(ext, data, choices, sheet=None, ctx=None):
    ext = ext.lower().lstrip(".")
    if ext == "docx":
        return apply_docx(data, choices, ctx)
    if ext in ("xlsx", "xlsm"):
        return apply_xlsx(data, choices, sheet, ctx)
    raise ValueError("Chỉ nhận file Word (.docx) hoặc Excel (.xlsx).")


def guess_loai(sheet_or_name):
    """Đoán loại chứng từ từ tên sheet/tên file: bdc, BBGH, Đơn đặt hàng, PLX…"""
    u = _UP(sheet_or_name)
    for key, loai in (("BDC", "BDC"), ("DOI CHIEU HANG", "BDC"), ("BBGH", "BBGH"), ("BIEN BAN", "BBGH"), ("DON DAT HANG", "PO"), ("PO", "PO"), ("PLX", "PLX"),
                      ("PHU LUC", "PLX"), ("DNTT", "DNTT"), ("DE NGHI THANH TOAN", "DNTT"), ("DCCN", "DCCN"), ("CONG NO", "DCCN")):
        if key in u.split() or (len(key) > 3 and key in u):
            return loai
    return "KHAC"

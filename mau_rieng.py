"""Mẫu riêng của từng khách (Word .docx hoặc Excel .xlsx): người dùng nhập thẳng file mẫu của khách, trong file ghi chỗ cần điền bằng ô thay thế
dạng {{ten_o}}; phần mềm điền số liệu của lô rồi xuất lại ĐÚNG định dạng file đó (không dựng lại chứng từ).

- Ô thay thế chung của cả lô: {{so_po}}, {{so_pxk}}, {{ngay}}, {{tong_sl}}, {{khach_ten}}... (xem TOKENS).
- Ô theo dòng hàng: {{stt}}, {{ma}}, {{ten}}, {{dvt}}, {{sl}}, {{gia}}, {{thanh_tien}}, {{kg}}, {{kien}}, {{net}}, {{gross}}. Dòng (Excel) / dòng bảng
  hoặc đoạn (Word) có chứa ô theo dòng hàng được nhân lên cho mỗi mặt hàng.
- Docx là file zip chứa XML nên không cần thư viện ngoài (bản .exe không phải kèm thêm gì).
"""

import io
import re
import zipfile
from copy import copy
from xml.sax.saxutils import escape

TOKENS = [
    ("khach_ten", "Tên công ty khách"), ("khach_dia_chi", "Địa chỉ khách"), ("khach_mst", "Mã số thuế khách"),
    ("ben_ban_ten", "Tên công ty bên bán (Hồng Thiên)"), ("ben_ban_dia_chi", "Địa chỉ bên bán"), ("ben_ban_mst", "Mã số thuế bên bán"),
    ("so_po", "Số PO"), ("ngay_po", "Ngày PO"), ("so_pxk", "Số phiếu xuất kho"), ("so_hd", "Số hóa đơn VAT"), ("so_tk", "Số tờ khai"),
    ("ngay", "Ngày chứng từ dd/mm/yyyy"), ("dd", "Ngày (2 số)"), ("mm", "Tháng (2 số)"), ("yyyy", "Năm"), ("yy", "Năm (2 số cuối)"),
    ("tong_sl", "Tổng số lượng"), ("tong_tri_gia", "Tổng trị giá"), ("tong_tri_gia_chu", "Tổng trị giá bằng chữ"), ("tong_kien", "Tổng số kiện"),
    ("tong_net", "Tổng trọng lượng tịnh"), ("tong_gross", "Tổng trọng lượng cả bì"),
    ("ten_hang", "Tên các mặt hàng (nối bằng ; )"), ("ma_hang", "Mã các mặt hàng"), ("hs", "Mã HS các mặt hàng"),
    ("dvt_chung", "Đơn vị tính của lô (theo mặt hàng đầu)"), ("dvt_chung_hoa", "Đơn vị tính của lô, viết hoa chữ đầu"),
    ("ngay_so", "Ngày chứng từ dạng ngày của Excel (ô chỉ chứa ô này)"), ("d", "Ngày (không có số 0 đầu)"), ("m", "Tháng (không có số 0 đầu)"), ("ngay_ngan", "Ngày chứng từ d/m/yyyy"),
    ("han_tt", "Hạn thanh toán dd/mm/yyyy (ngày chứng từ + số ngày nợ)"), ("so_ngay_no", "Số ngày nợ (thanh toán sau)"),
    ("sl_kien", "Số lượng mỗi kiện (định mức chung của lô, dùng trong công thức tổng kiện)"),
    ("po_dd", "Ngày của ngày PO (2 số)"), ("po_mm", "Tháng của ngày PO (2 số)"), ("po_yyyy", "Năm của ngày PO"), ("tong_tri_gia_phay", "Tổng trị giá dạng 22,534,720"),
]
ITEM_TOKENS = [
    ("stt", "Số thứ tự"), ("ma", "Mã hàng"), ("ten", "Tên hàng"), ("dvt", "Đơn vị tính"), ("sl", "Số lượng"), ("gia", "Đơn giá"),
    ("thanh_tien", "Thành tiền"), ("kg", "kg/chiếc"), ("bi", "Bì của dòng (cả bì - tịnh, kg)"), ("kien", "Số kiện"), ("net", "Trọng lượng tịnh"), ("gross", "Trọng lượng cả bì"), ("hs_dong", "Mã HS"),
    ("dvt_hoa", "Đơn vị tính viết hoa chữ đầu"),
    ("quy_cach", "Quy cách 'phi x dày x dài' (VD 114 x 2.5 x 265)"), ("phi", "Đường kính trong (số)"), ("day", "Độ dày (số)"), ("dai", "Chiều dài (số)"),
    ("tc_phi", "Tiêu chuẩn đường kính trong (VD 114±0,5)"), ("tc_day", "Tiêu chuẩn độ dày (VD 2.5±0,2)"), ("tc_dai", "Tiêu chuẩn chiều dài (VD 265±2)"),
    ("ma_kt", "Mã sản phẩm trên phiếu kiểm tra chất lượng (không đặt thì là mã hàng)"),
    ("sl_phay", "Số lượng dạng 8,509.0 (phẩy ngăn nghìn, như bảng kê Phụ lục X Richsound)"),
    ("thanh_tien_phay", "Thành tiền dạng 33,950,910.0 (phẩy ngăn nghìn, như bảng kê Phụ lục X Richsound)"),
]
_ITEM_KEYS = {k for k, _ in ITEM_TOKENS}
_TOKEN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def _dots(x):
    """Số có dấu chấm ngăn nghìn kiểu Việt Nam: 21212 -> '21.212'; 0,5 -> '0,5'."""
    x = float(x or 0)
    s = f"{x:,.3f}".rstrip("0").rstrip(".") if x != int(x) else f"{int(x):,}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _po_dates(rec):
    """Lô nhiều PO (không có một ngày PO chung): ngày của từng PO nối 'ngày1 + ngày2' theo thứ tự PO trên các dòng hàng."""
    dates, seen = rec.get("poDates") or {}, []
    for it in rec.get("items") or []:
        p = str(it.get("po") or "").strip()
        if p and p not in seen:
            seen.append(p)
    got = [str(dates.get(p) or "") for p in seen]
    return " + ".join(got) if any(got) else ""


def batch_values(rec, prof, consts):
    """Giá trị các ô chung của lô. `consts`: {name, addr, mst, dmy, words} từ phần mềm (tên bên bán, hàm đổi ngày, đọc số thành chữ)."""
    items = rec.get("items") or []
    d = consts["date"](rec.get("docDate"))
    total = sum(float(it.get("amount") or 0) or float(it.get("qty") or 0) * float(it.get("price") or 0) for it in items)
    num = lambda k: sum(float(it.get(k) or 0) for it in items)
    kien = consts.get("kien", num("kien"))  # tổng kiện phần mềm tính (Best: tổng SL / SL mỗi kiện, làm tròn cả lô)
    divs = {float(it.get("div") or 0) for it in items}
    sl_kien = f"{next(iter(divs)):g}" if len(divs) == 1 and next(iter(divs)) > 0 else ""  # định mức khác nhau: không có số chung
    unit = str((items[0].get("unit") if items else "") or prof.get("unit") or "")
    try:
        days = int(float(rec.get("payDays") or prof.get("payDays") or 30))
    except (TypeError, ValueError):
        days = 30
    import datetime
    due = d + datetime.timedelta(days=days)
    pm = re.match(r"\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", str(rec.get("poDate") or ""))
    po_parts = (pm.group(1).zfill(2), pm.group(2).zfill(2), pm.group(3)) if pm else (d.strftime("%d"), d.strftime("%m"), d.strftime("%Y"))
    return {
        "po_dd": po_parts[0], "po_mm": po_parts[1], "po_yyyy": po_parts[2],
        "khach_ten": prof.get("name", ""), "khach_dia_chi": prof.get("addr", ""), "khach_mst": prof.get("mst", ""),
        "ben_ban_ten": consts["name"], "ben_ban_dia_chi": consts["addr"].rstrip("."), "ben_ban_mst": consts["mst"],
        "so_po": rec.get("poNumber", ""), "ngay_po": rec.get("poDate") or _po_dates(rec), "so_pxk": rec.get("pxkNo", ""), "so_hd": rec.get("hdNo", ""), "so_tk": rec.get("tkNo", ""),
        "ngay": d.strftime("%d/%m/%Y"), "dd": d.strftime("%d"), "mm": d.strftime("%m"), "yyyy": d.strftime("%Y"), "yy": d.strftime("%y"),
        "tong_sl": _dots(num("qty")), "tong_tri_gia": _dots(total), "tong_tri_gia_chu": consts["words"](round(total)),
        "tong_kien": _dots(kien), "sl_kien": sl_kien, "__kien_gop__": bool(consts.get("kien_gop")), "tong_net": _dots(num("net")), "tong_gross": _dots(num("gross")),
        "ten_hang": "; ".join(str(it.get("ten_sp") or "") for it in items), "ma_hang": "; ".join(str(it.get("ma_sp") or "") for it in items),
        "hs": ", ".join(dict.fromkeys(str(it.get("hs") or "") for it in items if it.get("hs"))),
        "dvt_chung": unit, "dvt_chung_hoa": unit[:1].upper() + unit[1:],
        "d": str(d.day), "m": str(d.month), "ngay_ngan": f"{d.day}/{d.month}/{d.year}", "han_tt": due.strftime("%d/%m/%Y"), "so_ngay_no": str(days),
        "tong_tri_gia_phay": f"{total:,.0f}",
        # số thật của các ô tổng: ô Excel chỉ chứa đúng một ô tổng thì ghi số (cộng/định dạng được), không ghi chữ
        "ngay_so": d.strftime("%d/%m/%Y"),
        "__so__": {"ngay_so": datetime.datetime(d.year, d.month, d.day), "tong_sl": num("qty"), "tong_tri_gia": total, "tong_kien": kien, "tong_net": num("net"), "tong_gross": num("gross")},
    }


_DIMS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:mm)?\s*[xX*]\s*(\d+(?:[.,]\d+)?)\s*(?:mm)?\s*[xX*]\s*(\d+(?:[.,]\d+)?)")
# Dung sai mặc định trên phiếu kiểm tra chất lượng (theo phiếu mẫu TSCO ống 77x3: 77±0,2 / 3±0,2 / 87±2)
QC_TOL = {"phi": "0,2", "day": "0,2", "dai": "2"}


def item_dims(it):
    """Quy cách (phi, dày, dài) của dòng hàng, dạng chữ như ghi trên mã/tên: mã '114x2.5x265' -> ('114', '2.5', '265'). () nếu không có."""
    for src in (it.get("ma_sp"), it.get("ten_sp")):
        m = _DIMS.search(re.sub(r"\([^)]*\)", " ", str(src or "")))
        if m:
            return tuple(d.replace(",", ".") for d in m.groups())
    return ()


def _num(t):
    v = float(t)
    return int(v) if v == int(v) else v


def qc_values(it, qc=None):
    """Ô của phiếu kiểm tra chất lượng cho một dòng hàng. `qc`: mục của mã hàng trong hồ sơ khách (`qcItems`):
    {"ma": mã trên phiếu, "phi"/"day"/"dai": dung sai dạng chữ '0,5'}; thiếu thì dùng mã hàng và dung sai mặc định."""
    qc = qc or {}
    out = {"ma_kt": str(qc.get("ma") or it.get("ma_sp") or "")}
    dims = item_dims(it)
    if dims:
        out["quy_cach"] = " x ".join(dims)
        for k, d in zip(("phi", "day", "dai"), dims):
            out[k] = _num(d)
            out["tc_" + k] = f"{d}±{qc.get(k) or QC_TOL[k]}"
    else:
        out.update({k: "" for k in ("quy_cach", "phi", "day", "dai", "tc_phi", "tc_day", "tc_dai")})
    return out


def item_values(rec, qc_items=None):
    """Giá trị ô theo dòng hàng, mỗi mặt hàng một dict. `qc_items`: {mã hàng: mục phiếu kiểm tra chất lượng} của khách (nếu có)."""
    out = []
    for i, it in enumerate(rec.get("items") or [], 1):
        qty, price = float(it.get("qty") or 0), float(it.get("price") or 0)
        out.append({"stt": i, "ma": it.get("ma_sp", ""), "ten": it.get("ten_sp", ""), "dvt": it.get("unit", ""), "sl": qty, "gia": price,
                    "thanh_tien": float(it.get("amount") or 0) or qty * price, "kg": float(it.get("kg") or 0), "kien": float(it.get("kien") or 0),
                    "net": float(it.get("net") or 0), "gross": float(it.get("gross") or 0), "hs_dong": it.get("hs", ""),
                    "bi": round(float(it.get("gross") or 0) - float(it.get("net") or 0), 6),
                    "dvt_hoa": str(it.get("unit") or "")[:1].upper() + str(it.get("unit") or "")[1:]})
        out[-1]["sl_phay"] = f"{qty:,.1f}"
        out[-1]["thanh_tien_phay"] = f"{out[-1]['thanh_tien']:,.1f}"
        out[-1].update(qc_values(it, (qc_items or {}).get(str(it.get("ma_sp") or ""))))
        if str(it.get("po") or "").strip():  # {{so_po}} nằm trong dòng hàng = số PO của chính dòng đó (lô nhiều PO)
            out[-1]["so_po"] = str(it["po"]).strip()
    return out


def _text(v):
    return _dots(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _formula_num(v):
    """Số đặt vào công thức Excel: dấu chấm thập phân, không ngăn nghìn (7.79, không phải '7,79')."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{float(v):.10g}"
    return str(v)


def _sub(text, vals, unknown, formula=None):
    if formula is None:
        formula = isinstance(text, str) and text.startswith("=")
    def repl(m):
        k = m.group(1)
        if k in vals:
            return _formula_num(vals[k]) if formula else _text(vals[k])
        unknown.add(k)
        return m.group(0)
    return _TOKEN.sub(repl, text)


def tokens_in(text):
    return set(_TOKEN.findall(text or ""))


# ------------------------------------------------------------------------------------------------ Word
_PARA = re.compile(r"<w:p[ >].*?</w:p>", re.S)
_ROW = re.compile(r"<w:tr[ >].*?</w:tr>", re.S)
_T = re.compile(r"(<w:t(?: [^>]*)?>)(.*?)(</w:t>)", re.S)


def _xml_unescape(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def _para_text(p_xml):
    return _xml_unescape("".join(m.group(2) for m in _T.finditer(p_xml)))


def _set_para(p_xml, text):
    first = [True]

    def repl(m):
        if first[0]:
            first[0] = False
            return '<w:t xml:space="preserve">' + escape(text) + "</w:t>"
        return m.group(1) + m.group(3)

    return _T.sub(repl, p_xml)


def _fill_para(p_xml, vals, unknown):
    txt = _para_text(p_xml)
    if "{{" not in txt:
        return p_xml
    runs = [_xml_unescape(m.group(2)) for m in _T.finditer(p_xml)]
    if sum(len(tokens_in(r)) for r in runs) == len(_TOKEN.findall(txt)):
        # mọi ô thay thế nằm gọn trong từng đoạn chữ (run): thay tại chỗ, giữ nguyên in đậm/nghiêng và ngắt dòng của đoạn
        it = iter(runs)

        def repl(m):
            r = next(it)
            return ('<w:t xml:space="preserve">' + escape(_sub(r, vals, unknown)) + m.group(3)) if "{{" in r else m.group(0)
        return _T.sub(repl, p_xml)
    return _set_para(p_xml, _sub(txt, vals, unknown))


def _has_item_token(text):
    return bool(tokens_in(text) & _ITEM_KEYS)


def _fill_docx_xml(xml, batch, rows, unknown):
    def do_row(m):
        row = m.group(0)
        if not _has_item_token(_para_text(row)):
            return _PARA.sub(lambda p: _fill_para(p.group(0), batch, unknown), row)
        return "".join(_PARA.sub(lambda p, v=dict(batch, **r): _fill_para(p.group(0), v, unknown), row) for r in rows) if rows else ""

    # 1) dòng bảng: có ô theo dòng hàng thì nhân lên cho mỗi mặt hàng
    parts, last = [], 0
    for m in _ROW.finditer(xml):
        parts.append(_outside(xml[last:m.start()], batch, rows, unknown))
        parts.append(do_row(m))
        last = m.end()
    parts.append(_outside(xml[last:], batch, rows, unknown))
    return "".join(parts)


def _outside(seg, batch, rows, unknown):
    """Đoạn văn ngoài bảng: đoạn có ô theo dòng hàng được nhân lên cho mỗi mặt hàng."""
    def do_p(m):
        p = m.group(0)
        if _has_item_token(_para_text(p)):
            return "".join(_fill_para(p, dict(batch, **r), unknown) for r in rows) if rows else ""
        return _fill_para(p, batch, unknown)
    return _PARA.sub(do_p, seg)


def fill_docx(data, batch, rows):
    """Điền ô thay thế vào file Word (nội dung bytes). Trả (bytes mới, [ô lạ không nhận ra])."""
    unknown = set()
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            raw = src.read(item.filename)
            if item.filename == "word/document.xml" or re.fullmatch(r"word/(header|footer)\d*\.xml", item.filename):
                raw = _fill_docx_xml(raw.decode("utf-8"), batch, rows, unknown).encode("utf-8")
            dst.writestr(item, raw)
    return out.getvalue(), sorted(unknown)


# ------------------------------------------------------------------------------------------------ Excel
def _copy_row_style(ws, src_row, dst_row):
    for c in ws[src_row]:
        d = ws.cell(row=dst_row, column=c.column)
        if c.has_style:
            d._style = copy(c._style)
    if ws.row_dimensions[src_row].height:
        ws.row_dimensions[dst_row].height = ws.row_dimensions[src_row].height


_CELL_REF = re.compile(r"(?<![A-Za-z_\d!.$'\"])(\$?[A-Z]{1,3}\$?)(\d+)(?::(\$?[A-Z]{1,3}\$?)(\d+))?(?![\d(A-Za-z_!])")


def shift_formula_rows(formula, r, extra):
    """Công thức ở NGOÀI dòng hàng mẫu `r` khi chèn thêm `extra` dòng ngay dưới dòng r: ô dưới dòng r dời xuống,
    vùng kết thúc đúng ở dòng r (VD tổng SUM(D11:D11)) được kéo dài thêm cho hết các dòng hàng mới."""
    def repl(m):
        a = int(m.group(2))
        if m.group(3) is None:
            return f"{m.group(1)}{a + extra if a > r else a}"
        b = int(m.group(4))
        a2 = a + extra if a > r else a
        b2 = b + extra if b > r or (b == r and a <= r) else b
        return f"{m.group(1)}{a2}:{m.group(3)}{b2}"
    return _CELL_REF.sub(repl, formula)


def _is_formula(v):
    return isinstance(v, str) and v.startswith("=")


def _shift_print_rows(ws, r, extra):
    """Vùng in và dòng tiêu đề in lặp: dòng dưới dòng mẫu r dời xuống `extra` dòng, vùng chứa dòng r kéo dài thêm."""
    pa = re.search(r"\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)", str(ws.print_area or ""))
    if pa:
        a, b = int(pa.group(2)), int(pa.group(4))
        ws.print_area = f"{pa.group(1)}{a + extra if a > r else a}:{pa.group(3)}{b + extra if b >= r else b}"
    t = re.search(r"\$?(\d+):\$?(\d+)", str(ws.print_title_rows or ""))
    if t:
        a, b = int(t.group(1)), int(t.group(2))
        ws.print_title_rows = f"{a + extra if a > r else a}:{b + extra if b >= r else b}"


_OLD_PAY = re.compile(r"(=\$?[A-Z]{1,2}\$?\d+)\+45")  # ngày + 45: số ngày nợ đánh dấu khi đổi chứng từ dựng sẵn thành form


def fill_xlsx(data, batch, rows):
    """Điền ô thay thế vào file Excel (bytes). Dòng có ô theo dòng hàng được nhân lên cho mỗi mặt hàng (chép cả công thức, ô gộp,
    chữ cố định của dòng mẫu; công thức tổng bên dưới tự kéo dài theo số dòng). Trả (bytes mới, [ô lạ])."""
    import openpyxl
    from openpyxl.formula.translate import Translator
    from openpyxl.utils import get_column_letter
    wb = openpyxl.load_workbook(io.BytesIO(data))
    unknown = set()
    for ws in wb.worksheets:
        qty_ranges = []  # (cột, dòng đầu, dòng cuối) của cột {{sl}} sau khi nhân dòng: dùng cho công thức tổng kiện
        # dòng mẫu của bảng hàng (từ dưới lên để chèn dòng không làm lệch chỉ số)
        item_rows = [r for r in range(ws.max_row, 0, -1) if any(isinstance(c.value, str) and _has_item_token(c.value) for c in ws[r])]
        for r in item_rows:
            extra = max(len(rows), 1) - 1
            tpl = [(c.column, c.value) for c in ws[r]]
            row_merges = [(m.min_col, m.max_col) for m in ws.merged_cells.ranges if m.min_row == m.max_row == r]
            if extra > 0:
                for row in ws.iter_rows():
                    for c in row:
                        if c.row != r and _is_formula(c.value):
                            c.value = shift_formula_rows(c.value, r, extra)
                # ô gộp nằm dưới dòng mẫu dời xuống; ô gộp nhiều dòng chứa dòng mẫu thì kéo dài thêm
                merged = [(m.min_row + (extra if m.min_row > r else 0), m.min_col, m.max_row + extra, m.max_col)
                          for m in list(ws.merged_cells.ranges) if m.max_row > r and not (m.min_row == m.max_row == r)]
                for m in list(ws.merged_cells.ranges):
                    if m.max_row > r and not (m.min_row == m.max_row == r):
                        ws.unmerge_cells(str(m))
                # chiều cao / ẩn của các dòng dưới dòng mẫu dời theo (openpyxl không tự dời): không dời thì dòng chữ 2 hàng
                # rơi vào dòng cao 15 và bị cắt nửa chữ khi in
                dims = {k: (d.height, d.hidden) for k, d in list(ws.row_dimensions.items()) if k > r}
                for k in dims:
                    del ws.row_dimensions[k]
                ws.insert_rows(r + 1, extra)
                for k, (h, hid) in dims.items():
                    if h:
                        ws.row_dimensions[k + extra].height = h
                    if hid:
                        ws.row_dimensions[k + extra].hidden = True
                for mr0, mc0, mr1, mc1 in merged:
                    ws.merge_cells(start_row=mr0, start_column=mc0, end_row=mr1, end_column=mc1)
                _shift_print_rows(ws, r, extra)
                for k in range(1, extra + 1):
                    _copy_row_style(ws, r, r + k)
                    for c0, c1 in row_merges:
                        ws.merge_cells(start_row=r + k, start_column=c0, end_row=r + k, end_column=c1)
            qty_ranges = [(c, a + extra, b + extra) for c, a, b in qty_ranges]  # bảng hàng bên dưới (đã nhân trước) bị đẩy xuống
            qty_ranges += [(get_column_letter(col), r, r + extra) for col, val in tpl
                           if isinstance(val, str) and (_TOKEN.fullmatch(val.strip()) or [None, None])[1] == "sl"]
            # cả bảng cùng một số hóa đơn: ô {{so_hd}} dòng đầu ghi số, dòng dưới là công thức theo ô đầu (sửa ô đầu là đổi theo)
            one_hd = len({str(dict(batch, **row).get("so_hd", "")) for row in (rows or [{}])}) == 1
            for k in range(max(len(rows), 1)):
                v = dict(batch, **(rows[k] if rows else {}))
                for col, val in tpl:
                    cell = ws.cell(row=r + k, column=col)
                    if isinstance(val, str) and "{{" in val:
                        m = _TOKEN.fullmatch(val.strip())
                        so = batch.get("__so__") or {}
                        if _is_formula(val):  # công thức có ô thay thế (VD hạn thanh toán =C9+{{so_ngay_no}}): điền số rồi dời theo dòng
                            f = _sub(val, v, unknown)
                            addr = get_column_letter(col)
                            try:
                                cell.value = Translator(f, origin=f"{addr}{r}").translate_formula(f"{addr}{r + k}") if k else f
                            except Exception:  # noqa: BLE001 - công thức lạ: chép nguyên
                                cell.value = f
                        elif m and m.group(1) == "so_hd" and one_hd:
                            a = f"${get_column_letter(col)}${r}"
                            cell.value = str(v.get("so_hd") or "") if k == 0 else f'=IF({a}="","",{a})'
                            cell.number_format = "@" if k == 0 else "General"
                        elif m and m.group(1) in v and isinstance(v[m.group(1)], (int, float)):
                            cell.value = v[m.group(1)]  # ô chỉ chứa một ô số: ghi số thật để cộng được
                        elif m and m.group(1) in so and not (rows and m.group(1) in rows[k]):
                            cell.value = so[m.group(1)]
                        else:
                            cell.value = _sub(val, v, unknown)
                    elif _is_formula(val) and _OLD_PAY.fullmatch(val.replace(" ", "")) and batch.get("so_ngay_no"):
                        # form làm trước 18/11 còn ghi cứng hạn thanh toán =C9+45 (45 là số ngày của lô mẫu): dùng số ngày nợ của lô
                        f = _OLD_PAY.sub(lambda mm: mm.group(1) + "+" + str(batch["so_ngay_no"]), val.replace(" ", ""))
                        addr = get_column_letter(col)
                        cell.value = Translator(f, origin=f"{addr}{r}").translate_formula(f"{addr}{r + k}") if k else f
                    elif k and _is_formula(val):  # công thức của dòng mẫu: dời theo dòng mới (=E13*F13 -> =E14*F14)
                        addr = get_column_letter(col)
                        try:
                            cell.value = Translator(val, origin=f"{addr}{r}").translate_formula(f"{addr}{r + k}")
                        except Exception:  # noqa: BLE001 - công thức lạ: chép nguyên
                            cell.value = val
                    elif k and val is not None:
                        try:
                            cell.value = val  # chữ cố định của dòng mẫu (VD "Chiếc")
                        except (AttributeError, ValueError):  # ô bị gộp
                            pass
        so = batch.get("__so__") or {}
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and "{{" in c.value:
                    m = _TOKEN.fullmatch(c.value.strip())
                    if _is_formula(c.value) and "sl_kien" in tokens_in(c.value) and not batch.get("sl_kien"):
                        c.value = so.get("tong_kien", 0)  # định mức khác nhau giữa các dòng: ghi số kiện phần mềm tính
                    elif m and m.group(1) == "tong_kien" and batch.get("__kien_gop__") and batch.get("sl_kien") and len(qty_ranges) == 1:
                        col, a, b = qty_ranges[0]  # form cũ ghi số: đổi thành công thức tổng SL / SL mỗi kiện
                        c.value = f"=ROUNDUP(SUM({col}{a}:{col}{b})/{batch['sl_kien']},0)"
                    else:
                        c.value = so[m.group(1)] if m and m.group(1) in so else _sub(c.value, batch, unknown)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), sorted(unknown)


def _copy_images(src, dst):
    """Chép ảnh (logo, ảnh sản phẩm...) của sheet mẫu sang sheet chép (openpyxl copy_worksheet không chép ảnh)."""
    from copy import deepcopy
    from openpyxl.drawing.image import Image
    for img in getattr(src, "_images", []):
        raw = img._data()  # _data() đóng luồng của ảnh gốc: gắn lại bản bytes để lúc lưu file vẫn đọc được
        img.ref = io.BytesIO(raw)
        new = Image(io.BytesIO(raw))
        new.width, new.height = img.width, img.height
        new.anchor = deepcopy(img.anchor)
        dst.add_image(new)


def fill_xlsx_per_item(data, batch, rows):
    """Form MỖI MÃ HÀNG MỘT PHIẾU (VD phiếu kiểm tra chất lượng TSCO): sheet đầu của file là phiếu mẫu; mỗi mặt hàng một sheet chép
    từ phiếu mẫu (giữ ô gộp, định dạng, ảnh, thiết lập in), ô {{...}} điền số liệu của chính mặt hàng đó. Tên sheet = mã trên phiếu.
    Trả (bytes mới, [ô lạ])."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    tpl = wb.worksheets[0]
    for ws in wb.worksheets[1:]:
        wb.remove(ws)
    rows = rows or [{}]
    sheets = [tpl]
    for _ in rows[1:]:
        ws = wb.copy_worksheet(tpl)
        _copy_images(tpl, ws)
        ws.page_setup.orientation, ws.page_setup.paperSize = tpl.page_setup.orientation, tpl.page_setup.paperSize
        ws.page_margins = copy(tpl.page_margins)
        ws.print_options.horizontalCentered = tpl.print_options.horizontalCentered
        ws.sheet_properties.pageSetUpPr = copy(tpl.sheet_properties.pageSetUpPr)
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = tpl.page_setup.fitToWidth, tpl.page_setup.fitToHeight
        sheets.append(ws)
    unknown, so, used = set(), batch.get("__so__") or {}, set()
    for ws, row in zip(sheets, rows):
        v = dict(batch, **row)
        for r in ws.iter_rows():
            for c in r:
                if isinstance(c.value, str) and "{{" in c.value:
                    m = _TOKEN.fullmatch(c.value.strip())
                    if m and m.group(1) in row and isinstance(row[m.group(1)], (int, float)) and not isinstance(row[m.group(1)], bool):
                        c.value = row[m.group(1)]  # ô chỉ chứa một ô số: ghi số thật
                    elif m and m.group(1) in so and m.group(1) not in row:
                        c.value = so[m.group(1)]
                    else:
                        c.value = _sub(c.value, v, unknown)
        title = re.sub(r"[\\/*?:\[\]]", "-", str(row.get("ma_kt") or row.get("ma") or ws.title))[:31] or ws.title
        base, n = title, 2
        while title in used:  # hai dòng cùng mã: thêm (2), (3)
            title = f"{base[:27]} ({n})"
            n += 1
        used.add(title)
        ws.title = title
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), sorted(unknown)


def fill(ext, data, batch, rows):
    ext = ext.lower().lstrip(".")
    if ext == "docx":
        return fill_docx(data, batch, rows)
    if ext in ("xlsx", "xlsm"):
        return fill_xlsx(data, batch, rows)
    raise ValueError("Mẫu riêng chỉ nhận file Word (.docx) hoặc Excel (.xlsx).")


def template_tokens(ext, data):
    """Các ô thay thế có trong file mẫu (để báo người dùng ô nào nhận, ô nào lạ)."""
    ext = ext.lower().lstrip(".")
    found = set()
    if ext == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                if n == "word/document.xml" or re.fullmatch(r"word/(header|footer)\d*\.xml", n):
                    for p in _PARA.findall(z.read(n).decode("utf-8")):
                        found |= tokens_in(_para_text(p))
    elif ext in ("xlsx", "xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data))
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str):
                        found |= tokens_in(c.value)
    else:
        raise ValueError("Mẫu riêng chỉ nhận file Word (.docx) hoặc Excel (.xlsx).")
    known = {k for k, _ in TOKENS} | _ITEM_KEYS
    return sorted(found & known), sorted(found - known)


def preview(ext, data, max_rows=80, max_cols=14):
    """Xem mẫu: Word -> {"kind": "text", "text": ...} (đoạn văn, dòng bảng nối bằng ' | '); Excel -> {"kind": "grid", "rows": [[...]]} của trang đầu."""
    ext = ext.lower().lstrip(".")
    if ext == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        lines = []
        for m in re.finditer(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>", xml, re.S):
            blk = m.group(0)
            if blk.startswith("<w:tbl>"):
                for row in _ROW.findall(blk):
                    cells = re.findall(r"<w:tc>.*?</w:tc>", row, re.S)
                    lines.append(" | ".join(_para_text(c).strip() for c in cells))
            else:
                lines.append(_para_text(blk))
        return {"kind": "text", "text": "\n".join(lines)}
    if ext in ("xlsx", "xlsm"):
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(data)).worksheets[0]
        rows = [["" if c.value is None else str(c.value) for c in row[:max_cols]] for row in ws.iter_rows(max_row=max_rows)]
        return {"kind": "grid", "rows": rows, "sheet": ws.title}
    raise ValueError("Chỉ xem được file Word (.docx) hoặc Excel (.xlsx).")


def replace_text(ext, data, find, token):
    """Công cụ sửa mẫu: đổi một đoạn chữ (hoặc số) đang có trong mẫu thành ô {{token}}. Trả (bytes mới, số chỗ đã đổi).
    Word: đoạn có chữ đó được dựng lại theo định dạng của chữ đầu tiên trong đoạn. Excel: ô chứa chữ đó (hoặc ô số bằng đúng số đó)."""
    find, token = str(find or ""), str(token or "").strip("{} ")
    if not find.strip() or not re.fullmatch(r"[A-Za-z0-9_]+", token):
        raise ValueError("Cần nhập chữ cần đổi và chọn ô thay thế.")
    ext = ext.lower().lstrip(".")
    new = "{{" + token + "}}"
    count = 0
    if ext == "docx":
        src = zipfile.ZipFile(io.BytesIO(data))
        xml = src.read("word/document.xml").decode("utf-8")

        def repl(m):
            nonlocal count
            p = m.group(0)
            txt = _para_text(p)
            if find in txt:
                count += txt.count(find)
                return _set_para(p, txt.replace(find, new))
            return p

        out_xml = _PARA.sub(repl, xml)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                dst.writestr(item, out_xml.encode("utf-8") if item.filename == "word/document.xml" else src.read(item.filename))
        return out.getvalue(), count
    if ext in ("xlsx", "xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data))
        digits = re.sub(r"[.,\s]", "", find)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    v = c.value
                    if isinstance(v, str) and find in v:
                        count += v.count(find)
                        c.value = v.replace(find, new)
                    elif isinstance(v, (int, float)) and not isinstance(v, bool) and digits.isdigit() and str(int(v)) == digits and float(v) == int(v):
                        count += 1
                        c.value = new
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue(), count
    raise ValueError("Chỉ sửa được file Word (.docx) hoặc Excel (.xlsx).")


# ------------------------------------------------------------------------------------------------ sửa nội dung ngay trong phần mềm
def docx_paragraphs(data):
    """Chữ của từng đoạn trong thân file Word (kể cả đoạn trong ô bảng), theo thứ tự trong file."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return [_para_text(p) for p in _PARA.findall(xml)]


def set_docx_paragraphs(data, texts):
    """`texts`: {số thứ tự đoạn (từ 0): chữ mới}. Đoạn được đổi dồn chữ vào đoạn chữ đầu (giữ định dạng của nó); đoạn khác giữ nguyên."""
    src = zipfile.ZipFile(io.BytesIO(data))
    xml = src.read("word/document.xml").decode("utf-8")
    idx = [0]

    def repl(m):
        i = idx[0]
        idx[0] += 1
        if i not in texts or texts[i] == _para_text(m.group(0)):
            return m.group(0)
        p = m.group(0)
        if not _T.search(p):  # đoạn trống: thêm một đoạn chữ
            return p.replace("</w:p>", '<w:r><w:t xml:space="preserve">' + escape(texts[i]) + "</w:t></w:r></w:p>")
        return _set_para(p, texts[i])

    out_xml = _PARA.sub(repl, xml)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, out_xml.encode("utf-8") if item.filename == "word/document.xml" else src.read(item.filename))
    return out.getvalue()


def xlsx_cells(data, max_rows=300, max_cols=40):
    """Lưới ô của từng sheet Excel để sửa: [{"sheet", "rows": [[chữ hiện trong ô, ...]], "merged": {(dòng, cột) bị gộp vào ô khác}}].
    Công thức hiện nguyên dạng =..., số hiện như Excel lưu (không định dạng)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    out = []
    for ws in wb.worksheets:
        nr, nc = min(ws.max_row, max_rows), min(ws.max_column, max_cols)
        hidden = set()
        for m in ws.merged_cells.ranges:
            for rr in range(m.min_row, m.max_row + 1):
                for cc in range(m.min_col, m.max_col + 1):
                    if (rr, cc) != (m.min_row, m.min_col):
                        hidden.add((rr, cc))
        rows = []
        for r in range(1, nr + 1):
            rows.append(["" if ws.cell(r, c).value is None else _cell_text(ws.cell(r, c).value) for c in range(1, nc + 1)])
        out.append({"sheet": ws.title, "rows": rows, "merged": hidden})
    return out


def _cell_text(v):
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def set_xlsx_cells(data, changes):
    """`changes`: {(tên sheet, dòng, cột): chữ mới} (dòng/cột từ 1). Chữ là số thì ghi số, bắt đầu bằng = thì ghi công thức, rỗng thì xóa ô.
    Định dạng ô, ô gộp, độ rộng cột, thiết lập in giữ nguyên."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    for (sheet, r, c), text in changes.items():
        ws = wb[sheet]
        cell = ws.cell(r, c)
        if type(cell).__name__ == "MergedCell":
            continue
        t = str(text if text is not None else "")
        if t == "":
            cell.value = None
        elif re.fullmatch(r"-?\d+", t.strip()):
            cell.value = int(t.strip())
        elif re.fullmatch(r"-?\d*\.\d+", t.strip()):
            cell.value = float(t.strip())
        else:
            cell.value = t
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()

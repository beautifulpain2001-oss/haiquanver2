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
    ("ngay", "Ngày chứng từ dd/mm/yyyy"), ("dd", "Ngày (2 số)"), ("mm", "Tháng (2 số)"), ("yyyy", "Năm"),
    ("tong_sl", "Tổng số lượng"), ("tong_tri_gia", "Tổng trị giá"), ("tong_tri_gia_chu", "Tổng trị giá bằng chữ"), ("tong_kien", "Tổng số kiện"),
    ("tong_net", "Tổng trọng lượng tịnh"), ("tong_gross", "Tổng trọng lượng cả bì"),
    ("ten_hang", "Tên các mặt hàng (nối bằng ; )"), ("ma_hang", "Mã các mặt hàng"), ("hs", "Mã HS các mặt hàng"),
]
ITEM_TOKENS = [
    ("stt", "Số thứ tự"), ("ma", "Mã hàng"), ("ten", "Tên hàng"), ("dvt", "Đơn vị tính"), ("sl", "Số lượng"), ("gia", "Đơn giá"),
    ("thanh_tien", "Thành tiền"), ("kg", "kg/chiếc"), ("kien", "Số kiện"), ("net", "Trọng lượng tịnh"), ("gross", "Trọng lượng cả bì"), ("hs_dong", "Mã HS"),
]
_ITEM_KEYS = {k for k, _ in ITEM_TOKENS}
_TOKEN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def _dots(x):
    """Số có dấu chấm ngăn nghìn kiểu Việt Nam: 21212 -> '21.212'; 0,5 -> '0,5'."""
    x = float(x or 0)
    s = f"{x:,.3f}".rstrip("0").rstrip(".") if x != int(x) else f"{int(x):,}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def batch_values(rec, prof, consts):
    """Giá trị các ô chung của lô. `consts`: {name, addr, mst, dmy, words} từ phần mềm (tên bên bán, hàm đổi ngày, đọc số thành chữ)."""
    items = rec.get("items") or []
    d = consts["date"](rec.get("docDate"))
    total = sum(float(it.get("amount") or 0) or float(it.get("qty") or 0) * float(it.get("price") or 0) for it in items)
    num = lambda k: sum(float(it.get(k) or 0) for it in items)
    return {
        "khach_ten": prof.get("name", ""), "khach_dia_chi": prof.get("addr", ""), "khach_mst": prof.get("mst", ""),
        "ben_ban_ten": consts["name"], "ben_ban_dia_chi": consts["addr"].rstrip("."), "ben_ban_mst": consts["mst"],
        "so_po": rec.get("poNumber", ""), "ngay_po": rec.get("poDate", ""), "so_pxk": rec.get("pxkNo", ""), "so_hd": rec.get("hdNo", ""), "so_tk": rec.get("tkNo", ""),
        "ngay": d.strftime("%d/%m/%Y"), "dd": d.strftime("%d"), "mm": d.strftime("%m"), "yyyy": d.strftime("%Y"),
        "tong_sl": _dots(num("qty")), "tong_tri_gia": _dots(total), "tong_tri_gia_chu": consts["words"](round(total)),
        "tong_kien": _dots(num("kien")), "tong_net": _dots(num("net")), "tong_gross": _dots(num("gross")),
        "ten_hang": "; ".join(str(it.get("ten_sp") or "") for it in items), "ma_hang": "; ".join(str(it.get("ma_sp") or "") for it in items),
        "hs": ", ".join(dict.fromkeys(str(it.get("hs") or "") for it in items if it.get("hs"))),
    }


def item_values(rec):
    """Giá trị ô theo dòng hàng, mỗi mặt hàng một dict."""
    out = []
    for i, it in enumerate(rec.get("items") or [], 1):
        qty, price = float(it.get("qty") or 0), float(it.get("price") or 0)
        out.append({"stt": i, "ma": it.get("ma_sp", ""), "ten": it.get("ten_sp", ""), "dvt": it.get("unit", ""), "sl": qty, "gia": price,
                    "thanh_tien": float(it.get("amount") or 0) or qty * price, "kg": float(it.get("kg") or 0), "kien": float(it.get("kien") or 0),
                    "net": float(it.get("net") or 0), "gross": float(it.get("gross") or 0), "hs_dong": it.get("hs", "")})
    return out


def _text(v):
    return _dots(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def _sub(text, vals, unknown):
    def repl(m):
        k = m.group(1)
        if k in vals:
            return _text(vals[k])
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


def fill_xlsx(data, batch, rows):
    """Điền ô thay thế vào file Excel (bytes). Dòng có ô theo dòng hàng được nhân lên cho mỗi mặt hàng. Trả (bytes mới, [ô lạ])."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    unknown = set()
    for ws in wb.worksheets:
        # dòng mẫu của bảng hàng (từ dưới lên để chèn dòng không làm lệch chỉ số)
        item_rows = [r for r in range(ws.max_row, 0, -1) if any(isinstance(c.value, str) and _has_item_token(c.value) for c in ws[r])]
        for r in item_rows:
            extra = max(len(rows), 1) - 1
            if extra > 0:
                merged = [(m.min_row, m.min_col, m.max_row, m.max_col) for m in list(ws.merged_cells.ranges) if m.min_row > r]
                for m in list(ws.merged_cells.ranges):
                    if m.min_row > r:
                        ws.unmerge_cells(str(m))
                ws.insert_rows(r + 1, extra)
                for mr0, mc0, mr1, mc1 in merged:
                    ws.merge_cells(start_row=mr0 + extra, start_column=mc0, end_row=mr1 + extra, end_column=mc1)
                for k in range(1, extra + 1):
                    _copy_row_style(ws, r, r + k)
            tpl = [(c.column, c.value) for c in ws[r]]
            for k in range(max(len(rows), 1)):
                v = dict(batch, **(rows[k] if rows else {}))
                for col, val in tpl:
                    if isinstance(val, str) and "{{" in val:
                        m = _TOKEN.fullmatch(val.strip())
                        if m and m.group(1) in v and isinstance(v[m.group(1)], (int, float)):
                            ws.cell(row=r + k, column=col).value = v[m.group(1)]  # ô chỉ chứa một ô số: ghi số thật để cộng được
                        else:
                            ws.cell(row=r + k, column=col).value = _sub(val, v, unknown)
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and "{{" in c.value:
                    c.value = _sub(c.value, batch, unknown)
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

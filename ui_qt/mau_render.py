"""Vẽ HÌNH ẢNH của mẫu chứng từ (Word .docx / Excel .xlsx) ngay trong phần mềm, không cần cài Word/Excel/LibreOffice.

Excel: vẽ lưới theo độ rộng cột, chiều cao dòng, ô gộp, viền, màu nền, chữ đậm/nghiêng/cỡ chữ, căn lề, xuống dòng.
Word: dựng lại các đoạn và bảng (đậm, nghiêng, cỡ chữ, căn lề) trên trang A4.
Đây là hình gần đúng để nhận ra mẫu và soát ô {{...}} (được tô vàng); muốn xem đúng 100% thì mở bằng Word/Excel.
"""

import io
import re
import zipfile
from html import escape

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QTextDocument

_TOKEN = re.compile(r"\{\{\s*[A-Za-z0-9_]+\s*\}\}")
_HL = "#FDE68A"
MAX_ROWS, MAX_COLS = 70, 18


# ------------------------------------------------------------------------------------------------ Excel
def _col_px(ws, c):
    from openpyxl.utils import get_column_letter
    d = ws.column_dimensions.get(get_column_letter(c))
    if d is not None and d.hidden:
        return 0
    w = d.width if d is not None and d.width else 8.43
    return max(6, int(w * 7 + 5))


def _row_px(ws, r):
    d = ws.row_dimensions.get(r)
    if d is not None and d.hidden:
        return 0
    return max(8, int((d.height if d is not None and d.height else 15) * 96 / 72))


def _argb(color, default=None):
    try:
        rgb = color.rgb if color is not None and color.type == "rgb" else None
    except Exception:  # noqa: BLE001
        rgb = None
    if isinstance(rgb, str) and len(rgb) in (6, 8) and rgb not in ("00000000",):
        return QColor("#" + rgb[-6:])
    return default


def render_xlsx(data, width=900):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb.worksheets[0]
    last_r = last_c = 1
    for row in ws.iter_rows(max_row=MAX_ROWS, max_col=MAX_COLS):
        for c in row:
            if c.value not in (None, ""):
                last_r, last_c = max(last_r, c.row), max(last_c, c.column)
    merged = {}
    for m in ws.merged_cells.ranges:
        if m.min_row <= MAX_ROWS and m.min_col <= MAX_COLS:
            merged[(m.min_row, m.min_col)] = (min(m.max_row, MAX_ROWS), min(m.max_col, MAX_COLS))
            last_r, last_c = max(last_r, min(m.max_row, MAX_ROWS)), max(last_c, min(m.max_col, MAX_COLS))
    last_r, last_c = min(last_r, MAX_ROWS), min(last_c, MAX_COLS)
    xs, ys = [0], [0]
    for c in range(1, last_c + 1):
        xs.append(xs[-1] + _col_px(ws, c))
    for r in range(1, last_r + 1):
        ys.append(ys[-1] + _row_px(ws, r))
    inner = (xs[-1] + 2, ys[-1] + 2)
    img = QImage(inner[0], inner[1], QImage.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    inside = set()
    for (r0, c0), (r1, c1) in merged.items():
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if (r, c) != (r0, c0):
                    inside.add((r, c))

    def rect(r, c):
        r1, c1 = merged.get((r, c), (r, c))
        return QRectF(xs[c - 1] + 1, ys[r - 1] + 1, xs[c1] - xs[c - 1], ys[r1] - ys[r - 1])

    for r in range(1, last_r + 1):
        for c in range(1, last_c + 1):
            if (r, c) in inside:
                continue
            cell = ws.cell(row=r, column=c)
            rc = rect(r, c)
            val = cell.value
            text = "" if val is None else (str(val) if not isinstance(val, float) or val != int(val) else str(int(val)))
            token = bool(_TOKEN.search(text))
            fill = _argb(cell.fill.fgColor) if cell.fill is not None and cell.fill.fill_type == "solid" else None
            if token:
                p.fillRect(rc, QColor(_HL))
            elif fill is not None:
                p.fillRect(rc, fill)
            if text:
                f = QFont(cell.font.name or "Times New Roman")
                f.setPixelSize(max(7, int((cell.font.sz or 11) * 96 / 72)))
                f.setBold(bool(cell.font.b))
                f.setItalic(bool(cell.font.i))
                p.setFont(f)
                p.setPen(_argb(cell.font.color, QColor("#111827")) if not token else QColor("#92400E"))
                h = {"center": Qt.AlignHCenter, "right": Qt.AlignRight, "centerContinuous": Qt.AlignHCenter}.get(cell.alignment.horizontal, Qt.AlignLeft)
                v = {"top": Qt.AlignTop, "bottom": Qt.AlignBottom}.get(cell.alignment.vertical, Qt.AlignVCenter)
                flags = h | v | (Qt.TextWordWrap if cell.alignment.wrap_text or "\n" in text else 0)
                p.setClipRect(rc)
                p.drawText(rc.adjusted(3, 1, -3, -1), int(flags), text)
                p.setClipping(False)
            b = cell.border
            pen = QPen(QColor("#111827"), 1)
            p.setPen(pen)
            for side, line in ((b.left, (rc.left(), rc.top(), rc.left(), rc.bottom())), (b.right, (rc.right(), rc.top(), rc.right(), rc.bottom())),
                               (b.top, (rc.left(), rc.top(), rc.right(), rc.top())), (b.bottom, (rc.left(), rc.bottom(), rc.right(), rc.bottom()))):
                if side is not None and side.style:
                    p.drawLine(*[int(x) for x in line])
    p.end()
    return img.scaledToWidth(width, Qt.SmoothTransformation) if img.width() > width else img


# ------------------------------------------------------------------------------------------------ Word
_PARA = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>", re.S)
_ROW = re.compile(r"<w:tr[ >].*?</w:tr>", re.S)
_CELL = re.compile(r"<w:tc>.*?</w:tc>", re.S)
_P = re.compile(r"<w:p[ >].*?</w:p>", re.S)
_RUN = re.compile(r"<w:r[ >].*?</w:r>", re.S)


def _unesc(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def _run_html(run):
    texts = []
    for m in re.finditer(r"<w:t(?: [^>]*)?>(.*?)</w:t>|<w:tab/>|<w:br/>", run, re.S):
        if m.group(0).startswith("<w:tab"):
            texts.append("&nbsp;" * 8)
        elif m.group(0).startswith("<w:br"):
            texts.append("<br>")
        else:
            texts.append(_TOKEN.sub(lambda t: f'<span style="background:{_HL}">{escape(t.group(0))}</span>', escape(_unesc(m.group(1)))).replace("  ", "&nbsp; "))
    body = "".join(texts)
    if not body:
        return ""
    rpr = re.search(r"<w:rPr>.*?</w:rPr>", run, re.S)
    rp = rpr.group(0) if rpr else ""
    style = []
    if re.search(r'<w:b(?: w:val="(?:1|true|on)")?/>', rp):
        style.append("font-weight:bold")
    if re.search(r'<w:i(?: w:val="(?:1|true|on)")?/>', rp):
        style.append("font-style:italic")
    sz = re.search(r'<w:sz w:val="(\d+)"', rp)
    if sz:
        style.append(f"font-size:{int(sz.group(1)) / 2:g}pt")
    return f'<span style="{";".join(style)}">{body}</span>' if style else body


def _para_html(p):
    ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, re.S)
    pp = ppr.group(0) if ppr else ""
    jc = re.search(r'<w:jc w:val="(\w+)"', pp)
    align = {"center": "center", "right": "right", "both": "justify", "left": "left", "start": "left", "end": "right"}.get(jc.group(1) if jc else "", "left")
    heading = "Heading" in (re.search(r'<w:pStyle w:val="([^"]+)"', pp).group(1) if re.search(r'<w:pStyle w:val="([^"]+)"', pp) else "")
    inner = "".join(_run_html(r) for r in _RUN.findall(p))
    if heading and inner:
        inner = f'<b>{inner}</b>'
    return f'<p style="margin:0 0 2px 0;text-align:{align}">{inner or "&nbsp;"}</p>'


def docx_html(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for m in _PARA.finditer(xml):
        blk = m.group(0)
        if blk.startswith("<w:tbl>"):
            rows = []
            for row in _ROW.findall(blk):
                cells = "".join(f'<td style="border:1px solid #111;padding:3px">{"".join(_para_html(p) for p in _P.findall(c))}</td>' for c in _CELL.findall(row))
                rows.append(f"<tr>{cells}</tr>")
            out.append(f'<table width="100%" cellspacing="0" cellpadding="3" style="border-collapse:collapse">{"".join(rows)}</table>')
        else:
            out.append(_para_html(blk))
    return "".join(out)


def render_docx(data, width=900):
    doc = QTextDocument()
    f = QFont("Times New Roman")
    f.setPointSizeF(12)
    doc.setDefaultFont(f)
    margin = 60
    page_w = 794
    doc.setTextWidth(page_w - 2 * margin)
    doc.setHtml(f'<div style="font-family:\'Times New Roman\',serif;font-size:12pt">{docx_html(data)}</div>')
    h = max(int(doc.size().height()) + 2 * margin, int(page_w * 1.2))
    img = QImage(page_w, h, QImage.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.translate(margin, margin)
    doc.drawContents(p)
    p.end()
    return img.scaledToWidth(width, Qt.SmoothTransformation) if page_w > width else img


def render_template(ext, data, width=900):
    """Hình ảnh của mẫu (QImage). Ném ValueError nếu không phải .docx/.xlsx."""
    ext = ext.lower().lstrip(".")
    if ext == "docx":
        return render_docx(data, width)
    if ext in ("xlsx", "xlsm"):
        return render_xlsx(data, width)
    raise ValueError("Chỉ vẽ được file Word (.docx) hoặc Excel (.xlsx).")

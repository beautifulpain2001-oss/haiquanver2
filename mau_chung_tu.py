"""Chứng từ theo FILE MẪU CỦA KHÁCH (Best…): giữ nguyên định dạng file mẫu (cỡ cột, phông, khung, in ấn),
chỉ thay số liệu và nhân/bớt số dòng hàng. Không dùng widget; nhận `core` = hongthien_desktop_app.

Một file mẫu = một sheet mẫu đã có sẵn vài dòng hàng. "Vùng lặp" là các hàng của mẫu được nhân lên bằng số dòng thật
(dòng hàng, dòng "Số ĐĐH" theo PO). Hàng nằm sau vùng lặp được đẩy xuống, công thức tổng được sửa lại cho đúng vùng mới.
"""

import copy
import datetime
import os
import re

from openpyxl.formula.translate import Translator
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

DOCS = ("pkl", "pack", "pgh", "dccn", "dntt", "bbgh", "po")  # tên file mẫu: <mã khách>/<doc>.xlsx

_REF = re.compile(r"(?<![A-Za-z_!'])(\$?[A-Z]{1,3})(\$?)(\d+)(?![\d(])")


class Plan:
    """Đổi số hàng từ mẫu sang bảng mới. regions = [(đầu, cuối, số hàng mới)] theo hàng mẫu, không chồng nhau."""

    def __init__(self, regions, max_row):
        self.regions = sorted(regions)
        self.max_row = max_row
        self.rows = []  # (hàng mới, hàng mẫu dùng làm khuôn)
        self.first, self.last = {}, {}  # vùng (đầu) -> hàng mới đầu / cuối
        new, r = 1, 1
        regs = {a: (a, b, n) for a, b, n in self.regions}
        while r <= max_row:
            if r in regs:
                a, b, n = regs[r]
                self.first[a], self.last[a] = new, new + n - 1
                for i in range(n):
                    self.rows.append((new + i, a + min(i, b - a)))
                new += n
                r = b + 1
            else:
                self.rows.append((new, r))
                new += 1
                r += 1

    def region_of(self, r):
        for a, b, _ in self.regions:
            if a <= r <= b:
                return a, b
        return None

    def map(self, r, is_end=False):
        """Hàng mới tương ứng hàng mẫu r (trong vùng lặp: đầu vùng hoặc cuối vùng)."""
        off = 0
        for a, b, n in self.regions:
            if a <= r <= b:
                return self.last[a] if is_end else self.first[a]
            if b < r:
                off += n - (b - a + 1)
        return r + off

    def formula(self, text):
        """Sửa số hàng trong công thức ở ngoài vùng lặp: dời hàng; đầu/cuối dãy A15:A26 thành đầu/cuối vùng mới."""
        def sub(m):
            col, dollar, row = m.group(1), m.group(2), int(m.group(3))
            is_end = m.start() > 0 and text[m.start() - 1] == ":"
            return f"{col}{dollar}{self.map(row, is_end)}"
        return _REF.sub(sub, text)


def _copy_style(src, dst):
    dst.font = copy.copy(src.font)
    dst.fill = copy.copy(src.fill)
    dst.border = copy.copy(src.border)
    dst.alignment = copy.copy(src.alignment)
    dst.number_format = src.number_format
    dst.protection = copy.copy(src.protection)


def _print_end_row(tws):
    m = re.search(r"\$?[A-Z]+\$?(\d+)\s*$", str(tws.print_area or ""))
    return int(m.group(1)) if m else tws.max_row


def clone_sheet(wb, tws, title, regions, max_col=None):
    """Sao chép sheet mẫu `tws` sang sổ `wb` (tên `title`), nhân các vùng lặp. Trả (ws mới, Plan)."""
    end_row = _print_end_row(tws)
    plan = Plan([(a, b, n) for a, b, n in regions if b <= end_row], end_row)
    ws = wb.create_sheet(title=title[:31])
    for letter, dim in tws.column_dimensions.items():
        nd = ws.column_dimensions[letter]
        nd.width, nd.hidden = dim.width, dim.hidden
        if dim.min and dim.max and dim.max > dim.min:  # nhóm cột cùng độ rộng
            for c in range(dim.min, dim.max + 1):
                ws.column_dimensions[get_column_letter(c)].width = dim.width
                ws.column_dimensions[get_column_letter(c)].hidden = dim.hidden  # cột ẩn của mẫu ẩn cả nhóm, không chỉ cột đầu nhóm
    max_col = max_col or tws.max_column
    for new_r, tr in plan.rows:
        in_region = plan.region_of(tr) is not None
        rd = tws.row_dimensions[tr]
        if rd.height:
            ws.row_dimensions[new_r].height = rd.height
        a_reg = plan.region_of(tr)
        if (tws.row_dimensions[a_reg[0]].hidden if a_reg else rd.hidden):  # dòng trong vùng lặp: ẩn hay không theo dòng đầu vùng
            ws.row_dimensions[new_r].hidden = True
        for c in range(1, max_col + 1):
            src = tws.cell(row=tr, column=c)
            dst = ws.cell(row=new_r, column=c)
            _copy_style(src, dst)
            v = src.value
            if isinstance(v, str) and v.startswith("="):
                v = (Translator(v, origin=src.coordinate).translate_formula(dst.coordinate) if in_region else plan.formula(v))
            elif v is not None and not isinstance(v, (str, int, float, bool, datetime.date, datetime.datetime)):
                v = getattr(v, "text", None)  # công thức mảng hoặc kiểu lạ: bỏ, bộ điền sẽ ghi lại
            dst.value = v
    for mr in tws.merged_cells.ranges:
        if mr.min_row > end_row:
            continue
        a = plan.region_of(mr.min_row)
        if a and mr.min_row == mr.max_row:
            if mr.min_row != a[0]:
                continue  # chỉ lấy ô gộp của hàng đầu vùng, nhân cho mọi hàng của vùng
            for nr in range(plan.first[a[0]], plan.last[a[0]] + 1):
                ws.merge_cells(start_row=nr, start_column=mr.min_col, end_row=nr, end_column=mr.max_col)
            continue
        ws.merge_cells(start_row=plan.map(mr.min_row), start_column=mr.min_col, end_row=plan.map(mr.max_row, True), end_column=mr.max_col)
    # in ấn
    ps, tps = ws.page_setup, tws.page_setup
    for k in ("orientation", "paperSize", "scale", "fitToWidth", "fitToHeight"):
        setattr(ps, k, getattr(tps, k))
    ws.sheet_properties.pageSetUpPr = copy.copy(tws.sheet_properties.pageSetUpPr)
    ws.page_margins = copy.copy(tws.page_margins)
    ws.print_options = copy.copy(tws.print_options)
    ws.sheet_view.showGridLines = tws.sheet_view.showGridLines
    pa = re.search(r"\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)", str(tws.print_area or ""))
    if pa:
        ws.print_area = f"{pa.group(1)}{plan.map(int(pa.group(2)))}:{pa.group(3)}{plan.map(int(pa.group(4)), True)}"
    if tws.print_title_rows:
        t = re.search(r"(\d+):\$?(\d+)", str(tws.print_title_rows))
        if t:
            ws.print_title_rows = f"{plan.map(int(t.group(1)))}:{plan.map(int(t.group(2)), True)}"
    return ws, plan


def load_template(path, pick=0):
    import openpyxl
    wb = openpyxl.load_workbook(path)
    return wb.worksheets[min(pick, len(wb.worksheets) - 1)]


# ------------------------------------------------------------------ bộ điền từng chứng từ
def _unit(it, prof):
    return str(it.get("unit") or prof.get("unit") or "")


def _all_div(rec, n):
    divs = {float(it.get("div") or 0) for it in rec.get("items", [])}
    return divs == {float(n)}


def _kien_total(rec):
    return sum(int(it.get("kien") or 0) for it in rec.get("items", []))


def _po_lines(core, rec, pos_fmt):
    return [pos_fmt(p, d) for p, d in (core.rec_po_list(rec) or [("", "")])]


_PXK_RE = re.compile(r"(PXK\w*\s*[:：]?\s*)(\d{3,})", re.I)


def unify_pxk(ws, pxk):
    """Mọi chỗ ghi 'PXK… : <số>' trong sheet đều thành số PXK hiện hành (mẫu của khách có thể ghi mã cũ ở nhiều ô). Trả số chỗ đã đổi."""
    n = 0
    pxk = str(pxk or "").strip()
    if not pxk:
        return 0
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and _PXK_RE.search(c.value):
                new = _PXK_RE.sub(lambda m: m.group(1) + pxk, c.value)
                if new != c.value:
                    c.value, n = new, n + 1
    return n


def fill_pkl(core, wb, rec, prof, tws, title):
    items, pos = rec.get("items", []), core.rec_po_list(rec) or [("", "")]
    ws, pl = clone_sheet(wb, tws, title, [(3, 4, max(len(pos), 2)), (15, 26, max(len(items), 1))])
    dt = core._dmy(core._iso_to_date(rec.get("docDate")))
    ws[f"I{pl.map(2)}"] = f"PXKKVCNB : {rec.get('pxkNo', '')}"
    ws[f"L{pl.map(2)}"] = f"     Ngày :{dt}"
    ws["A3"] = core.HT_NAME
    for i, (po, pd) in enumerate(pos):
        ws[f"I{pl.first[3] + i}"] = f"Số ĐĐH: {po}"
        ws[f"L{pl.first[3] + i}"] = f"     Ngày:{pd}"
    for col in ("A", "I"):
        ws[f"{col}{pl.map(9)}"] = prof["name"]
        ws[f"{col}{pl.map(10)}"] = prof["addr"]
    ws[f"A{pl.map(6)}"] = core.ADDR_HT.rstrip(".")
    ws[f"A{pl.map(12)}"] = f"Từ: {core.HT_NAME}\nĐến: {prof['name']}"
    ws[f"H{pl.map(30)}"] = core.HT_NAME
    for i, it in enumerate(items):
        r = pl.first[15] + i
        spec = core.split_name_spec(it["ten_sp"])[1]
        tare = float(it.get("tare") or 0)
        for col, v in (("A", i + 1), ("B", it["ten_sp"]), ("H", _unit(it, prof)), ("I", it.get("qty", 0)), ("J", f"=K{r}+{tare:g}"),
                       ("K", f"=I{r}*O{r}"), ("L", it.get("price", 0)), ("M", f"=I{r}*L{r}"), ("N", spec), ("O", it.get("kg", 0))):
            ws[f"{col}{r}"] = v
    if not _all_div(rec, 20):  # mẫu chia 20 ống/kiện; khác định mức thì ghi số kiện đã tính
        ws[f"C{pl.map(28)}"] = _kien_total(rec)
    unify_pxk(ws, rec.get("pxkNo"))
    return ws


def fill_pack(core, wb, rec, prof, tws, title):
    items, pos = rec.get("items", []), core.rec_po_list(rec) or [("", "")]
    ws, pl = clone_sheet(wb, tws, title, [(3, 4, max(len(pos), 2)), (18, 29, max(len(items), 1))])
    dt = core._dmy(core._iso_to_date(rec.get("docDate")))
    ws["D2"] = f"PXKKVCNB : {rec.get('pxkNo', '')}"
    ws["F2"] = f" Ngày: {dt}"
    ws["A3"] = core.HT_NAME
    for i, (po, pd) in enumerate(pos):
        ws[f"D{3 + i}"] = f"Số ĐĐH: {po}"
        ws[f"F{3 + i}"] = f"       Ngày: {pd}"
    ws[f"A{pl.map(6)}"] = core.ADDR_HT.rstrip(".")
    ws[f"A{pl.map(7)}"] = f"Tel : {core.HT_TEL}"
    ws[f"A{pl.map(10)}"] = prof["name"]
    ws[f"A{pl.map(11)}"] = prof["addr"]
    place = core.short_place(prof.get("addr", ""))
    ws[f"C{pl.map(14)}"] = place
    ws[f"D{pl.map(14)}"] = f"{(prof.get('customs') or {}).get('incoterm', 'DAP')} {place.split(' - ')[-1]}".strip()
    for i, it in enumerate(items):
        r = pl.first[18] + i
        tare = float(it.get("tare") or 0)
        for col, v in (("A", i + 1), ("B", it["ten_sp"]), ("D", it.get("qty", 0)), ("E", f"=G{r}*D{r}"), ("F", f"=E{r}+{tare:g}"), ("G", it.get("kg", 0))):
            ws[f"{col}{r}"] = v
    if not _all_div(rec, 20):
        ws[f"B{pl.map(32)}"] = _kien_total(rec)
    unify_pxk(ws, rec.get("pxkNo"))
    return ws


def fill_pgh(core, wb, rec, prof, tws, title):
    items = rec.get("items", [])
    ws, pl = clone_sheet(wb, tws, title, [(8, 9, max(len(items), 1))])
    d_giao = (core._iso_to_date(rec["deliveryDate"]) if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", str(rec.get("deliveryDate") or "").strip())
              else core._iso_to_date(rec.get("docDate")) + datetime.timedelta(days=1))
    ws["A2"] = f"送货单位/ Bên giao hàng：{core.HT_NAME} "
    ws["J2"] = f"送货单号/Số phiếu giao hàng：XKTLGH-{d_giao:%y%m%d}"
    ws["A3"] = f"送货地址/Địa chỉ bên giao hàng ： {core.ADDR_HT}"
    ws["J3"] = f"发票号/ Số hóa đơn: {rec.get('hdNo', '')}"
    ws["A4"] = f"收货单位/ Bên nhận hàng：{prof['name']}"
    ws["J4"] = f"送货日期/ Ngày giao hàng：{core._dmy(d_giao)}"
    ws["A5"] = f"收货地址/Địa chỉ nhận hàng：{prof.get('addrKho') or prof['addr']}"
    ws["A6"] = f"联系人 Người liên hệ：{prof.get('buyerContact', '')}"
    ws["F6"] = f"联系电话/ DTDD：{prof.get('buyerTel', '')}"
    for i, it in enumerate(items):
        r = pl.first[8] + i
        base, spec = core.split_name_spec(it["ten_sp"])
        tare = float(it.get("tare") or 0)
        u = _unit(it, prof)
        for col, v in (("A", i + 1), ("B", it.get("ma_sp", "")), ("C", base + " "), ("D", spec), ("F", u[:1].upper() + u[1:]),
                       ("G", it.get("qty", 0)), ("H", f"=N{r}*G{r}"), ("I", f"=H{r}+{tare:g}"), ("J", it.get("inquiry", "")),
                       ("K", it.get("po", "")), ("L", it.get("dept") or prof.get("dept", "")), ("M", it.get("customsNo", "")), ("N", it.get("kg", 0))):
            ws[f"{col}{r}"] = v
    return ws


def fill_dccn_able(core, wb, rec, prof, tws, title):
    """Bảng đối chiếu công nợ kiểu Able (sheet 'BẢNG ĐỐI CHIẾU CÔNG NỢ'): STT | Ngày giao | PO | Mã SP | Quy cách | Mã hàng | ĐVT | SL | Đơn giá | Thành tiền."""
    items = rec.get("items", [])
    ws, pl = clone_sheet(wb, tws, title, [(12, 24, max(len(items), 1))], max_col=11)
    d = core._iso_to_date(rec.get("docDate"))
    ws["B2"] = f"Ngày日{d.day:02d} tháng月{d.month:02d}  năm年 {d.year}"
    ws["D4"] = core.HT_NAME
    ws["D5"] = core.ADDR_HT
    ws["B7"] = f"Khách hàng客户:   {prof['name']}"
    ws["B8"] = f"Địa chỉ:   :{prof.get('addrKho') or prof['addr']}"
    ws["B9"] = f"Mã số thuế:\t  {prof.get('mst', '')}"
    r0 = pl.first[12]
    for i in range(1, len(items)):  # các dòng mẫu phía dưới cỡ chữ lệch nhau: lấy kiểu của dòng đầu cho đều
        for col in "BCDEFGHIJK":
            ws[f"{col}{r0 + i}"]._style = copy.copy(ws[f"{col}{r0}"]._style)
        if ws.row_dimensions[r0].height:
            ws.row_dimensions[r0 + i].height = ws.row_dimensions[r0].height
    for i, it in enumerate(items):
        r = r0 + i
        u = str(it.get("unit") or prof.get("unit") or "")
        ship = it.get("shipDate")
        c = ws[f"C{r}"]
        c.value = core._iso_to_date(ship) if ship else d
        c.number_format = "dd/mm/yyyy"
        for col, v in (("B", i + 1), ("D", it.get("po", "")), ("F", it.get("ten_sp", "")), ("H", u.lower()),
                       ("I", it.get("qty", 0)), ("J", it.get("price", 0)), ("K", f"=I{r}*J{r}")):
            ws[f"{col}{r}"] = v
    total = round(core.lot_totals(rec)["amount"])
    ws[f"B{pl.map(28)}"] = f"Tổng tiền bằng chữ 总金额大写（越南盾): {core.num_to_vn_words(total)}"
    sig = pl.map(30)
    ws.merge_cells(f"G{sig}:K{sig}")
    ws[f"G{sig}"] = str(prof["name"]).upper()
    ws[f"G{sig}"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    return ws


def fill_dccn(core, wb, rec, prof, tws, title):
    if "ĐỐI CHIẾU CÔNG NỢ" in str(tws["B1"].value or "").upper():
        return fill_dccn_able(core, wb, rec, prof, tws, title)
    items = rec.get("items", [])
    ws, pl = clone_sheet(wb, tws, title, [(9, 20, max(len(items), 1))])
    d_hd = core._iso_to_date(rec.get("docDate"))
    days = int(float(rec.get("payDays") or prof.get("payDays") or 60))
    ws["A2"] = f"销售方/Người bán：{core.HT_NAME}"
    ws["H2"] = f"购买方/Người mua：{prof['name']}"
    ws["A3"] = f"乙方（卖方）: {core.HT_NAME_EN}"
    ws["H3"] = f"甲方（买方）: {prof.get('nameCn', '')}"
    ws["A4"] = f"联系人/Người liên hệ：{prof.get('sellerContact', '')}"
    ws["H4"] = f"联系人/Người liên hệ：{prof.get('buyerContact', '')}"
    ws["A5"] = f"电话/Điện thoại：{prof.get('sellerTel', '')}"
    ws["H5"] = f"电话/Điện thoại：{prof.get('buyerTel', '')}"
    r0 = pl.first[9]
    for i, it in enumerate(items):
        r = r0 + i
        po = it.get("po", "")
        vals = {"A": i + 1, "B": rec.get("hdNo", "") if i == 0 else f"=$B${r0}", "C": d_hd if i == 0 else f"=$C${r0}",
                "D": po,
                "E": it.get("ma_sp", ""), "F": it["ten_sp"], "G": it.get("qty", 0), "H": it.get("price", 0), "I": f"=G{r}*H{r}",
                "J": "VND", "K": f"{days} ngày", "L": f"=C{r}+{days}"}
        for col, v in vals.items():
            ws[f"{col}{r}"] = v
        ws[f"C{r}"].number_format = ws[f"L{r}"].number_format = "dd/mm/yyyy"
    base = pl.map(24)
    texts = {1: f"Bên bán 乙方（卖方）:  {core.HT_NAME}", 2: f"Mã số doanh nghiệp/Mã số thuế 企业编码/税务编码：{core.MST_HT}",
             3: f"Địa chỉ trụ sở chính地址：{core.ADDR_HT.rstrip('.')}", 4: f"Số tài khoản账号：'{core.HT_BANK_ACC}",
             5: f"tại Ngân hàng 开户行:  {core.HT_BANK_AT}", 6: f"Đơn vị  hưởng thụ 收款单位名称：{core.HT_NAME_SHORT}",
             7: f"Swift code: {core.HT_SWIFT}"}
    for k, t in texts.items():
        ws[f"A{base + k}"] = t
    return ws


def fill_dntt(core, wb, rec, prof, tws, title):
    ws, _ = clone_sheet(wb, tws, title, [])
    days = int(float(rec.get("payDays") or prof.get("payDays") or 60))
    d_tt = core._iso_to_date(rec.get("docDate")) + datetime.timedelta(days=days)
    total = round(core.lot_totals(rec)["amount"])
    pos = [p for p, _ in core.rec_po_list(rec)]
    ws["A1"] = f"{prof.get('nameCn', '')}\n{prof['name']}".strip()
    ws["C3"] = core._dmy(d_tt)
    ws["C4"] = core.HT_NAME
    ws["C6"] = total
    ws["C6"].number_format = "#,##0"
    ws["C8"] = core.num_to_vn_words(total)  # mẫu dùng hàm ngoài [1]!vnd(): ghi chữ trực tiếp để mở ở máy nào cũng đúng
    ws["C10"] = f"Chi trả tiền mua lõi giấy cho {core.HT_NAME} theo PO số: {' và '.join(pos)}"
    ws["F13"] = core.HT_NAME_SHORT
    ws["E14"] = f"Tại Ngân hàng {core.HT_BANK_AT}"
    ws["C15"] = core.HT_BANK_ACC
    ws["C16"] = core.HT_SWIFT
    return ws




def fill_pkl_arizon(core, wb, rec, prof, tws, title):
    """Invoice Arizon theo file mẫu (sheet '9.2'): Mã hàng | Tên hàng | PO | ĐVT | SL | kg/chiếc | cả bì | tịnh | số kiện | đơn giá | thành tiền."""
    items = rec.get("items", [])
    ws, pl = clone_sheet(wb, tws, title, [(13, 20, max(len(items), 1))], max_col=14)
    dt = core._dmy(core._iso_to_date(rec.get("docDate")))
    ws["G2"] = f" Invoice no: {rec.get('pxkNo', '')}"
    ws["L2"] = f"Ngày:{dt}"
    ws["A3"] = core.HT_NAME
    ws["A4"] = core.ADDR_HT
    ws["A7"] = f"\n{prof['name']}"
    ws["A8"] = prof["addr"]
    ws["A10"] = f"Từ:{core.HT_NAME}\nĐến: {prof['name']}"
    ws[f"F{pl.map(24)}"] = core.HT_NAME
    for col, hide in (("B", True), ("H", False), ("J", True)):  # B (Mã hàng trống) và J (cột đệm) thừa: ẩn; H (kg/chiếc) phải hiện
        ws.column_dimensions[col].hidden = hide
        if not hide and not ws.column_dimensions[col].width:
            ws.column_dimensions[col].width = 10
    r0 = pl.first[13]
    for i, it in enumerate(items):
        r = r0 + i
        tare = float(it.get("tare") or 0)
        div = float(it.get("div") or 0)
        u = str(it.get("unit") or prof.get("unit") or "")
        for col, v in (("A", "=ROW()-12"), ("C", str(it.get("ma_sp") or "").strip()), ("D", "\n" + str(it.get("ten_sp") or "").strip()), ("E", it.get("po", "")),
                       ("F", u[:1].upper() + u[1:]), ("G", it.get("qty", 0)), ("H", it.get("kg", 0)), ("I", f"=K{r}+{tare:g}"), ("K", f"=G{r}*H{r}"),
                       ("L", f"=ROUNDUP(G{r}/{div:g},0)" if div > 0 else 0), ("M", it.get("price", 0)), ("N", f"=M{r}*G{r}")):
            ws[f"{col}{r}"] = v
    return ws


def fill_bbgh(core, wb, rec, prof, tws, title):
    """Biên bản bàn giao theo file mẫu của khách (sheet 'BBGH'): bên giao, bên nhận, bảng hàng giao nhận, chữ ký."""
    items = rec.get("items", [])
    ws, pl = clone_sheet(wb, tws, title, [(21, 25, max(len(items), 1))], max_col=7)
    d = core._iso_to_date(rec.get("docDate"))
    ws["A1"] = core.HT_NAME
    ws["A6"] = f"Hôm nay, ngày {d.day} tháng {d.month} năm {d.year}"
    ws["A8"] = f"Tại {prof['name']} chúng tôi gồm có: "
    ws["A10"] = f"Bên giao: {core.HT_NAME}"
    ws["A12"] = f"Địa chỉ : {core.ADDR_HT}"
    ws["A14"] = f"Bên nhận: {prof['name']}"
    ws["A16"] = f"Địa chỉ: {prof.get('addrKho') or prof['addr']}"
    ws[f"A{pl.map(27)}"] = None  # mẫu lặp lại câu 'Hai bên cùng tiến hành…' sau bảng: bỏ câu thừa
    r0 = pl.first[21]
    for i, it in enumerate(items):
        r = r0 + i
        u = str(it.get("unit") or prof.get("unit") or "")
        for col, v in (("A", f"{it.get('ma_sp', '')} {it.get('ten_sp', '')}".strip()), ("B", it.get("po", "")), ("C", u[:1].upper() + u[1:]),
                       ("D", it.get("qty", 0)), ("E", it.get("price", 0)), ("F", f"=D{r}*E{r}")):
            ws[f"{col}{r}"] = v
    return ws


def fill_po(core, wb, rec, prof, tws, title):
    """Đơn đặt hàng (PO) song ngữ theo mẫu của khách (VD Betterial): STT | Tên hàng | ĐVT | Thông số quy cách | SL | Đơn giá | Thành tiền, tổng, VAT, bằng chữ, điều khoản."""
    items = rec.get("items", [])
    ws, pl = clone_sheet(wb, tws, title, [(18, 25, max(len(items), 1))], max_col=8)
    d_po = core._parse_dmy(rec.get("poDate")) or core._iso_to_date(rec.get("docDate"))
    d_giao = core._iso_to_date(rec.get("deliveryDate") or rec.get("docDate"))
    ws["A7"] = f"Ngày/ 日期 : {d_po.year}.{d_po.month:02d}.{d_po.day:02d}"
    ws["D7"] = f"Số/ No.  {rec.get('poNumber', '')}"
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=9, max_col=14):  # ô phụ ngoài bảng (tham chiếu file khác...) không đưa sang PO mới
        for c in row:
            c.value = None
    r0 = pl.first[18]
    for i, it in enumerate(items):
        r = r0 + i
        name = str(it.get("ten_sp") or "").strip()
        code = str(it.get("ma_sp") or "").strip()
        kind = re.split(r"[\d(]", name, maxsplit=1)[0].strip() or "Hàng hóa"
        spec = name if (not code or f"({code})" in name.replace(" ", "")) else f"{name}\n({code})"
        if i:  # dòng thêm lấy kiểu dòng đầu cho đều
            for col in "ABCDEFGH":
                ws[f"{col}{r}"]._style = copy.copy(ws[f"{col}{r0}"]._style)
        ws.row_dimensions[r].height = max(30.0, 15.0 * (1 + len(spec) // 34 + spec.count("\n")))
        for col, v in (("A", i + 1), ("B", kind), ("C", "PCS个"), ("D", spec), ("E", it.get("qty", 0)), ("F", it.get("price", 0)), ("G", f"=E{r}*F{r}")):
            ws[f"{col}{r}"] = v
    last = r0 + max(len(items), 1) - 1
    t = pl.map(26)
    ws[f"E{t}"] = f"=SUM(E{r0}:E{last})"
    ws[f"G{t}"] = f"=SUM(G{r0}:G{last})"
    ws[f"G{t + 1}"] = 0
    ws[f"G{t + 2}"] = f"=G{t}+G{t + 1}"
    total = round(sum(float(it.get("qty", 0)) * float(it.get("price", 0)) for it in items))
    ws[f"C{pl.map(29)}"] = core.num_to_vn_words(total)
    ws[f"A{pl.map(30)}"] = f"* Thời gian giao hàng 交货时间:{d_giao.day:02d}/{d_giao.month:02d}/{d_giao.year}"
    return ws


FILLERS = {"po": fill_po, "bbgh": fill_bbgh, "pkl": fill_pkl, "pkl_arizon": fill_pkl_arizon, "pack": fill_pack, "pgh": fill_pgh, "dccn": fill_dccn, "dntt": fill_dntt}


def build_from_template(core, doc, wb, rec, prof, path, title):
    ws = FILLERS[doc](core, wb, rec, prof, load_template(path), title)
    # số dòng hàng thay đổi nên không để mẫu cố định tỷ lệ in: vừa bề ngang một trang, vừa một trang cao nếu ít dòng
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1 if ws.max_row <= 45 else 0
    ws.page_setup.scale = None
    return ws


# ------------------------------------------------------------------ vừa chữ khi in/mở file
def _text_of(v):
    return v if isinstance(v, str) and not v.startswith("=") else None


def _units(text, size, bold):
    """Độ dài chữ theo đơn vị độ rộng cột Excel (ước lượng, thừa một chút để không bao giờ bị cắt)."""
    return len(text) * (size / 11.0) * (1.12 if bold else 1.03)


def _lines_needed(text, width, size, bold):
    n = 0
    for para in text.split("\n"):
        n += max(1, -(-int(_units(para, size, bold) * 1.08 + 0.999) // max(int(width), 1)))
    return n


def autofit_workbook(wb):
    for ws in wb.worksheets:
        try:
            autofit_sheet(ws)
        except Exception:  # không để lỗi trình bày chặn xuất chứng từ
            pass


def autofit_sheet(ws):
    """Mọi ô chữ đều hiện đủ: chữ dài thì tự xuống dòng và nâng chiều cao dòng; số quá rộng thì nới cột."""
    from openpyxl.styles import Alignment
    colw = lambda c: (ws.column_dimensions[get_column_letter(c)].width or 8.43)
    hidden = lambda c: ws.column_dimensions[get_column_letter(c)].hidden
    # 1) nới cột cho các ô số (không công thức, không gộp)
    merged_at = {}
    for mr in ws.merged_cells.ranges:
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1):
                merged_at[(r, c)] = mr
    for row in ws.iter_rows():
        for cell in row:
            v = cell.value
            if isinstance(v, bool) or not isinstance(v, (int, float)) or (cell.row, cell.column) in merged_at:
                continue
            fmt = cell.number_format or ""
            text = f"{v:,.2f}" if "0.00" in fmt else (f"{round(v):,}" if "#,##0" in fmt else str(v))
            size = (cell.font.size or 11) if cell.font else 11
            need = _units(text, size, bool(cell.font and cell.font.bold)) + 1.5
            if need > colw(cell.column) and not hidden(cell.column):
                ws.column_dimensions[get_column_letter(cell.column)].width = min(round(need, 1), 60)
    # 2) chữ dài: bật xuống dòng, nâng chiều cao dòng
    need_h = {}
    for row in ws.iter_rows():
        for cell in row:
            text = _text_of(cell.value)
            if not text or ws.row_dimensions[cell.row].hidden or hidden(cell.column):
                continue
            mr = merged_at.get((cell.row, cell.column))
            if mr and (mr.min_row, mr.min_col) != (cell.row, cell.column):
                continue
            c0, c1, r0, r1 = (mr.min_col, mr.max_col, mr.min_row, mr.max_row) if mr else (cell.column, cell.column, cell.row, cell.row)
            width = sum(colw(c) for c in range(c0, c1 + 1) if not hidden(c))
            if not mr and (cell.alignment is None or cell.alignment.horizontal in (None, "general", "left")) and not (cell.alignment and cell.alignment.wrap_text):
                c = cell.column + 1  # chữ ô không gộp tràn sang các ô trống bên phải
                while c <= ws.max_column and ws.cell(cell.row, c).value in (None, "") and (cell.row, c) not in merged_at:
                    width += 0 if hidden(c) else colw(c)
                    c += 1
            size = (cell.font.size or 11) if cell.font else 11
            bold = bool(cell.font and cell.font.bold)
            al = cell.alignment
            if _units(max(text.split("\n"), key=len), size, bold) > width * 0.98 and not (al and al.wrap_text):
                cell.alignment = Alignment(horizontal=al.horizontal, vertical=al.vertical or "center", wrap_text=True,
                                           indent=al.indent, text_rotation=al.text_rotation)
                al = cell.alignment
            if not (al and al.wrap_text) and "\n" not in text:
                continue
            h = _lines_needed(text, width, size, bold) * size * 1.33 + 5
            have = sum((ws.row_dimensions[r].height or 15) for r in range(r0, r1 + 1))
            if h > have:
                need_h[r1] = max(need_h.get(r1, 0), (ws.row_dimensions[r1].height or 15) + (h - have))
    for r, h in need_h.items():
        ws.row_dimensions[r].height = min(round(h, 1), 409)

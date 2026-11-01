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
from openpyxl.utils import get_column_letter

DOCS = ("pkl", "pack", "pgh", "dccn", "dntt")  # tên file mẫu: <mã khách>/<doc>.xlsx

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


def clone_sheet(wb, tws, title, regions):
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
    max_col = tws.max_column
    for new_r, tr in plan.rows:
        in_region = plan.region_of(tr) is not None
        rd = tws.row_dimensions[tr]
        if rd.height:
            ws.row_dimensions[new_r].height = rd.height
        if rd.hidden:
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


def fill_pkl(core, wb, rec, prof, tws, title):
    items, pos = rec.get("items", []), core.rec_po_list(rec) or [("", "")]
    ws, pl = clone_sheet(wb, tws, title, [(3, 4, len(pos)), (15, 26, max(len(items), 1))])
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
    return ws


def fill_pack(core, wb, rec, prof, tws, title):
    items, pos = rec.get("items", []), core.rec_po_list(rec) or [("", "")]
    ws, pl = clone_sheet(wb, tws, title, [(3, 4, len(pos)), (18, 29, max(len(items), 1))])
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


def fill_dccn(core, wb, rec, prof, tws, title):
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


FILLERS = {"pkl": fill_pkl, "pack": fill_pack, "pgh": fill_pgh, "dccn": fill_dccn, "dntt": fill_dntt}


def build_from_template(core, doc, wb, rec, prof, path, title):
    return FILLERS[doc](core, wb, rec, prof, load_template(path), title)

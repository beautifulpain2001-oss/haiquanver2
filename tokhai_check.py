"""Bước ⑤ "Kiểm tra tờ khai": đối chiếu tờ khai nháp ECUS (bản "In thử" xuất ra Excel/CSV) với Invoice, Hóa đơn VAT và
Phiếu xuất kho của lô, rồi ghi một file Excel kết quả (KetQua, ToKhai, Invoice, HoaDon_VAT, PXK).

Logic chép từ macro ModToKhai.bas của file Check_hang_XML_vs_ERP.xlsm (NhapFileToKhai, SoSanhToKhaiInvoice, ReadTKHeader,
ReadToKhaiItems, CheckTKRowInternal, MatchInvoiceRow, FindFuzzyInvoiceRow, BuildSummaryTK, WriteHeaderCheckRow...).
Khác macro (ghi rõ ở từng chỗ):
  - số liệu Invoice lấy từ dòng hàng của lô (rec["items"], đã tính theo công thức của invoice), không đọc sheet Invoice
    và không tra ERP chung;
  - ĐVT số lượng mong đợi theo khách (customs_unit: cái -> PCE, ống -> PIP, Best -> PIP), macro cứng PCE;
  - PO trong mô tả so với PO của chính dòng Invoice đã ghép (lô nhiều PO);
  - thêm so HS tờ khai với HS của mã hàng, số dòng hàng khai báo, tổng SL/tiền Hóa đơn VAT và PXK so với Invoice;
  - ngày hàng đi / ngày phát hành so với ngày chứng từ của lô (macro so với ngày hôm nay);
  - nhiều tờ khai (lô trên 50 dòng): kiện, gross, trị giá cộng các tờ khai rồi mới so với tổng lô.

Module không phụ thuộc Qt. Các hàm cần dữ liệu của phần mềm nhận `core` (module hongthien_desktop_app) làm tham số.
"""

import csv
import datetime
import io
import os
import re
import unicodedata

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

try:  # chữ nhiều màu trong một ô (tô phần tên khác nhau); openpyxl >= 3.1
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
except ImportError:  # pragma: no cover
    CellRichText = None

TOL_DEFAULT = 0.0  # so khớp tuyệt đối (Huy 21/11: không cho phép sai số); chỉ bỏ nhiễu số thực sau 6 số lẻ
TK_EXTS = (".xlsx", ".xlsm", ".xls", ".csv")
NE = "≠"  # ≠


# ---------------------------------------------------------------- đọc số, chữ
def nfc(s):
    return unicodedata.normalize("NFC", str(s if s is not None else ""))


def cell_text(v):
    """Ô -> chữ đã cắt khoảng trắng (ô ngày -> dd/mm/yyyy, số nguyên không có '.0')."""
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, datetime.date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return nfc(v).strip()


def _num_like(s):
    try:
        float(s.replace(".", "").replace(",", "."))
        return True
    except ValueError:
        return False


def is_num(v):
    """Như IsNumeric(Replace(Replace(s,".",""),",",".")) của macro; ô đã là số thì luôn đúng."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    s = cell_text(v)
    return bool(s) and s != "-" and _num_like(s)


def parse_vn_num(v):
    """Số kiểu Việt Nam (ParseVNNum): ô số giữ nguyên; chuỗi rỗng/'-' = 0; có '.' thì bỏ hết '.', ',' đổi thành '.'.
    '6.331.208' -> 6331208; '106,08' -> 106.08; '1.234,5' -> 1234.5."""
    if v is None or isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = cell_text(v)
    if not s or s == "-":
        return 0.0
    s = s.replace(".", "").replace(",", ".")
    m = re.match(r"\s*[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)  # như Val(): đọc phần số ở đầu
    try:
        return float(m.group(0)) if m else 0.0
    except ValueError:
        return 0.0


_RE_PO = re.compile(r"Po[\s.]*No[\s.:]*([A-Za-z0-9\-]+)", re.I)
_RE_CUT = re.compile(r"(?:,?\s*Po[\s.]*No\b|\.\s*Hàng mới)", re.I)
_RE_TOONG = re.compile(r"^giấy\s+tổ\s+ong\s+", re.I)
_RE_PXK = re.compile(r"PXK[A-Za-z]*\s*(?:số|so|:)?\s*[:.]?\s*(\d{4,})", re.I)


def extract_po(s):
    m = _RE_PO.search(nfc(s))
    return m.group(1) if m else ""


def clean_po(s):
    """'Po No 202639HT' -> '202639HT'; chuỗi không có 'Po No' giữ nguyên."""
    return extract_po(s) or cell_text(s)


def clean_tk_desc(s):
    """Mô tả tờ khai bỏ phần 'Po.No ...' / '. Hàng mới 100%' và dấu phẩy cuối."""
    s = nfc(s)
    m = _RE_CUT.search(s)
    if m and m.start() > 0:
        s = s[:m.start()]
    s = s.strip()
    if s.endswith(","):
        s = s[:-1].strip()
    return s


def norm_tk_key(s):
    """Khóa so tên: bỏ tiền tố 'Giấy tổ ong', gộp khoảng trắng, viết hoa (giữ dấu tiếng Việt như macro)."""
    s = _RE_TOONG.sub("", nfc(s).strip())
    s = re.sub(r"\s+", " ", s)
    return s.upper()


def extract_pxk(s):
    m = _RE_PXK.search(nfc(s))
    return m.group(1) if m else ""


def levenshtein(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def diff_span(s1, s2):
    """(đầu, cuối1, cuối2): phần khác nhau là s1[đầu:cuối1] và s2[đầu:cuối2] (bỏ tiền tố chung và hậu tố chung)."""
    p = 0
    while p < len(s1) and p < len(s2) and s1[p] == s2[p]:
        p += 1
    sfx = 0
    while len(s1) - sfx > p and len(s2) - sfx > p and s1[len(s1) - 1 - sfx] == s2[len(s2) - 1 - sfx]:
        sfx += 1
    return p, len(s1) - sfx, len(s2) - sfx


def describe_name_diff(s1, s2):
    p, e1, e2 = diff_span(s1, s2)
    d1 = s1[p:max(e1, p + 1)]
    d2 = s2[p:max(e2, p + 1)]
    cut = lambda t: t if len(t) <= 25 else t[:25] + "…"
    return f'"{cut(d1)}" {NE} "{cut(d2)}"'


def fmt_num(v, nd=0):
    """1234567.5 -> '1,234,567.50' (như FmtNum của macro)."""
    return f"{float(v or 0):,.{nd}f}"


def fmt_short(v):
    """Như Format(v, "#,##0.##"): tối đa 2 số lẻ, bỏ số 0 thừa."""
    s = f"{float(v or 0):,.2f}".rstrip("0").rstrip(".")
    return s or "0"


def differs(a, b, tol=0.0):
    """Hai số khác nhau? Mặc định tuyệt đối (làm tròn 6 số lẻ để bỏ nhiễu số thực: 1.1400000000000001 = 1.14)."""
    return round(abs(float(a or 0) - float(b or 0)), 6) > tol


def append_msg(cur, add):
    return add if not cur else f"{cur}; {add}"


# ---------------------------------------------------------------- nạp file tờ khai
def rows_from_csv_text(text):
    text = text.lstrip("﻿")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = "\t" if "\t" in sample else ","
    return [tuple(r) for r in csv.reader(io.StringIO(text), delimiter=delim)]


def rows_from_paste(text):
    """Đoạn đã copy từ Excel/ECUS (mỗi dòng một hàng, các ô cách nhau bằng tab)."""
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "\t" not in text:
        return rows_from_csv_text(text)
    return [tuple(line.split("\t")) for line in text.split("\n")]


def rows_from_file(path, core=None):
    """Sheet đầu tiên của file tờ khai thành danh sách hàng. CSV đọc UTF-8 (có/không BOM), mọi ô là chữ như macro."""
    ext = os.path.splitext(str(path))[1].lower()
    if ext not in TK_EXTS:
        raise ValueError(f"File tờ khai phải là Excel hoặc CSV ({', '.join(TK_EXTS)}): {os.path.basename(path)}")
    if ext == ".csv":
        with open(path, "rb") as f:
            raw = f.read()
        for enc in ("utf-8-sig", "cp1258", "cp1252"):
            try:
                return rows_from_csv_text(raw.decode(enc))
            except UnicodeDecodeError:
                continue
        return rows_from_csv_text(raw.decode("utf-8", "replace"))
    if core is not None and hasattr(core, "excel_rows"):
        return core.excel_rows(path)
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    return list(wb.worksheets[0].iter_rows(values_only=True))


class Grid:
    """Bảng ô đánh số kiểu Excel (hàng, cột bắt đầu từ 1) trên danh sách hàng."""

    def __init__(self, rows):
        self.rows = [tuple(r) for r in rows]
        self.last_row = len(self.rows)
        self.last_col = max((len(r) for r in self.rows), default=0)

    def raw(self, r, c):
        if 1 <= r <= self.last_row:
            row = self.rows[r - 1]
            if 1 <= c <= len(row):
                return row[c - 1]
        return None

    def text(self, r, c):
        return cell_text(self.raw(r, c))

    def first_non_empty(self, r, c1, c2):
        for c in range(c1, c2 + 1):
            s = self.text(r, c)
            if s:
                return s
        return ""

    def first_num(self, r, c1, c2):
        """Ô số đầu tiên (giá trị gốc, để parse_vn_num đọc đúng ô số thật lẫn chữ '6.331.208')."""
        for c in range(c1, c2 + 1):
            v = self.raw(r, c)
            s = cell_text(v)
            if s and s != "-" and is_num(v):
                return v
        return None

    def last_text(self, r, c1, c2):
        for c in range(c2, c1 - 1, -1):
            v = self.raw(r, c)
            s = cell_text(v)
            if s and s != "-" and not is_num(v):
                return s
        return ""

    def unit_token(self, r, c1, c2, tokens):
        for c in range(c1, c2 + 1):
            s = self.text(r, c).upper()
            if s in tokens:
                return s
        return ""


def is_item_tag(s):
    """'<01>', '<02>'... (số nguyên trong ngoặc nhọn)."""
    s = cell_text(s)
    return len(s) >= 3 and s[0] == "<" and s[-1] == ">" and s[1:-1].strip().isdigit()


def read_tk_header(g):
    """Phần đầu tờ khai (ReadTKHeader): quét dòng 1..120, cột 1..24."""
    h = {"tkNo": "", "po": "", "pk": 0.0, "gross": 0.0, "amount": 0.0, "lines": 0, "depDate": "", "invNo": "",
         "invDate": "", "taxAmount": 0.0, "note": ""}
    for r in range(1, min(g.last_row, 120) + 1):
        for c in range(1, 25):
            s = g.text(r, c).lower()
            if not s:
                continue
            if s == "số tờ khai" and not h["tkNo"]:
                h["tkNo"] = g.first_non_empty(r, c + 1, 10)
            elif s == "số lượng" and h["pk"] == 0 and r < 80:
                v = g.first_non_empty(r, c + 1, 12)
                if v and _num_like(v.replace(".", "")):
                    h["pk"] = parse_vn_num(v)
            elif "tổng trọng lượng hàng" in s and h["gross"] == 0:
                h["gross"] = parse_vn_num(g.first_non_empty(r, c + 1, 15))
            elif "ngày hàng đi dự kiến" in s and not h["depDate"]:
                h["depDate"] = g.first_non_empty(r, c + 1, 20)
            elif "ký hiệu và số hiệu" in s and not h["po"]:
                h["po"] = g.first_non_empty(r, c + 1, 18)
            elif s == "số hóa đơn" and not h["invNo"]:
                for cc in range(26, c, -1):
                    v = g.text(r, cc)
                    if len(v) >= 4 and v.isdigit():
                        h["invNo"] = v
                        break
            elif s == "ngày phát hành" and not h["invDate"]:
                h["invDate"] = g.first_non_empty(r, c + 1, 26)
            elif "tổng trị giá hóa đơn" in s and h["amount"] == 0:
                h["amount"] = parse_vn_num(g.first_num(r, c + 1, 24))
            elif "tổng trị giá tính thuế" in s and h["taxAmount"] == 0:
                h["taxAmount"] = parse_vn_num(g.first_num(r, c + 1, 26))
            elif "tổng số dòng hàng của tờ khai" in s and h["lines"] == 0:
                h["lines"] = int(parse_vn_num(g.first_non_empty(r, c + 1, 26)))
            elif s == "phần ghi chú" and not h["note"]:
                h["note"] = g.first_non_empty(r, c + 1, 28)
    return h


def read_tk_items(g, tk_seq=1, started=False):
    """Dòng hàng tờ khai (ReadToKhaiItems). Trả (danh sách dòng, số thứ tự tờ khai cuối).
    `tk_seq`/`started`: nối tiếp nhiều file, gặp lại <01> là sang tờ khai kế tiếp."""
    items = []
    last_c = min(g.last_col, 30)
    seen = started
    for r in range(1, g.last_row + 1):
        tag = g.text(r, 3)
        if not is_item_tag(tag):
            continue
        if tag == "<01>" and seen:
            tk_seq += 1
        seen = True
        r_end = min(r + 22, g.last_row)
        d = {"desc": "", "q1": 0.0, "q2": 0.0, "price": 0.0, "amount": 0.0, "hs": "", "u1": "", "u2": "", "cur": "", "pu": "",
             "taxP": 0.0, "taxV": 0.0}
        for rr in range(r + 1, r_end + 1):
            s = g.text(rr, 3)
            if is_item_tag(s) or s == "<EXP>":
                break
            lbl = s.lower()
            if "mã số hàng hóa" in lbl:
                d["hs"] = g.first_non_empty(rr, 4, 10)
            elif "mô tả hàng hóa" in lbl:
                d["desc"] = g.first_non_empty(rr, 4, max(last_c, 4))
            elif "trị giá hóa đơn" in lbl:
                d["amount"] = parse_vn_num(g.first_non_empty(rr, 4, 13))
                for c in range(13, last_c + 1):
                    if "đơn giá hóa đơn" in g.text(rr, c).lower():
                        d["price"] = parse_vn_num(g.first_num(rr, c + 1, last_c))
                        d["cur"] = g.unit_token(rr, c + 1, last_c, ("VND", "USD"))
                        d["pu"] = g.unit_token(rr, c + 1, last_c, ("PCE", "PCS", "KGM", "CAI", "PIP"))
                        break
            if "trị giá tính thuế" in g.text(rr, 4).lower():
                d["taxV"] = parse_vn_num(g.first_num(rr, 5, 13))
            if "đơn giá tính thuế" in g.text(rr, 15).lower():
                d["taxP"] = parse_vn_num(g.first_num(rr, 16, last_c))
            for c in range(12, 19):
                lb = g.text(rr, c).lower()
                if lb == "số lượng (1)":
                    d["q1"] = parse_vn_num(g.first_num(rr, c + 1, last_c))
                    d["u1"] = g.last_text(rr, c + 1, last_c)
                elif lb == "số lượng (2)":
                    d["q2"] = parse_vn_num(g.first_num(rr, c + 1, last_c))
                    d["u2"] = g.last_text(rr, c + 1, last_c)
        if not d["desc"]:
            continue
        raw = clean_tk_desc(d["desc"])
        items.append({
            "tag": f"TK{tk_seq}-{tag}", "tk": tk_seq, "descFull": d["desc"], "raw": raw, "key": norm_tk_key(raw),
            "qty": d["q1"], "net": d["q2"], "price": d["price"], "amount": d["amount"], "hs": d["hs"],
            "u1": d["u1"].upper(), "u2": d["u2"].upper(), "cur": d["cur"] or "VND", "pu": d["pu"], "taxP": d["taxP"], "taxV": d["taxV"],
            "po": extract_po(d["desc"]), "origOK": "hàng mới" in nfc(d["desc"]).lower(),
        })
    return items, tk_seq, seen


def read_tokhai(sections):
    """`sections`: danh sách [(tên nguồn, danh sách hàng)] (mỗi file / đoạn dán một mục).
    Trả {"headers": [phần đầu từng nguồn], "items": [...], "nTK": số tờ khai, "sources": [tên]}."""
    headers, items, seq, started = [], [], 1, False
    for name, rows in sections:
        g = Grid(rows)
        h = read_tk_header(g)
        h["source"] = name
        headers.append(h)
        its, seq_end, started_now = read_tk_items(g, seq if not started else seq + 1, False)
        if its:
            items += its
            seq, started = seq_end, True
    n_tk = len({it["tk"] for it in items})
    return {"headers": headers, "items": items, "nTK": n_tk, "sources": [n for n, _ in sections]}


# ---------------------------------------------------------------- dữ liệu Invoice của lô
def invoice_rows(core, rec):
    """Dòng Invoice của lô, đúng số liệu ghi trên invoice (tịnh = ROUNDUP(SL x kg,2), kiện = ROUNDUP(SL/SL kiện,0), tiền = SL x giá)."""
    prof = core.PROFILES.get(rec.get("customer"), {}) or {}
    cfg = prof.get("customs") or {}
    out = []
    for i, it in enumerate(rec.get("items") or [], 1):
        qty, price = float(it.get("qty") or 0), float(it.get("price") or 0)
        names = []
        for nm in (it.get("ten_hq"), it.get("ten_sp")):
            if nm:
                names.append(str(nm))
        try:
            names.append(core.with_code(prof, it, it.get("ten_sp") or ""))
        except Exception:
            pass
        try:
            names.append(core.customs_desc(it))
        except Exception:
            pass
        disp = str(it.get("ten_hq") or it.get("ten_sp") or "").strip()
        keys = []
        for nm in names:
            k = norm_tk_key(clean_tk_desc(str(nm).replace("\n", " ")))
            if k and k not in keys:
                keys.append(k)
        po = clean_po(it.get("po") or rec.get("poNumber") or "")
        try:
            unit_qty = core.customs_unit(prof, it)
        except Exception:
            unit_qty = "PCE"
        out.append({
            "row": i, "name": clean_tk_desc(disp) or disp, "keys": keys, "po": po, "qty": qty, "price": price,
            "amount": float(it.get("amount") or 0) or qty * price, "net": float(it.get("net") or 0),
            "gross": float(it.get("gross") or it.get("net") or 0), "kien": float(it.get("kien") or 0),
            "hs": str(it.get("hs") or cfg.get("hs") or "").strip(), "unitQty": str(unit_qty or "PCE").upper(),
            "unitWt": str(cfg.get("unitWt") or "KGM").upper(),
        })
    return out


def _match_exact(tk, inv, used):
    best, best_sc = None, None
    for j, r in enumerate(inv):
        if used[j] or tk["key"] not in r["keys"]:
            continue
        sc = abs(r["qty"] - tk["qty"]) * 1000 + abs(r["price"] - tk["price"])
        if best_sc is None or sc < best_sc:
            best, best_sc = j, sc
        if sc == 0:
            break
    return best


def _match_fuzzy(tk, inv, used):
    best, best_d = None, 999999
    key = tk["key"]
    for j, r in enumerate(inv):
        if used[j]:
            continue
        for k in r["keys"]:
            if abs(len(key) - len(k)) <= 3 and max(len(key), len(k)) > 4:
                d = levenshtein(key, k)
                if d < best_d and d <= 3:
                    best, best_d = j, d
    return best


def _digits(s):
    return re.sub(r"\D", "", str(s or ""))


def check_row_internal(tk, inv_row, exp_po, tol):
    """Kiểm tra nội bộ một dòng tờ khai (CheckTKRowInternal) + HS so với mã hàng."""
    msg = ""
    if differs(tk["qty"] * tk["price"], tk["amount"], tol):
        msg = append_msg(msg, f"SL×ĐG{NE}Trị giá TK")
    if tk["taxP"] > 0 and differs(tk["price"], tk["taxP"], tol):
        msg = append_msg(msg, f"ĐG{NE}ĐG tính thuế")
    if tk["taxV"] > 0 and differs(tk["amount"], tk["taxV"], tol):
        msg = append_msg(msg, f"TG{NE}TG tính thuế")
    if not tk["hs"]:
        msg = append_msg(msg, "Thiếu HS Code")
    elif inv_row and inv_row["hs"] and _digits(inv_row["hs"]) != _digits(tk["hs"]):
        msg = append_msg(msg, f"HS TK {tk['hs']}{NE}HS hồ sơ {inv_row['hs']}")
    exp_u1 = inv_row["unitQty"] if inv_row else "PCE"
    exp_u2 = inv_row["unitWt"] if inv_row else "KGM"
    if tk["u1"] and tk["u1"] != exp_u1:
        msg = append_msg(msg, f"ĐVT1={tk['u1']}{NE}{exp_u1}")
    if tk["u2"] and tk["u2"] != exp_u2:
        msg = append_msg(msg, f"ĐVT2={tk['u2']}{NE}{exp_u2}")
    if exp_po and (not tk["po"] or tk["po"].lower() not in exp_po.lower()):
        msg = append_msg(msg, f"PO mô tả={tk['po']}{NE}{exp_po}")
    if not tk["origOK"]:
        msg = append_msg(msg, "Thiếu 'Hàng mới'")
    return msg


def _iso_to_vn(iso):
    p = str(iso or "").split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(iso or "")


def _norm_date(s):
    """'20/11/2026' / '2026-11-20' / '20/11/26' -> date hoặc None."""
    s = str(s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _same_pxk(core, a, b):
    if hasattr(core, "_same_pxk"):
        return core._same_pxk(a, b)
    a, b = str(a or "").strip(), str(b or "").strip()
    return bool(a and b) and ((a.isdigit() and b.isdigit() and int(a) == int(b)) or a.casefold() == b.casefold())


def bkav_totals(ws, head_row):
    """Tổng SoLuong / ThanhTien và số dòng của sheet nạp Bkav (đọc theo tên tiêu đề, không theo vị trí)."""
    cols = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=head_row, column=c).value
        if v:
            cols[str(v).strip()] = c
    cq, cp, ca = cols.get("SoLuong"), cols.get("DonGia"), cols.get("ThanhTien")
    qty = amt = 0.0
    n = 0
    for r in range(head_row + 1, ws.max_row + 1):
        q = ws.cell(row=r, column=cq).value if cq else None
        if q in (None, ""):
            continue
        q = parse_vn_num(q)
        a = ws.cell(row=r, column=ca).value if ca else None
        if isinstance(a, str) and a.startswith("="):
            a = q * parse_vn_num(ws.cell(row=r, column=cp).value if cp else 0)
        qty += q
        amt += parse_vn_num(a)
        n += 1
    return {"qty": qty, "amount": amt, "rows": n}


def check_tokhai(core, rec, tk, tol=TOL_DEFAULT, bkav=None):
    """Đối chiếu tờ khai đã đọc (`read_tokhai`) với lô `rec`. `bkav`: {"VAT": tổng, "PXK": tổng} từ `bkav_totals` (tùy chọn).
    Trả {"rows": [...], "header": [...], "summary": {...}}."""
    tol = max(float(tol or 0), 0.0)
    inv = invoice_rows(core, rec)
    used = [False] * len(inv)
    inv_pos = []
    for r in inv:
        if r["po"] and r["po"] not in inv_pos:
            inv_pos.append(r["po"])
    all_pos = ", ".join(inv_pos)
    rows = []
    n_ok = n_err = n_miss = n_name = 0
    s_tk = {"qty": 0.0, "net": 0.0, "amount": 0.0}
    first_err = ""
    for t in tk["items"]:
        s_tk["qty"] += t["qty"]
        s_tk["net"] += t["net"]
        s_tk["amount"] += t["amount"]
        j = _match_exact(t, inv, used)
        name_diff = False
        if j is None:
            j = _match_fuzzy(t, inv, used)
            name_diff = j is not None
        ir = inv[j] if j is not None else None
        int_msg = check_row_internal(t, ir, ir["po"] if ir else all_pos, tol)
        row = {"tk": t, "inv": ir, "internal": int_msg, "nameDiff": name_diff, "bad": set()}
        if ir is None:
            n_miss += 1
            n_err += 1
            row["status"] = "THIẾU TRÊN INV"
            row["detail"] = append_msg("Không tìm thấy mã hàng trên Invoice", int_msg)
        else:
            used[j] = True
            checks = {"qty": (t["qty"], ir["qty"]), "net": (t["net"], ir["net"]), "price": (t["price"], ir["price"]),
                      "amount": (t["amount"], ir["amount"])}
            row["bad"] = {k for k, (a, b) in checks.items() if differs(a, b, tol)}
            if not name_diff and not row["bad"] and not int_msg:
                n_ok += 1
                row["status"] = "KHỚP"
                row["detail"] = "Khớp hoàn toàn (SL, TL, Giá, Tiền, HS, ĐVT, PO)"
            else:
                n_err += 1
                reason = ""
                if name_diff:
                    n_name += 1
                    row["status"] = "SAI TÊN"
                    reason = append_msg(reason, f"Sai tên ({describe_name_diff(t['raw'], ir['name'])})")
                elif row["bad"]:
                    row["status"] = "LỆCH"
                else:
                    row["status"] = "LỖI TK"
                if "qty" in row["bad"]:
                    reason = append_msg(reason, f"SL (TK:{fmt_short(t['qty'])} {NE} INV:{fmt_short(ir['qty'])})")
                if "net" in row["bad"]:
                    reason = append_msg(reason, f"TL tịnh (TK:{fmt_short(t['net'])} {NE} INV:{fmt_short(ir['net'])})")
                if "price" in row["bad"]:
                    reason = append_msg(reason, f"Đơn giá (TK:{fmt_short(t['price'])} {NE} INV:{fmt_short(ir['price'])})")
                if "amount" in row["bad"]:
                    reason = append_msg(reason, f"Trị giá (TK:{fmt_num(t['amount'])} {NE} INV:{fmt_num(ir['amount'])})")
                if int_msg:
                    reason = append_msg(reason, "Nội bộ TK: " + int_msg)
                row["detail"] = reason
        if row["status"] != "KHỚP" and not first_err:
            first_err = f"{t['tag']} ({t['raw']}): {row['detail']}"
        rows.append(row)
    missing_tk = []
    for j, r in enumerate(inv):
        if not used[j]:
            missing_tk.append({"tk": None, "inv": r, "internal": "", "nameDiff": False, "bad": set(), "status": "CHƯA LÊN TK",
                               "detail": "Có trên Invoice, chưa có trên Tờ khai này"})
    rows += missing_tk
    tot = core.lot_totals(rec)
    inv_sum = {"qty": sum(r["qty"] for r in inv), "amount": sum(r["amount"] for r in inv),
               "gross": float(tot.get("gross") or 0), "kien": float(tot.get("kien") or 0)}
    header = header_checks(core, rec, tk, inv_pos, inv_sum, tol, bkav)
    h_err = sum(1 for h in header if not h["ok"])
    summary = {
        "nTK": len(tk["items"]), "nINV": len(inv), "nOK": n_ok, "nERR": n_err, "nMissINV": n_miss, "nNotOnTK": len(missing_tk),
        "nNameErr": n_name, "sumTK": s_tk, "sumINV": inv_sum, "firstErr": first_err, "headerOK": len(header) - h_err,
        "headerErr": h_err, "nHeader": len(header), "declaredLines": sum(h["lines"] for h in tk["headers"]), "tol": tol,
        "nTKSheets": tk.get("nTK", 1), "ok": n_err == 0 and h_err == 0 and bool(tk["items"]),
    }
    return {"rows": rows, "header": header, "summary": summary, "invPOs": all_pos}


def header_checks(core, rec, tk, inv_pos, inv_sum, tol, bkav=None):
    """Các mục kiểm tra phần đầu tờ khai (BuildSummaryTK: R40 kiện, R41 gross, R46 ngày đi, R47 PO, R49 số hóa đơn,
    R51 ngày phát hành, R53 tổng trị giá, R54 trị giá tính thuế, R64 ghi chú PXK) + số dòng hàng và tổng HĐ VAT / PXK."""
    hs = tk["headers"] or [read_tk_header(Grid([]))]
    multi = len(hs) > 1
    out = []

    def add(tag, title, tk_val, inv_val, ok, detail_ok, detail_bad):
        out.append({"tag": tag, "title": title, "tk": tk_val, "inv": inv_val, "ok": bool(ok), "detail": detail_ok if ok else detail_bad})

    pk = sum(h["pk"] for h in hs)
    gross = sum(h["gross"] for h in hs)
    amt = sum(h["amount"] for h in hs)
    tax = sum(h["taxAmount"] for h in hs)
    sfx = f" ({len(hs)} tờ khai cộng lại)" if multi else ""
    ok = pk > 0 and not differs(pk, inv_sum["kien"], tol)
    add("R40", "Số lượng kiện (PK)", fmt_num(pk) + " PK" + sfx, fmt_num(inv_sum["kien"]) + " PK", ok,
        "Khớp số kiện với Invoice", f"Lệch số kiện (TK={fmt_num(pk)} {NE} INV={fmt_num(inv_sum['kien'])})")
    ok = gross > 0 and not differs(gross, inv_sum["gross"], tol)
    add("R41", "Tổng trọng lượng Gross", fmt_num(gross, 2) + " kg" + sfx, fmt_num(inv_sum["gross"], 2) + " kg", ok,
        "Khớp tổng Gross với Invoice",
        f"Chênh lệch {fmt_num(gross - inv_sum['gross'], 2)} kg (TK={fmt_num(gross, 2)} {NE} INV={fmt_num(inv_sum['gross'], 2)})")
    doc_vn = _iso_to_vn(rec.get("docDate"))
    doc_d = _norm_date(rec.get("docDate"))
    deps = [h["depDate"] for h in hs]
    ok = all(d and _norm_date(d) == doc_d for d in deps)
    shown = " | ".join(d or "(trống)" for d in deps)
    add("R46", "Ngày hàng đi dự kiến", shown, doc_vn + " (ngày chứng từ)", ok, "Đúng ngày chứng từ",
        f"Ngày đi ({shown}) {NE} ngày chứng từ ({doc_vn})")
    hdr_po = " | ".join(h["po"] for h in hs if h["po"])
    miss = [p for p in inv_pos if p.lower() not in hdr_po.lower()]
    ok = not miss and bool(hdr_po)
    add("R47", "Số PO (Ký hiệu & số hiệu)", hdr_po or "(trống)", ", ".join(inv_pos), ok, "Có đủ tất cả PO của Invoice",
        (f"Thiếu PO: {', '.join(miss)} (cần đủ cả: {', '.join(inv_pos)})" if hdr_po else "Tờ khai chưa ghi Ký hiệu và số hiệu (PO)"))
    pxk = str(rec.get("pxkNo") or "").strip()
    invs = [h["invNo"] for h in hs]
    ok = bool(pxk) and all(_same_pxk(core, v, pxk) for v in invs)
    shown = " | ".join(("B - " + v) if v else "(trống)" for v in invs)
    add("R49", "Số hóa đơn (PXKKVCNB)", shown, pxk or "(chưa nhập số PXK)", ok, "Khớp số PXKKVCNB của lô",
        f"Số HĐ trên TK ({' | '.join(v or 'trống' for v in invs)}) {NE} số PXK của lô ({pxk or 'chưa nhập'})")
    dates = [h["invDate"] for h in hs]
    ok = all(d and _norm_date(d) == doc_d for d in dates)
    shown = " | ".join(d or "(trống)" for d in dates)
    add("R51", "Ngày phát hành", shown, doc_vn + " (ngày chứng từ)", ok, "Đúng ngày chứng từ",
        f"Ngày PH ({shown}) {NE} ngày chứng từ ({doc_vn})")
    ok = amt > 0 and not differs(amt, inv_sum["amount"], tol)
    add("R53", "Tổng trị giá hóa đơn", fmt_num(amt) + " VND" + sfx, fmt_num(inv_sum["amount"]) + " VND", ok,
        "Khớp tổng thành tiền Invoice", f"Lệch tổng tiền (TK={fmt_num(amt)} {NE} INV={fmt_num(inv_sum['amount'])})")
    ok = tax > 0 and not differs(tax, inv_sum["amount"], tol)
    add("R54", "Tổng trị giá tính thuế", fmt_num(tax) + " VND" + sfx, fmt_num(inv_sum["amount"]) + " VND", ok,
        "Khớp tổng thành tiền Invoice", f"Lệch trị giá tính thuế (TK={fmt_num(tax)} {NE} INV={fmt_num(inv_sum['amount'])})")
    notes = [h["note"] for h in hs]
    note_px = [extract_pxk(n) for n in notes]
    ok = bool(pxk) and all(_same_pxk(core, p, pxk) for p in note_px)
    add("R64", "Ghi chú (Số PXKKVCNB)", " | ".join(n or "(trống)" for n in notes), f"PXKKVCNB : {pxk}" if pxk else "(chưa nhập số PXK)", ok,
        "Khớp số PXKKVCNB của lô",
        f"Số PXK trong ghi chú ({' | '.join(p or 'trống' for p in note_px)}) {NE} số PXK của lô ({pxk or 'chưa nhập'})")
    declared = sum(h["lines"] for h in hs)
    n_items = len(tk["items"])
    ok = declared > 0 and declared == n_items
    add("R61", "Tổng số dòng hàng của tờ khai", f"{declared} dòng khai báo", f"{n_items} dòng đọc được trên tờ khai", ok,
        "Đọc đủ số dòng hàng khai báo",
        f"Tờ khai khai {declared} dòng nhưng đọc được {n_items} dòng (thiếu trang hoặc dòng không có mô tả)")
    for key, tag, title in (("VAT", "HĐ VAT", "Hóa đơn VAT (file nạp Bkav)"), ("PXK", "PXK", "Phiếu xuất kho (file nạp Bkav)")):
        b = (bkav or {}).get(key)
        if not b:
            continue
        ok = not differs(b["qty"], inv_sum["qty"], tol) and not differs(b["amount"], inv_sum["amount"], tol)
        add(tag, title, f"{fmt_num(b['qty'])} SL | {fmt_num(b['amount'])} VND ({b['rows']} dòng)",
            f"{fmt_num(inv_sum['qty'])} SL | {fmt_num(inv_sum['amount'])} VND", ok, "Khớp tổng SL và thành tiền với Invoice",
            f"Lệch với Invoice (SL {fmt_num(b['qty'])} {NE} {fmt_num(inv_sum['qty'])}; tiền {fmt_num(b['amount'])} {NE} {fmt_num(inv_sum['amount'])})")
    return out


def summary_lines(result, limit=10):
    """Các câu ngắn cho thẻ kết quả trên màn hình."""
    s = result["summary"]
    lines = []
    if s["ok"]:
        lines.append(f"✅  Khớp toàn bộ {s['nTK']} dòng tờ khai và {s['nHeader']} mục phần đầu tờ khai.")
    else:
        if not s["nTK"]:
            lines.append("❌  Chưa đọc được dòng hàng nào (<01>, <02>...) trong tờ khai.")
        else:
            lines.append(f"❌  Dòng hàng: khớp {s['nOK']}/{s['nTK']}, lệch / sai tên / lỗi {s['nERR']}. "
                         f"Phần đầu tờ khai: đúng {s['headerOK']}/{s['nHeader']} mục.")
    if s["nNotOnTK"]:
        lines.append(f"ℹ  {s['nNotOnTK']} dòng Invoice chưa có trên tờ khai này (bình thường nếu lô chia nhiều tờ khai).")
    shown = 0
    for h in result["header"]:
        if not h["ok"] and shown < limit:
            lines.append(f"• {h['title']}: {h['detail']}")
            shown += 1
    for r in result["rows"]:
        if r["status"] in ("KHỚP", "CHƯA LÊN TK") or shown >= limit:
            continue
        t = r["tk"]
        lines.append(f"• Dòng {t['tag']} {t['raw'][:60]}: {r['status']} – {r['detail']}")
        shown += 1
    return lines


# ---------------------------------------------------------------- file Excel kết quả
HEAD_FILL = "1F4E79"
HEAD2_FILL = "2F5597"
OK_FILL, OK_FONT = "C6EFCE", "006100"
ERR_FILL, ERR_FONT = "FFC7CE", "9C0006"
NAME_FILL, NAME_FONT = "FFF2CC", "9C6500"
GREY_FILL, GREY_FONT = "F2F2F2", "595959"
GRID = Side(style="thin", color="C8C8C8")
BOX = Border(left=GRID, right=GRID, top=GRID, bottom=GRID)


def _fill(c):
    return PatternFill("solid", start_color=c, end_color=c)


def _style_range(ws, rng, fill=None, color=None, bold=None):
    for row in ws[rng]:
        for c in row:
            if fill:
                c.fill = _fill(fill)
            if color or bold is not None:
                c.font = Font(color=color or (c.font.color.rgb if c.font and c.font.color and isinstance(c.font.color.rgb, str) else None),
                              bold=c.font.bold if bold is None else bold)


def _merge(ws, rng, value=None, **kw):
    ws.merge_cells(rng)
    c = ws[rng.split(":")[0]]
    if value is not None:
        c.value = value
    return c


def _rich_diff(text, start, end):
    """Ô chữ có đoạn [start:end] tô đỏ đậm (tên khác nhau)."""
    if CellRichText is None or end <= start:
        return text
    parts = []
    if start > 0:
        parts.append(TextBlock(InlineFont(color="806000"), text[:start]))
    parts.append(TextBlock(InlineFont(color="DC0000", b=True), text[start:end]))
    if end < len(text):
        parts.append(TextBlock(InlineFont(color="806000"), text[end:]))
    return CellRichText(parts)


def write_ketqua_sheet(ws, rec, result, label=""):
    s = result["summary"]
    ws["A1"] = "SO SÁNH TỜ KHAI NHÁP vs INVOICE / HÓA ĐƠN VAT / PHIẾU XUẤT KHO"
    ws["A1"].font = Font(bold=True, size=14, color=HEAD_FILL)
    ws["A2"] = (f"Khách: {label or rec.get('customer', '')}  |  PO: {result.get('invPOs') or rec.get('poNumber') or '-'}  |  "
                f"PXK: {rec.get('pxkNo') or '-'}  |  Ngày chứng từ: {_iso_to_vn(rec.get('docDate'))}  |  "
                f"Kiểm tra lúc {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    ws["A2"].font = Font(italic=True, color="595959")
    ws["A3"] = "Sai số cho phép:"
    ws["A3"].font = Font(bold=True)
    ws["C3"] = s["tol"]
    ws["C3"].fill = _fill("FFFF99")
    ws["D3"] = "(0 = so khớp tuyệt đối, lệch bao nhiêu cũng báo; ô số lệch tô đỏ theo ô này)"
    ws["D3"].font = Font(italic=True, color="595959")

    # --- tóm tắt A5:R8
    _merge(ws, "A5:C5", "Số dòng Tờ khai:")
    ws["D5"] = f"{s['nTK']} / {s['declaredLines']}" if s["declaredLines"] else str(s["nTK"])
    _merge(ws, "E5:F5", "Khớp hoàn toàn:")
    ws["G5"] = s["nOK"]
    _merge(ws, "A6:C6", "Số dòng Invoice:")
    ws["D6"] = s["nINV"]
    _merge(ws, "E6:F6", "Số dòng lỗi / lệch:")
    ws["G6"] = s["nERR"]
    _merge(ws, "A7:C7", "Chưa lên Tờ khai:")
    ws["D7"] = s["nNotOnTK"]
    _merge(ws, "E7:F7", "Sai tên / Thiếu INV:")
    ws["G7"] = f"{s['nNameErr']} / {s['nMissINV']}"
    hs = result.get("headers") or []
    _merge(ws, "A8:C8", "Đối chiếu Header TK:")
    _merge(ws, "D8:G8", "Số TK: " + (" | ".join(h["tkNo"] or "-" for h in hs) or "-") + " | PO: "
           + (" | ".join(h["po"] or "-" for h in hs) or "-") + " | HĐ: " + (" | ".join(h["invNo"] or "-" for h in hs) or "-"))
    for r in (5, 6, 7, 8):
        _merge(ws, f"H{r}:R{r}")
    if s["nERR"] == 0 and s["nTK"]:
        ws["H5"] = f"TẤT CẢ {s['nTK']} DÒNG TỜ KHAI KHỚP HOÀN TOÀN VỚI INVOICE (SL, TL, GIÁ, TIỀN, HS, ĐVT, PO)"
        _style_range(ws, "H5:R5", OK_FILL, OK_FONT, True)
        ws["H6"] = "Không phát hiện sai lệch nào trong các dòng hàng của Tờ khai."
    else:
        ws["H5"] = f"PHÁT HIỆN {s['nERR']} DÒNG LỆCH / SAI TÊN / LỖI NỘI BỘ TỜ KHAI" if s["nTK"] else "CHƯA ĐỌC ĐƯỢC DÒNG HÀNG NÀO TRÊN TỜ KHAI"
        _style_range(ws, "H5:R5", ERR_FILL, ERR_FONT, True)
        ws["H6"] = "Lỗi đầu tiên: " + (s["firstErr"] or "-")
    st, si = s["sumTK"], s["sumINV"]
    ws["H7"] = (f"Cộng dòng TK đang check: {fmt_num(st['qty'])} pcs | {fmt_num(st['net'], 2)} kg | {fmt_num(st['amount'])} VND"
                f"   ||   Tổng Invoice: {fmt_num(si['qty'])} pcs | {fmt_num(si['amount'])} VND")
    if s["headerErr"]:
        ws["H8"] = (f"HEADER TK: Đúng {s['headerOK']}/{s['nHeader']} mục | Phát hiện {s['headerErr']} mục sai/lệch "
                    "(xem chi tiết từng dòng bên dưới)")
        _style_range(ws, "H8:R8", NAME_FILL, ERR_FONT)
    else:
        ws["H8"] = f"HEADER TK: KHỚP TOÀN BỘ {s['headerOK']}/{s['nHeader']} MỤC VỚI INVOICE (xem chi tiết bên dưới)"
        _style_range(ws, "H8:R8", OK_FILL, OK_FONT)
    for row in ws["A5:R8"]:
        for c in row:
            c.border = BOX
            c.alignment = Alignment(vertical="center", horizontal=c.alignment.horizontal)
    for ref in ("A5", "A6", "A7", "A8", "E5", "E6", "E7", "D5", "D6", "D7", "G5", "G6", "G7", "H5"):
        ws[ref].font = Font(bold=True, color=ws[ref].font.color.rgb if ws[ref].font.color and isinstance(ws[ref].font.color.rgb, str) else None)
    for ref in ("D5", "D6", "D7", "D8", "G5", "G6", "G7"):
        ws[ref].alignment = Alignment(horizontal="center", vertical="center")
    for r in range(5, 9):
        ws.row_dimensions[r].height = 20

    # --- bảng đối chiếu phần đầu tờ khai (từ dòng 10)
    _merge(ws, "A10:B10", "Dòng TK")
    _merge(ws, "C10:D10", "Mục kiểm tra Header")
    _merge(ws, "E10:I10", "Giá trị trên Tờ khai (TK)")
    _merge(ws, "J10:N10", "Giá trị chuẩn / Invoice (INV)")
    _merge(ws, "O10:P10", "Trạng thái")
    _merge(ws, "Q10:R10", "Chi tiết kiểm tra")
    for row in ws["A10:R10"]:
        for c in row:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = _fill(HEAD2_FILL)
            c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[10].height = 22
    r = 11
    for h in result["header"]:
        _merge(ws, f"A{r}:B{r}", h["tag"])
        _merge(ws, f"C{r}:D{r}", h["title"])
        _merge(ws, f"E{r}:I{r}", h["tk"])
        _merge(ws, f"J{r}:N{r}", h["inv"])
        _merge(ws, f"O{r}:P{r}", "ĐÚNG" if h["ok"] else "SAI / LỆCH")
        _merge(ws, f"Q{r}:R{r}", h["detail"])
        ws[f"A{r}"].alignment = Alignment(horizontal="center", vertical="center")
        ws[f"A{r}"].font = Font(bold=True)
        ws[f"C{r}"].font = Font(bold=True)
        ws[f"E{r}"].alignment = Alignment(wrap_text=True, vertical="center")
        ws[f"J{r}"].alignment = Alignment(wrap_text=True, vertical="center")
        ws[f"Q{r}"].alignment = Alignment(wrap_text=True, vertical="center")
        ws[f"O{r}"].alignment = Alignment(horizontal="center", vertical="center")
        fill, font = (OK_FILL, OK_FONT) if h["ok"] else (ERR_FILL, ERR_FONT)
        _style_range(ws, f"O{r}:P{r}", fill, font, True)
        ws[f"Q{r}"].font = Font(color=font)
        for row in ws[f"A{r}:R{r}"]:
            for c in row:
                c.border = BOX
        ws.row_dimensions[r].height = 30 if max(len(h["tk"]), len(h["detail"])) > 55 else 20
        r += 1

    # --- bảng chi tiết dòng hàng
    hdr_row = r + 1
    first = hdr_row + 1
    heads = ["STT", "Dòng TK", "Tên hàng (Tờ khai)", "SL (TK)", "TL Tịnh (TK)", "Đơn giá (TK)", "Trị giá (TK)", "Dòng INV",
             "Tên hàng (Invoice)", "SL (INV)", "TL Tịnh (INV)", "Đơn giá (INV)", "Thành tiền (INV)", "HS Code", "ĐVT / Tiền tệ",
             "Kiểm tra nội bộ TK", "Trạng thái", "Kết quả chi tiết"]
    for i, t in enumerate(heads, 1):
        c = ws.cell(row=hdr_row, column=i, value=t)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = _fill(HEAD_FILL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    ws.row_dimensions[hdr_row].height = 30
    rr = first
    for stt, row in enumerate(result["rows"], 1):
        t, ir = row["tk"], row["inv"]
        ws.cell(row=rr, column=1, value=stt)
        if t:
            ws.cell(row=rr, column=2, value=t["tag"])
            ws.cell(row=rr, column=3, value=t["raw"])
            for col, k in ((4, "qty"), (5, "net"), (6, "price"), (7, "amount")):
                ws.cell(row=rr, column=col, value=t[k])
            ws.cell(row=rr, column=14, value=t["hs"])
            ws.cell(row=rr, column=15, value=f"{t['u1']}/{t['u2']} ({t['cur']})")
            p = ws.cell(row=rr, column=16, value=row["internal"] or f"OK (PO {t['po']})")
            p.font = Font(color=ERR_FONT, bold=True) if row["internal"] else Font(color=OK_FONT)
            if row["internal"]:
                p.fill = _fill(ERR_FILL)
        if ir:
            ws.cell(row=rr, column=8, value=ir["row"])
            ws.cell(row=rr, column=9, value=ir["name"])
            for col, k in ((10, "qty"), (11, "net"), (12, "price"), (13, "amount")):
                ws.cell(row=rr, column=col, value=ir[k])
        q = ws.cell(row=rr, column=17, value=row["status"])
        d = ws.cell(row=rr, column=18, value=row["detail"])
        st = row["status"]
        if st == "KHỚP":
            q.fill, q.font = _fill(OK_FILL), Font(color=OK_FONT, bold=True)
        elif st == "THIẾU TRÊN INV":
            for c in range(1, 19):
                ws.cell(row=rr, column=c).fill = _fill(ERR_FILL)
                ws.cell(row=rr, column=c).font = Font(color=ERR_FONT, bold=(c == 17))
        elif st == "CHƯA LÊN TK":
            for c in range(1, 19):
                ws.cell(row=rr, column=c).fill = _fill(GREY_FILL)
                ws.cell(row=rr, column=c).font = Font(color=GREY_FONT)
        else:
            d.font = Font(color=ERR_FONT)
            if st == "SAI TÊN":
                q.fill, q.font = _fill(NAME_FILL), Font(color=NAME_FONT, bold=True)
                a, b = t["raw"], ir["name"]
                p0, e1, e2 = diff_span(a, b)
                for col, txt, end in ((3, a, e1), (9, b, e2)):
                    c = ws.cell(row=rr, column=col)
                    c.fill = _fill(NAME_FILL)
                    c.value = _rich_diff(txt, p0, end)
            else:
                q.fill, q.font = _fill(ERR_FILL), Font(color=ERR_FONT, bold=True)
        for c in range(1, 19):
            cell = ws.cell(row=rr, column=c)
            cell.border = BOX
            cell.alignment = Alignment(vertical="center", wrap_text=c in (3, 9, 16, 18),
                                       horizontal="center" if c in (1, 2, 8, 14, 15, 17) else None)
        rr += 1
    last = rr - 1
    if last >= first:
        for col, fmt in (("D", "#,##0.##"), ("J", "#,##0.##"), ("E", "#,##0.00"), ("K", "#,##0.00"),
                         ("F", "#,##0.##"), ("L", "#,##0.##"), ("G", "#,##0"), ("M", "#,##0")):
            for r2 in range(first, last + 1):
                ws[f"{col}{r2}"].number_format = fmt
        # ô số lệch tô đỏ bằng định dạng có điều kiện theo ô $C$3 (0): sửa số trong Excel thì tự tô lại
        red = PatternFill("solid", start_color=ERR_FILL, end_color=ERR_FILL)
        for a, b in (("D", "J"), ("E", "K"), ("F", "L"), ("G", "M")):
            f = f"AND(ISNUMBER(${a}{first}),ISNUMBER(${b}{first}),ROUND(ABS(${a}{first}-${b}{first}),6)>$C$3)"
            ws.conditional_formatting.add(f"{a}{first}:{a}{last}", FormulaRule(formula=[f], fill=red, font=Font(color=ERR_FONT, bold=True)))
            ws.conditional_formatting.add(f"{b}{first}:{b}{last}", FormulaRule(formula=[f], fill=red, font=Font(color=ERR_FONT, bold=True)))
        ws.auto_filter.ref = f"A{hdr_row}:R{last}"
    widths = {"A": 6, "B": 11, "C": 46, "D": 10, "E": 11, "F": 11, "G": 14, "H": 8, "I": 46, "J": 10, "K": 11, "L": 11,
              "M": 14, "N": 11, "O": 15, "P": 30, "Q": 15, "R": 60}
    for k, w in widths.items():
        ws.column_dimensions[k].width = w
    ws.freeze_panes = f"D{first}"
    ws.sheet_view.zoomScale = 90
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    return {"headerRow": hdr_row, "firstRow": first, "lastRow": last}


def write_tokhai_sheet(ws, sections):
    """Tờ khai nguyên văn như đã nạp; nhiều file thì nối liền, cách 2 dòng trống (như macro chế độ ghép thêm)."""
    r = 1
    for _name, rows in sections:
        for row in rows:
            for c, v in enumerate(row, 1):
                if v not in (None, ""):
                    ws.cell(row=r, column=c, value=v if not isinstance(v, str) else nfc(v))
            r += 1
        r += 2
    for c in range(1, 33):
        ws.column_dimensions[get_column_letter(c)].width = 9
    ws.column_dimensions["C"].width = 18


def build_workbook(core, rec, sections, tol=TOL_DEFAULT, label=""):
    """Dựng workbook kết quả và trả (wb, result). Ba sheet chứng từ dựng bằng chính các hàm xuất của phần mềm."""
    wb = Workbook()
    ws = wb.active
    ws.title = "KetQua"
    wb.create_sheet("ToKhai")
    before = set(wb.sheetnames)
    core.build_invoice_pkl_sheet(wb, rec, "Invoice")
    new = [n for n in wb.sheetnames if n not in before]
    if new and new[0] != "Invoice":
        wb[new[0]].title = "Invoice"
    vat = core.build_vat_bkav_sheet(wb, rec, "HoaDon_VAT")
    pxk = core.build_pxk_bkav_sheet(wb, rec, "PXK")
    bkav = {"VAT": bkav_totals(wb["HoaDon_VAT"] if vat is None else vat, 5),
            "PXK": bkav_totals(wb["PXK"] if pxk is None else pxk, 2)}
    tk = read_tokhai(sections)
    result = check_tokhai(core, rec, tk, tol, bkav)
    result["headers"] = tk["headers"]
    write_ketqua_sheet(ws, rec, result, label)
    write_tokhai_sheet(wb["ToKhai"], sections)
    wb.active = 0
    return wb, result


def _free_path(path):
    """Tên file chưa bị khóa: nếu file đang mở trong Excel (không ghi được) thì thêm _2, _3..."""
    base, ext = os.path.splitext(path)
    cands = [path] + [f"{base}_{i}{ext}" for i in range(2, 50)]
    return cands


def save_workbook(wb, path):
    """Ghi file; file cũ đang mở trong Excel (PermissionError) thì ghi sang tên _2, _3... Trả (đường dẫn, có đổi tên)."""
    last_err = None
    for i, p in enumerate(_free_path(path)):
        try:
            wb.save(p)
            return p, i > 0
        except PermissionError as e:
            last_err = e
            continue
    raise ValueError(f"Không ghi được file kiểm tra (file đang mở trong Excel?): {last_err}")


def copy_tokhai_files(paths, folder, customer, s_key):
    """Lưu bản sao tờ khai nháp vào thư mục lô (ToKhaiNhap_<khách>_<ngày>[_2].<đuôi>), trả danh sách đường dẫn mới."""
    import shutil
    out = []
    for i, src in enumerate(paths, 1):
        ext = os.path.splitext(src)[1].lower()
        name = f"ToKhaiNhap_{customer}_{s_key}{'' if len(paths) == 1 else '_' + str(i)}{ext}"
        dst = os.path.join(folder, name)
        try:
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
            out.append(dst)
        except OSError:
            out.append(src)
    return out


def run_check(core, store, rec, paths, tol=TOL_DEFAULT, paste_text=None):
    """Toàn bộ bước ⑤: đọc tờ khai (file và/hoặc đoạn dán), đối chiếu, ghi KiemTraToKhai_<khách>_<ngày>.xlsx vào thư mục lô.
    Trả {"path", "fname", "renamed", "result", "lines", "tkFiles"}. Ném ValueError(thông báo tiếng Việt) khi không làm được."""
    if not rec.get("items"):
        raise ValueError("Lô chưa có dòng hàng nào để đối chiếu với tờ khai.")
    paths = [p for p in (paths or []) if p]
    if not paths and not str(paste_text or "").strip():
        raise ValueError("Chưa chọn file tờ khai nháp.")
    folder = store.ensure_lot_folder(rec)
    s_key = rec.get("scheduleKey") or "tk"
    cust = rec.get("customer") or "khach"
    if str(paste_text or "").strip():  # đoạn dán: lưu thành CSV (tab) trong thư mục lô để mở lại hồ sơ vẫn còn
        p = os.path.join(folder, f"ToKhaiNhap_{cust}_{s_key}_dan.csv")
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            f.write(str(paste_text).replace("\r\n", "\n"))
        paths = paths + [p]
    sections = []
    for p in paths:
        if not os.path.isfile(p):
            raise ValueError(f"Không tìm thấy file tờ khai: {p}")
        try:
            sections.append((os.path.basename(p), rows_from_file(p, core)))
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Không đọc được file tờ khai {os.path.basename(p)}: {e}")
    tk_files = copy_tokhai_files([p for p in paths if os.path.dirname(os.path.abspath(p)) != os.path.abspath(folder)], folder, cust, s_key)
    tk_files = [p for p in paths if os.path.dirname(os.path.abspath(p)) == os.path.abspath(folder)] + tk_files
    label = ((core.PROFILES.get(cust) or {}).get("label") if hasattr(core, "PROFILES") else "") or cust
    wb, result = build_workbook(core, rec, sections, tol, label)
    fname = f"KiemTraToKhai_{cust}_{s_key}.xlsx"
    path, renamed = save_workbook(wb, os.path.join(folder, fname))
    try:
        store.write_lot_card(rec, folder)
    except Exception:
        pass
    return {"path": path, "fname": os.path.basename(path), "renamed": renamed, "result": result,
            "lines": summary_lines(result), "tkFiles": tk_files}

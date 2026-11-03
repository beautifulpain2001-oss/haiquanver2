"""Đọc PO dạng bảng scan khó đọc (VD Able: chữ Hán, nhiều PO trong một file PDF) theo từng ô của bảng.

Không dùng numpy (bản .exe bỏ numpy): mọi phép đo đường kẻ dùng Pillow.
Mỗi dòng hàng trả về trạng thái rõ ràng để người dùng biết dòng nào đã đọc đủ, dòng nào phải kiểm tra, dòng nào chưa đọc được:
  read = "ok"      đọc đủ và SL x đơn giá = thành tiền
  read = "suy_ra"  có ô đọc hỏng nhưng suy ra được từ các ô còn lại (kiểm tra lại)
  read = "loi"     không đọc được (điền tay); read_note ghi phần đã đọc được
"""
import os
import re

os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # Tesseract chạy song song nhiều ô: mỗi tiến trình một luồng cho nhanh

from PIL import Image

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

BOX = getattr(getattr(Image, "Resampling", Image), "BOX")


# ------------------------------------------------------------------ đo đường kẻ bằng Pillow
def dark_profile(img, axis, th=170, box=None):
    """Tỷ lệ điểm tối (0..1) theo từng hàng (axis=0) hoặc từng cột (axis=1) trong vùng box=(l, t, r, b)."""
    c = img.crop(box) if box else img
    c = c.point(lambda v: 255 if v < th else 0)
    c = c.resize((1, c.height), BOX) if axis == 0 else c.resize((c.width, 1), BOX)
    return [v / 255.0 for v in c.getdata()]


def runs(flags, gap=4):
    """Gộp các vị trí liên tiếp (cách nhau tối đa gap) thành một vạch; trả vị trí giữa mỗi vạch."""
    out = []
    for i, f in enumerate(flags):
        if f:
            if out and i - out[-1][-1] <= gap:
                out[-1].append(i)
            else:
                out.append([i])
    return [int(sum(r) / len(r)) for r in out]


def deskew(img):
    """Xoay nhẹ cho đường kẻ ngang thật thẳng (scan hay lệch 0.3-1 độ): chọn góc làm các vạch ngang sắc nhất."""
    small = img.resize((img.width // 4, img.height // 4), BOX)
    best_a, best_s = 0.0, -1.0
    a = -1.5
    while a <= 1.5001:
        r = small.rotate(a, resample=Image.BILINEAR, fillcolor=255)
        prof = dark_profile(r, 0, 150, (int(r.width * 0.08), 0, int(r.width * 0.92), r.height))
        s = sum(p * p for p in prof)
        if s > best_s:
            best_a, best_s = a, s
        a = round(a + 0.25, 2)
    return img.rotate(best_a, resample=Image.BILINEAR, fillcolor=255) if abs(best_a) > 1e-6 else img


# ------------------------------------------------------------------ khung bảng
def table_grid(img):
    """(các đường ngang của bảng đã bù đường bị khuyết, các đường dọc). [] nếu không thấy bảng."""
    W, H = img.size
    x0, x1 = int(W * 0.08), int(W * 0.92)
    prof = dark_profile(img, 0, 170, (x0, 0, x1, H))
    ys = runs([p > 0.3 for p in prof], 4)
    if len(ys) < 3:
        return [], []
    diffs = [b - a for a, b in zip(ys, ys[1:])]
    small = [d for d in diffs if 25 <= d <= 120]
    if not small:
        return [], []
    mode = max(set(round(d / 3) * 3 for d in small), key=[round(d / 3) * 3 for d in small].count)
    near = sorted(d for d in small if abs(d - mode) <= mode * 0.2)
    pitch = near[len(near) // 2]
    # đoạn đường kẻ liên tục từ khung tiêu đề; chỗ khuyết bù theo bước đều
    start = next((i for i, d in enumerate(diffs) if abs(d - pitch) <= pitch * 0.25), None)
    if start is None:
        return [], []
    full = [ys[start]]
    for y in ys[start + 1:]:
        gap = y - full[-1]
        n = round(gap / pitch)
        if n < 1:
            continue
        if gap > pitch * 4 and len(full) >= 3:
            break
        if n > 1 and abs(gap - n * pitch) > pitch * 0.35 * n:
            if len(full) >= 3:
                break
            full = [y]
            continue
        for k in range(1, n):
            full.append(int(full[-1] + gap / n))
        full.append(y)
    if len(full) < 3:
        return [], []
    # đường dọc đo ở vài dòng dữ liệu đầu (bỏ dòng tiêu đề)
    top = full[1] + 6
    xs = []
    for k in (1, 3, 6):  # dòng đầu trước (trang chỉ có 1 dòng hàng thì các dòng dưới đã ngoài bảng)
        bot = min(full[-1], full[1] + k * pitch) - 6
        xs = runs([p > 0.6 for p in dark_profile(img, 1, 200, (0, top, W, max(bot, top + 10)))], 5)
        if len(xs) >= 7:
            break
    if len(xs) < 7:
        return [], []
    left, right = xs[0], xs[-1]

    def inside(y0, y1):  # dòng thuộc bảng khi cả hai viền trái/phải còn liền nét
        lo = dark_profile(img, 1, 200, (left - 20, y0 + 4, left + 20, y1 - 4))
        hi = dark_profile(img, 1, 200, (right - 20, y0 + 4, right + 20, y1 - 4))
        return max(lo) > 0.6 or max(hi) > 0.6  # scan lệch/cong: một trong hai viền còn thấy là đủ

    kept = [full[0], full[1]]
    for y0, y1 in zip(full[1:-1], full[2:]):  # cắt phần ngoài bảng (khung chữ ký, chữ viết tay)
        if not inside(y0, y1):
            break
        kept.append(y1)
    while inside(kept[-1], kept[-1] + pitch):  # đường kẻ ngang mờ nên bị khuyết ở cuối bảng: nối tiếp theo bước đều
        kept.append(kept[-1] + pitch)
    return kept, xs


# ------------------------------------------------------------------ OCR từng ô
def _ocr(cell, config):
    if cell.width < 6 or cell.height < 6:
        return ""
    c = cell.resize((int(cell.width * 1.6), int(cell.height * 1.6)), Image.LANCZOS)
    try:
        return pytesseract.image_to_string(c, lang="eng", config=config).strip()
    except Exception:
        return ""


NUM = "--psm 7 -c tessedit_char_whitelist=0123456789,."
INT = "--psm 7 -c tessedit_char_whitelist=0123456789"
SPEC = "--psm 7 -c tessedit_char_whitelist=0123456789*xX%^"
REF = "--psm 7 -c tessedit_char_whitelist=VN0123456789-"


def vnd_candidates(t):
    """Số tiền VND từ chuỗi OCR như '5,239.00 đ' ('5,239,004': dấu chấm thành phẩy, chữ đ thành số 4/1). Mọi số tiền trên PO
    đều có phần thập phân .00 nên thử cắt 2 chữ số cuối, và cắt thêm 1 ký tự nếu chữ đ bị đọc thành số. Trả danh sách số nguyên."""
    d = re.sub(r"\D", "", t or "")
    out = []
    if len(d) >= 3 and d.endswith("00"):
        out.append(int(d[:-2]))
    if len(d) >= 4 and d[:-1].endswith("00"):
        out.append(int(d[:-3]))
    if not out and d and 2 <= len(d) <= 9:  # không thấy phần thập phân: coi cả chuỗi là số nguyên
        out.append(int(d))
    return [x for x in dict.fromkeys(out) if x > 0]


def close(a, b):
    """Cùng độ dài, lệch tối đa 1 chữ số (OCR hay nhầm 0/3/8, 1/7)."""
    a, b = str(int(a)), str(int(b))
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


# ------------------------------------------------------------------ Able
def _catalog_index(catalog):
    """[(mã, mục, phi, dày, dài, gam, giá, có_in)] từ mã dạng 38*5*460*250g hoặc 38*5*460*250g-ko-in."""
    out = []
    for it in catalog:
        m = re.fullmatch(r"(\d+)\*(\d+)\*(\d+)\*(\d+(?:\.\d+)?)g(-ko-in)?", str(it.get("code") or ""))
        if m:
            out.append((it["code"], it, m.group(1), m.group(2), m.group(3), m.group(4), float(it.get("price") or 0), not m.group(5)))
    return out


def _dist(a, b):
    return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))


def _solve_from(r, idx, in_hint):
    qs = list(dict.fromkeys(int(re.sub(r"\D", "", x)) for x in r["qty_t"] if re.sub(r"\D", "", x) and len(re.sub(r"\D", "", x)) <= 7))
    ps = list(dict.fromkeys(v for x in r["price_t"] for v in vnd_candidates(x)))
    ams = list(dict.fromkeys(v for x in r["amount_t"] for v in vnd_candidates(x)))
    return solve_row(qs, ps, ams, r["digits"], idx, in_hint)


def solve_row(qs, ps, ams, spec_digits, idx, in_hint=None):
    """Chọn mặt hàng + SL + đơn giá + thành tiền khớp nhất từ các cách đọc của từng ô.
    qs/ps/ams: danh sách giá trị có thể (OCR nhiều cách). spec_digits: chuỗi số đọc được ở ô quy cách (phi*dày*dài).
    Trả (mục, qty, price, amount, read, note) hoặc None. read = ok (mọi ô khớp nhau) | suy_ra (phải suy từ ô khác)."""
    prices = sorted({c[6] for c in idx if c[6]})
    def like(x, v):  # đơn giá đọc hỏng: lệch 1 chữ số, hoặc mất chữ số đầu (',239' của 5,239)
        return close(x, v) or (len(str(v)) >= 3 and str(int(x)).endswith(str(v)))
    cand_p = [x for x in prices if x in ps] + [x for x in prices if x not in ps and any(like(x, v) for v in ps if v)]
    price_known = bool(cand_p)
    if not cand_p:
        cand_p = prices
    best = None
    for price in cand_p:
        for q in qs:
            if any(abs(q * price - am) <= 1 for am in ams):
                best = (price, q, "ok")  # SL và thành tiền đọc được khớp nhau với một đơn giá đã học
                break
        if best:
            break
        for am in ams:  # SL đọc hỏng: suy từ thành tiền / đơn giá (khi chưa biết đơn giá thì phải khớp SL đã đọc)
            if am % price == 0 and 0 < am // price < 5_000_000 and (price_known or not qs or am // price in qs):
                best = (price, am // price, "suy_ra")
                break
        if best:
            break
        if not ams and qs and price_known:  # thành tiền đọc hỏng: SL x đơn giá
            best = (price, qs[0], "suy_ra")
            break
    if not best:
        return None
    price, qty, how = best
    length = spec_digits[-3:] if len(spec_digits) >= 3 else ""
    cands = [c for c in idx if abs(c[6] - price) < 1e-9]
    if length and cands:
        dmin = min(_dist(c[4], length) for c in cands)
        near = [c for c in cands if _dist(c[4], length) == dmin]
        if dmin > 1 or len({c[4] for c in near}) > 1:
            how = "suy_ra"
        cands = near
    if not cands:
        return None
    pick = None
    if in_hint is not None:
        pick = next((c for c in cands if c[7] == in_hint), None)
    if pick is None:
        pick = next((c for c in cands if c[7]), cands[0])  # chưa phân biệt in / không in: lấy bản in (loại phổ biến)
    return pick[1], int(qty), int(round(price)), int(round(qty * price)), how, len(cands)


def read_able_page(img, idx, page_no=1, on_row=None):
    """Đọc một trang PO Able. Trả (số hợp đồng, dòng [dict], tổng SL, tổng tiền, ghi chú)."""
    img = deskew(img)
    W, H = img.size
    ys, xs = table_grid(img)
    if not ys or len(xs) < 7:
        return "", [], None, None, "không thấy khung bảng"
    # cột tính từ bên phải: ghi chú | thành tiền | đơn giá | SL | quy cách
    cols = {"ref": (xs[-2], xs[-1]), "amount": (xs[-3], xs[-2]), "price": (xs[-4], xs[-3]), "qty": (xs[-5], xs[-4]), "spec": (xs[-6], xs[-5])}
    ncol = (xs[1], xs[-6]) if len(xs) >= 8 else (xs[0], xs[-6])
    idx_rows = list(zip(ys[1:-1], ys[2:]))

    def read_row(span):
        y0, y1 = span

        def cell(key, cfg, shrink=10):
            a, b = cols[key]
            return _ocr(img.crop((a + shrink, y0 + 8, b - shrink, y1 - 8)), cfg)
        spec_t = cell("spec", SPEC)
        r = {"spec_t": spec_t, "digits": re.sub(r"\D", "", spec_t), "qty_t": [cell("qty", INT)], "price_t": [cell("price", NUM)],
             "amount_t": [cell("amount", NUM)], "ref_t": cell("ref", REF), "y": span}
        sol = _solve_from(r, idx, None)
        if not sol or sol[4] != "ok":  # cách đọc đầu chưa khớp: đọc lại từng ô bằng chế độ khác rồi mới kết luận
            r["qty_t"].append(cell("qty", "--psm 8 -c tessedit_char_whitelist=0123456789"))
            r["price_t"].append(cell("price", "--psm 8 -c tessedit_char_whitelist=0123456789,."))
            r["amount_t"].append(cell("amount", "--psm 8 -c tessedit_char_whitelist=0123456789,."))
        ink = img.crop((ncol[0] + 8, y0 + 8, ncol[1] - 8, y1 - 8)).point(lambda v: 255 if v < 150 else 0).getbbox()
        r["name_w"] = (ink[2] - ink[0]) if ink else 0
        if on_row:
            on_row()
        return r

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(read_row, idx_rows))
    name_w = [r["name_w"] for r in rows]
    # dòng tổng (大写金额): không có quy cách, là dòng cuối
    total_q = total_a = None
    if rows and len(re.sub(r"\D", "", rows[-1]["spec_t"])) < 5:
        last = rows.pop()
        name_w.pop()
        tq = [int(re.sub(r"\D", "", x)) for x in last["qty_t"] if re.sub(r"\D", "", x)]
        ta = [v for x in last["amount_t"] for v in vnd_candidates(x)]
        total_q = tq[0] if tq else None
        total_a = ta[0] if ta else None
    # bản in (印刷纸管) hay không in (纸管): chữ Hán dài hơn ở ô tên; chỉ tin khi hai nhóm độ rộng tách biệt rõ
    in_flags = [None] * len(rows)
    if len(rows) >= 3 and max(name_w) > 0:
        lo, hi = min(name_w), max(name_w)
        if (hi - lo) / hi > 0.22:
            mid = (lo + hi) / 2
            in_flags = [w > mid for w in name_w]
    # số hợp đồng ở phía trên bảng
    po = ""
    try:
        top = ys[0]
        head = img.crop((int(W * 0.45), max(0, top - 330), int(W * 0.95), max(0, top - 10)))
        head = head.resize((head.width * 2, head.height * 2), Image.LANCZOS)
        txt = pytesseract.image_to_string(head, lang="eng", config="--psm 6")
        txt = re.sub(r"(?<=\d) (?=\d)", "", txt)
        found = re.findall(r"(?<!\d)(20\d{6}\s?[-–]\s?\d{5})(?!\d)", txt)
        po = re.sub(r"\s+", "", found[-1]).replace("–", "-") if found else ""
    except Exception:
        po = ""
    out = []
    for i, r in enumerate(rows, 1):
        qs = [int(re.sub(r"\D", "", x)) for x in r["qty_t"] if re.sub(r"\D", "", x) and len(re.sub(r"\D", "", x)) <= 7]
        qs = list(dict.fromkeys(qs))
        ps = list(dict.fromkeys(v for x in r["price_t"] for v in vnd_candidates(x)))
        ams = list(dict.fromkeys(v for x in r["amount_t"] for v in vnd_candidates(x)))
        sol = solve_row(qs, ps, ams, r["digits"], idx, in_flags[i - 1])
        ref = re.search(r"VN?\d{4}-\d{4}-\d{3}|20\d{2}-\d{3,4}-\d{3}", r["ref_t"]) or None
        base = {"page": page_no, "idx": i, "spec_t": r["spec_t"], "ref": (ref.group(0) if ref else r["ref_t"]), "po": po}
        if sol:
            item, qty, price, amount, how, nc = sol
            out.append({**base, "code": item["code"], "name": item["name"], "qty": qty, "price": price, "amount": amount, "read": how,
                        "read_note": "" if how == "ok" else "suy ra từ các ô còn lại, kiểm tra với PO"})
        else:
            got = []
            if r["spec_t"]:
                got.append(f"quy cách “{r['spec_t']}”")
            if qs:
                got.append(f"SL {qs[0]}")
            if ps:
                got.append(f"giá {ps[0]:,}")
            out.append({**base, "code": "", "name": "", "qty": 0, "price": 0, "amount": 0, "read": "loi",
                        "read_note": "Không đọc được dòng này, hãy nhập tay" + (f" (máy chỉ thấy: {', '.join(got)})" if got else "")})
    return po, out, total_q, total_a, ""


def read_able_pdf(core, path, catalog, scale=4, progress=None):
    """Đọc mọi trang PO Able dạng scan. Trả {rows, pages, check}. rows = danh sách dòng có trạng thái; check = câu nói về việc tổng có khớp PO.
    progress(text, fraction 0..1) được gọi trong lúc đọc để giao diện hiện tiến trình. [] nếu không phải bảng Able / không đọc được gì."""
    if core.pdfium is None or pytesseract is None:
        return {"rows": [], "pages": 0, "check": ""}
    idx = _catalog_index(catalog)
    if not idx:
        return {"rows": [], "pages": 0, "check": ""}
    import threading
    doc = core.pdfium.PdfDocument(path)
    total_pages = len(doc)
    rows, notes, pages = [], [], 0
    lock = threading.Lock()
    for n in range(total_pages):
        if progress:
            progress(f"Đang đọc trang {n + 1}/{total_pages}…", n / total_pages)
        img = core.auto_rotate_scan(doc[n].render(scale=scale).to_pil()).convert("L")
        done = [0]

        def on_row(n=n):
            with lock:
                done[0] += 1
                if progress:
                    progress(f"Đang đọc trang {n + 1}/{total_pages} · {done[0]} dòng đã xong", (n + min(0.95, done[0] / 40.0)) / total_pages)
        po, got, tq, ta, why = read_able_page(img, idx, n + 1, on_row)
        if not got:
            continue
        pages += 1
        sa = sum(r["amount"] for r in got)
        bad = sum(1 for r in got if r["read"] == "loi")
        if ta and abs(sa - ta) <= 1 and not bad:
            notes.append(f"Trang {n + 1}: {len(got)} dòng, tổng tiền khớp PO ✓")
        elif ta:
            notes.append(f"Trang {n + 1}: tổng tiền đọc được {sa:,.0f} ≠ tổng trên PO {ta:,.0f} — có dòng sai hoặc chưa đọc")
        rows += got
    if progress:
        progress("Đã đọc xong, đang kiểm tra…", 1.0)
    return {"rows": rows, "pages": pages, "check": "; ".join(notes)}

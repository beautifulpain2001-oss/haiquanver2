"""Trạng thái một lô hàng đang làm trong giao diện mới. Thuần Python (không Qt) để test được.

Mọi tính toán/đọc/xuất/lưu đều gọi các hàm lot_* của lõi (`core` = hongthien_desktop_app),
nên giao diện và các kiểm thử dùng chung một đường xử lý.
"""

import datetime
import os


class Lot:
    def __init__(self, core, store):
        self.core, self.store = core, store
        self.reset(None)

    # ---- khởi tạo / đổi khách -------------------------------------------------
    def reset(self, customer):
        self.customer = customer
        self.items = []
        self.po_dates = {}
        self.schedules = None  # Shirai: các ngày giao của PO {ngày: {dateStr, items}}
        self.selected_dates = []  # ngày giao được chọn để khai; chọn nhiều ngày = một invoice, một tờ khai
        self.record_id = None  # mã hồ sơ đang sửa (None = hồ sơ mới)
        self.po_files = []  # file PO gốc đã nạp (được lưu cùng chứng từ)
        self.read_text = ""  # câu tóm tắt kết quả đọc PO (hiện ở đầu bước ③)
        self.rule_note = ""
        self.po_auto, self.po_touched = False, False
        self.pxk_auto, self.pxk_touched = False, False  # số PXK tự điền (số lớn nhất + 1) / người dùng đã tự sửa
        self.exported = {}  # ô chứng từ của hồ sơ (vat, pxk, pkl, tk) -> file
        self.files = []  # mọi file đã xuất trong lô này, để hiển thị
        self.saved = False
        self.skip_h = False  # Kodi: Invoice không lấy cột Thành Tiền
        self.form = {"doc_date": datetime.date.today().strftime("%Y-%m-%d"), "po": "", "po_date": "", "pxk": "", "hd": "", "tk": ""}
        if customer:
            self.apply_defaults()

    def apply_defaults(self):
        d = self.core.lot_defaults(self.customer)
        self.form.update(xe=d["xe"], driver=d["driver"], ldd=d["ldd"], tare=d["tare"], pay_days=d["pay_days"],
                         delivery=d["delivery"], luong=d["luong"])

    def fill_next_po(self):
        """Khách có công thức số PO (poGen, VD Betterial HT202610 + số thứ tự): PO còn trống thì điền số kế tiếp và gán cho các dòng chưa có số PO."""
        if str(self.form.get("po", "")).strip() or self.po_touched or self.record_id or not self.customer:
            return
        nxt = self.store.next_po_number(self.customer, self.form.get("doc_date", ""))
        if nxt:
            self.form["po"], self.po_auto = nxt, True
            for it in self.items:
                if not str(it.get("po") or "").strip():
                    it["po"] = nxt

    def fill_next_pxk(self):
        """Số PXK còn trống thì điền số kế tiếp (lớn nhất đã có + 1); người dùng sửa tay thì không điền lại."""
        if str(self.form.get("pxk", "")).strip() or self.pxk_touched or self.record_id:
            return
        nxt = self.store.next_pxk()
        if nxt:
            self.form["pxk"], self.pxk_auto = nxt, True

    def fill_vehicle_defaults(self):
        """Biển số, lái xe còn trống thì lấy từ thông tin khách (người dùng vừa lưu ở mục Khách hàng)."""
        prof = self.core.PROFILES.get(self.customer) or {}
        for k, pk in (("xe", "xe"), ("driver", "driver")):
            if not str(self.form.get(k, "")).strip() and prof.get(pk):
                self.form[k] = prof[pk]

    def select_customer(self, customer):
        if customer != self.customer:
            self.reset(customer)

    @property
    def profile(self):
        return self.core.PROFILES[self.customer]

    @property
    def is_best(self):
        return bool(self.customer) and self.core.is_best_docset(self.profile)

    @property
    def fixed_order(self):
        """Khách chỉ đặt một mã hàng cố định (VD Sunlu): không đọc file PO, chỉ xác nhận số PO, số lượng, đơn giá."""
        return bool(self.customer) and self.customer not in self.core.BUILTIN_CUSTOMERS and self.core.is_fixed_order(self.profile)

    def fixed_defaults(self):
        """Số PO kế tiếp (3 phần), ngày PO, số lượng và đơn giá gần nhất để điền sẵn."""
        return self.core.lot_fixed_order_defaults(self.store, self.customer)

    def confirm_fixed_order(self, po, po_date, qty, price):
        """Tạo lô một dòng hàng từ số liệu người dùng xác nhận. Ném ValueError (tiếng Việt) nếu thiếu/sai."""
        po = str(po or "").strip()
        items = self.core.lot_fixed_order_items(self.store, self.customer, po, qty, price, self.form.get("tare", ""))
        self.items = items
        self.form["po"], self.form["po_date"] = po, str(po_date or "").strip()
        self.po_dates = {po: self.form["po_date"]}
        self.po_touched, self.po_auto = True, False
        self.schedules, self.selected_dates, self.po_files = None, [], []
        it = items[0]
        self.read_text = f"Đơn {po}: {it['ten_sp']} — {it['qty']:,} {it.get('unit', '')} × {it['price']:,} đ."
        self.saved = False
        return items

    @property
    def multi_po(self):
        """Khách gom nhiều PO một lô (khách đã học)."""
        return bool(self.customer) and self.customer not in self.core.BUILTIN_CUSTOMERS

    # ---- nạp PO ----------------------------------------------------------------
    def read_po(self, path, append=False, progress=None):
        """Đọc PO (chạy được ở luồng nền: không đụng trạng thái). Trả kết quả để `apply_po` áp dụng.
        progress(text, fraction) báo tiến trình đọc (nếu có)."""
        res = self.core.lot_load_po(self.store, path, self.customer, self.form.get("tare", ""), self.items, append, self.po_dates, progress)
        res["path"], res["append"] = path, append
        return res

    def apply_po(self, res):
        if not res["ok"]:
            return False
        if res["customer"] != self.customer:  # app tự nhận ra khách theo nội dung file
            self.customer = res["customer"]
            self.apply_defaults()
        if res.get("path"):
            self.po_files = (self.po_files if res.get("append") else []) + [res["path"]]
        self.items = res["items"]
        catalog = self.store.items_for_customer(self.customer) if self.customer else []
        self.rule_note = ""
        if res.get("raw_text") and self.customer and self.customer not in self.core.BUILTIN_CUSTOMERS:
            self.core.attach_sources(self.items, res["raw_text"])  # dòng PO gốc của từng dòng hàng: để chọn lại số đúng khi máy đọc sai
            rules = self.store.read_rules(self.customer)
            if rules:
                fixed = self.core.apply_read_rules(self.items, rules)
                self.core.lot_recalc(self.items, self.customer, self.form.get("tare", ""))
                self.rule_note = f"Đã đọc theo quy tắc đã học cho khách này (sửa {fixed} dòng)." if fixed else "Đã áp quy tắc đọc đã học cho khách này."
        self.core.mark_read(self.items, catalog)
        for it in self.items:  # nhớ file PO và trang của từng dòng để mở đúng chỗ khi cần soát
            it.setdefault("po_file", res.get("path") or "")
        rep = res.get("read_report") or self.core.read_report(self.items)
        self.read_text = (rep.get("text", "") if res.get("read_report") else "") + ((" " + self.rule_note) if self.rule_note else "")
        self.po_dates = res["po_dates"]
        self.form["po"] = res["po"] or self.form["po"]
        if res["po_date"]:
            self.form["po_date"] = res["po_date"]
        if res["schedules"]:
            self.schedules = res["schedules"]
            self.selected_dates = list(self.schedules)  # mặc định: cả PO là một invoice
        else:
            self.schedules, self.selected_dates = None, []
        self.record_id = None
        self.saved = False
        return True

    def set_dates(self, keys):
        """Chọn các ngày giao để khai (invoice và tờ khai chỉ gồm những ngày này). Ném ValueError nếu không chọn ngày nào."""
        keys = [k for k in (self.schedules or {}) if k in keys]
        if not keys:
            raise ValueError("Phải chọn ít nhất một ngày giao để khai.")
        self.selected_dates = keys
        self.items = self.core.lot_merge_dates(self.schedules, keys)
        self.saved = False

    # ---- dòng hàng -------------------------------------------------------------
    def new_item_values(self):
        return self.core.lot_item_defaults(self.customer, str(self.form.get("po", "")).split(" + ")[-1], self.form.get("tare", ""))

    def save_item(self, vals, idx=None):
        base = self.items[idx] if idx is not None else None
        item = self.core.lot_item_from_values(self.store, self.customer, vals, self.form.get("tare", ""), base)
        if base is None:
            item["read"] = "tay"  # dòng thêm bằng tay
        elif base.get("read") in ("loi", "suy_ra"):
            item["read"], item["read_note"] = "tay", "Đã nhập/sửa tay"  # người dùng đã xác nhận dòng máy không đọc chắc
        if idx is None:
            self.items.append(item)
        else:
            self.items[idx] = item
        self.saved = False
        return item

    def delete_item(self, idx):
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
            self.saved = False

    def recalc(self):
        self.core.lot_recalc(self.items, self.customer, self.form.get("tare", ""))
        self.saved = False

    def normalize(self):
        for i, it in enumerate(self.items, 1):
            it["stt"] = i
            it["amount"] = round(float(it.get("qty", 0)) * float(it.get("price", 0)))

    # ---- trạng thái đọc PO theo từng dòng -------------------------------------
    def row_status(self, it):
        """(mã, nhãn, ghi chú): mã ok/check/bad/hand hoặc '' khi dòng không có thông tin đọc (PO đọc theo cách cũ)."""
        r = it.get("read")
        code = {"ok": "ok", "suy_ra": "check", "loi": "bad", "tay": "hand"}.get(r, "")
        return code, self.core.READ_LABELS.get(r, ""), str(it.get("read_note") or "")

    def has_read_info(self):
        return any(it.get("read") for it in self.items)

    def read_counts(self):
        n = {"ok": 0, "check": 0, "bad": 0, "hand": 0}
        for it in self.items:
            c = self.row_status(it)[0]
            if c:
                n[c] += 1
        return n

    def attention_rows(self):
        """Chỉ số các dòng cần xem: chưa đọc được trước, rồi dòng phải suy ra."""
        bad = [i for i, it in enumerate(self.items) if it.get("read") == "loi"]
        chk = [i for i, it in enumerate(self.items) if it.get("read") == "suy_ra"]
        return bad + chk

    # ---- chọn lại số đúng từ các số máy đọc được trong dòng PO ------------------------------
    def pick_info(self, idx):
        """Thông tin để người dùng chọn lại số: dòng PO gốc, các số trong dòng (đúng như in trên PO), SL/đơn giá máy đang dùng. None nếu dòng không có dòng PO gốc."""
        it = self.items[idx] if 0 <= idx < len(self.items) else None
        if not it or not it.get("src"):
            return None
        return {"src": it["src"], "numbers": self.core.line_numbers(it["src"]), "qty": it.get("qty"), "price": it.get("price")}

    def apply_pick(self, idx, qty_text, price_text):
        """Người dùng chọn/gõ SL và đơn giá đúng. Chọn từ các số máy đọc được ở cả hai ô -> nhớ quy tắc vị trí cho khách (lần sau tự đọc đúng);
        gõ tay thì chỉ ghi nhật ký chỗ máy đọc sai. Trả câu thông báo cho người dùng."""
        info = self.pick_info(idx)
        if info is None:
            raise ValueError("Dòng này không có dòng PO gốc để chọn lại.")
        nums = info["numbers"]
        try:
            qty = float(str(qty_text).replace(",", "").strip())
            price = float(str(price_text).replace(",", "").strip())
        except ValueError:
            raise ValueError("Số lượng và đơn giá phải là số.")
        if qty <= 0 or price <= 0:
            raise ValueError("Số lượng và đơn giá phải lớn hơn 0.")
        it = self.items[idx]
        old_q, old_p = it.get("qty"), it.get("price")
        def pos(txt):
            t = str(txt).strip()
            return nums.index(t) if t in nums else None
        pq, pp = pos(qty_text), pos(price_text)
        num = lambda v: int(v) if v == int(v) else v
        it["qty"], it["price"], it["amount"] = num(qty), num(price), round(qty * price)
        it["read"], it["read_note"] = "tay", "Đã chọn/sửa từ PO"
        self.core.lot_recalc(self.items, self.customer, self.form.get("tare", ""))
        self.saved = False
        fixes = []
        for field, label, old, new, p_ in (("qty", "Số lượng", old_q, num(qty), pq), ("price", "Đơn giá", old_p, num(price), pp)):
            if str(old) != str(new):
                fixes.append({"field": field, "label": label, "read": old, "correct": new, "how": "chọn từ số máy đọc" if p_ is not None else "gõ tay",
                              "line": info["src"], "po": it.get("po", ""), "file": os.path.basename(it.get("po_file") or "")})
        rule, msg = None, ""
        if pq is not None and pp is not None and pq != pp and self.customer not in self.core.BUILTIN_CUSTOMERS:
            n = len(nums)
            rule = {"qty": pq - n, "price": pp - n, "n": n}
            if pp + 1 < n and abs(qty * price - float(nums[pp + 1].replace(",", ""))) <= max(1.0, price * 1e-3):
                rule["amount"] = pp + 1 - n  # số ngay sau đơn giá đúng là thành tiền: dùng để tự kiểm tra lần sau
            msg = (f"Đã nhớ cách đọc cho khách này: SL là số thứ {abs(rule['qty'])} tính từ cuối dòng, đơn giá là số thứ {abs(rule['price'])}. "
                   "Lần sau máy tự đọc theo cách này (dòng nào lệch cách bố trí thì máy bỏ qua).")
        elif fixes:
            msg = "Đã sửa dòng và ghi lại chỗ máy đọc sai (số bạn nhập không nằm trong các số máy đọc được nên chưa tạo quy tắc tự đọc)."
        if fixes or rule:
            self.store.learn_read_rule(self.customer, rule, fixes)
        return msg or "Đã cập nhật dòng."

    # ---- tra mặt hàng để thêm dòng ---------------------------------------------
    def search_items(self, query, limit=60):
        return self.core.lot_search_items(self.store, self.customer, query, limit) if self.customer else []

    def add_from_catalog(self, hit, qty, po=""):
        item = self.core.lot_item_from_catalog(self.store, self.customer, hit, qty, po or str(self.form.get("po", "")).split(" + ")[-1], self.form.get("tare", ""))
        item["read"] = "tay"
        self.items.append(item)
        self.saved = False
        return item

    def row_issues(self, it):
        out = []
        if float(it.get("qty") or 0) <= 0:
            out.append("Số lượng bằng 0")
        if float(it.get("kg") or 0) <= 0:
            out.append("Thiếu kg/chiếc")
        if float(it.get("div") or 0) <= 0:
            out.append("Thiếu SL/kiện")
        return out

    # ---- hồ sơ, kiểm tra, xuất, lưu -------------------------------------------
    def record(self):
        self.normalize()
        form = dict(self.form, customer=self.customer, schedule="", po_dates=self.po_dates, record_id=self.record_id, po_files=self.po_files)
        return self.core.lot_build_record(self.store, form, self.items)

    def totals(self):
        return self.core.lot_totals(self.record())

    def validate(self):
        """(lỗi chặn xuất, cảnh báo cho phép xuất), mỗi mục là một câu tiếng Việt."""
        errors, warns = [], []
        if not self.customer:
            return ["Chưa chọn khách hàng."], warns
        if not self.items:
            return ["Chưa có dòng hàng nào. Hãy nạp file PO ở bước ② hoặc thêm dòng ở bước ③."], warns
        bad = [i for i, it in enumerate(self.items, 1) if it.get("read") == "loi"]
        if bad:
            errors.append(f"Còn {len(bad)} dòng chưa đọc được từ PO (dòng {', '.join(map(str, bad))}). Hãy nhập tay (bấm đúp vào dòng) hoặc xóa dòng đó.")
            return errors, warns
        chk = [i for i, it in enumerate(self.items, 1) if it.get("read") == "suy_ra"]
        if chk:
            warns.append(f"Dòng {', '.join(map(str, chk))} máy phải suy ra từ ô khác của PO: hãy so lại với PO.")
        if not str(self.form.get("po", "")).strip():
            warns.append("Chưa nhập số PO.")
        if not str(self.form.get("pxk", "")).strip():
            warns.append("Chưa nhập số PXK (file Invoice sẽ dùng số tạm).")
        warns += [w for w in self.core.check_lot(self.record()) if w not in warns]
        return errors, warns

    def _note_file(self, mode, name, path, now):
        entry = {"mode": mode, "label": self.core.LOT_MODE_LABELS.get(mode, mode), "name": name, "path": path, "time": now}
        self.files = [f for f in self.files if f["mode"] != mode] + [entry]
        slot = {"VAT": "vat", "PXK": "pxk", "PKL": "pkl", "ALL": None}.get(mode)
        if slot:
            self.exported[slot] = {"name": name, "path": path, "time": now}
        if mode == "PLX" and "tk" not in self.exported:
            self.exported["tk"] = {"name": name, "path": path, "time": now}

    def export(self, mode):
        """mode "ALL": mỗi chứng từ một file riêng. Mode khác: chỉ chứng từ đó.
        Trả {"files": [...], "problems": [...], "dsh": None}."""
        rec = self.record()
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        if mode == "ALL":
            res = self.core.lot_export_each(self.store, rec, skip_h=self.skip_h)
            for f in res["files"]:
                self._note_file(f["mode"], f["name"], f["path"], now)
            return {"files": res["files"], "problems": res["problems"], "dsh": None}
        res = self.core.lot_export(self.store, rec, mode, skip_h=self.skip_h)
        self._note_file(mode, res["fname"], res["path"], now)
        one = {"mode": mode, "label": self.core.LOT_MODE_LABELS.get(mode, mode), "name": res["fname"], "path": res["path"]}
        return {"files": [one], "problems": res["problems"], "dsh": res["dsh"]}

    def save(self):
        rec = self.core.lot_save_new(self.store, self.record(), self.exported)
        self.record_id = rec["id"]
        self.saved = True
        return rec

    def folder(self):
        return self.store.get_record_folder_path(self.record())

    def load_record(self, rec):
        """Nạp hồ sơ đã lưu để làm tiếp."""
        self.reset(rec.get("customer") or "kodi")
        g = lambda k, d="": rec.get(k, d) or d
        self.form.update(doc_date=g("docDate", self.form["doc_date"]), po=g("poNumber"), po_date=g("poDate"), pxk=g("pxkNo"),
                         hd=g("hdNo"), tk=g("tkNo"), luong=g("luong", "Xanh"), xe=g("xeNo", self.form.get("xe", "")),
                         driver=g("driver", self.form.get("driver", "")), ldd=g("lddSeq", self.form.get("ldd", "")))
        if rec.get("payDays"):
            self.form["pay_days"] = str(rec["payDays"])
        self.form["delivery"] = g("deliveryDate")
        self.po_dates = dict(rec.get("poDates") or {})
        self.items = [dict(x) for x in rec.get("items", [])]
        self.exported = {k: v for k, v in (rec.get("files") or {}).items() if v}
        self.files = []
        self.record_id = rec.get("id")
        self.saved = True

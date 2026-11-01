"""Trạng thái một lô hàng đang làm trong giao diện mới. Thuần Python (không Qt) để test được.

Mọi tính toán/đọc/xuất/lưu đều gọi các hàm lot_* của lõi (`core` = hongthien_desktop_app),
nên giao diện Tkinter cũ và giao diện mới cho kết quả giống hệt nhau.
"""

import datetime


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
    def multi_po(self):
        """Khách gom nhiều PO một lô (khách đã học)."""
        return bool(self.customer) and self.customer not in self.core.BUILTIN_CUSTOMERS

    # ---- nạp PO ----------------------------------------------------------------
    def read_po(self, path, append=False):
        """Đọc PO (chạy được ở luồng nền: không đụng trạng thái). Trả kết quả để `apply_po` áp dụng."""
        return self.core.lot_load_po(self.store, path, self.customer, self.form.get("tare", ""), self.items, append, self.po_dates)

    def apply_po(self, res):
        if not res["ok"]:
            return False
        if res["customer"] != self.customer:  # app tự nhận ra khách theo nội dung file
            self.customer = res["customer"]
            self.apply_defaults()
        self.items = res["items"]
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

    def row_issues(self, it):
        out = []
        if float(it.get("qty") or 0) <= 0:
            out.append("Số lượng bằng 0")
        if float(it.get("kg") or 0) <= 0:
            out.append("Thiếu kg/chiếc")
        if float(it.get("div") or 0) <= 0:
            out.append("Thiếu SL/kiện")
        if not it.get("hs"):
            out.append("Thiếu mã HS")
        return out

    # ---- hồ sơ, kiểm tra, xuất, lưu -------------------------------------------
    def record(self):
        self.normalize()
        form = dict(self.form, customer=self.customer, schedule="", po_dates=self.po_dates, record_id=self.record_id)
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
        if not str(self.form.get("po", "")).strip():
            warns.append("Chưa nhập số PO.")
        if not str(self.form.get("pxk", "")).strip():
            warns.append("Chưa nhập số PXK (file Invoice sẽ dùng số tạm).")
        warns += [w for w in self.core.check_lot(self.record()) if w not in warns]
        return errors, warns

    def _note_file(self, mode, name, path, now):
        entry = {"mode": mode, "label": self.core.LOT_MODE_LABELS.get(mode, mode), "name": name, "path": path, "time": now}
        self.files = [f for f in self.files if f["mode"] != mode] + [entry]
        slot = {"VAT": "vat", "PXK": "pxk", "PKL": "pkl", "B11": "tk", "ALL": None}.get(mode)
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

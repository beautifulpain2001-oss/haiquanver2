"""Đọc PO: báo dòng đáng ngờ (read = ok / suy_ra), kiểm tổng PO, OCR lại khi lớp chữ PDF kém."""

import pytest

import hongthien_desktop_app as app

L1 = {"qty": 1000, "price": 31500}
L2 = {"qty": 500, "price": 89700}  # 31.500.000 + 44.850.000 = 76.350.000


class TestPoTotalCheck:
    def test_matches(self):
        r = app.po_total_check("1 ...\nTổng cộng 76.350.000\n", [L1, L2])
        assert r.startswith("✅") and "76,350,000" in r

    def test_mismatch_reports_amount(self):
        r = app.po_total_check("Tổng cộng 80.000.000", [L1, L2])
        assert r.startswith("⚠") and "80,000,000" in r and "3,650,000" in r

    def test_total_includes_vat_8(self):
        assert app.po_total_check("Tổng cộng 82.458.000", [L1, L2]).startswith("✅")

    def test_total_on_next_line(self):
        assert app.po_total_check("Tổng cộng\n76.350.000", [L1, L2]).startswith("✅")

    def test_chinese_label(self):
        assert app.po_total_check("合计 76,350,000.00", [L1, L2]).startswith("✅")

    def test_no_total_line(self):
        assert app.po_total_check("không có dòng tổng", [L1, L2]) == ""

    def test_no_lines(self):
        assert app.po_total_check("Tổng cộng 76.350.000", []) == ""

    @pytest.mark.parametrize("txt", ["Tổng cộng số lượng 1.500", "Total Qty 1500", "Tổng cộng SL: 1500"])
    def test_quantity_totals_are_not_money_totals(self, txt):
        assert app.po_total_check(txt, [L1, L2]) == ""

    def test_quantity_total_does_not_hide_money_total(self):
        r = app.po_total_check("Tổng cộng số lượng 1.500\nTổng cộng 76.350.000", [L1, L2])
        assert r.startswith("✅")


class TestKodiRead:
    def test_sample_po_all_ok(self, store):
        _, _, lines = app.parse_kodi_po_text("\n".join(
            ["ĐƠN ĐẶT HÀNG Số: 03102026 - 01KDHT"]
            + [l for l in __import__("test_po_parsers").KODI_PO_TEXT.splitlines() if l[:1].isdigit() and "chiếc" in l]), store.kodi_items, store)
        assert lines and all(x["read"] == "ok" for x in lines)

    def test_line_without_amount_is_guess(self, store):
        txt = "Số: 03102026 - 01KDHT\n1 Ống giấy phi 76 x 9 x 1000mm chiếc 1000 31.500\n"
        _, _, lines = app.parse_kodi_po_text(txt, store.kodi_items, store)
        assert lines and lines[0]["read"] == "suy_ra" and "đoán" in lines[0]["read_note"]

    def test_unknown_item_is_flagged(self, store):
        txt = "Số: 03102026 - 01KDHT\n1 Ống giấy phi 99 x 7 x 1234mm chiếc 100 1.000 100.000\n"
        _, _, lines = app.parse_kodi_po_text(txt, store.kodi_items, store)
        assert lines and lines[0]["read"] == "suy_ra" and "danh mục Kodi" in lines[0]["read_note"]


PO_HEAD = "ĐƠN ĐẶT HÀNG\nSố PO: DP2026-0457 Ngày 18/10/2026\n"
CAT = [
    {"code": "DP-76-1000", "name": "Ống giấy phi 76 x 5 x 1000mm", "price": 21000, "kg": 1.25, "div": 5, "unit": "chiếc"},
    {"code": "DP-PAD-01", "name": "Tấm lót giấy 1100 x 1100mm", "price": 15500.5, "kg": 0.45, "div": 50, "unit": "tấm"},
]


def generic(text, **prof_extra):
    prof = app.build_custom_profile("dai", {"po_pattern": app.infer_po_pattern("DP2026-0457"), **prof_extra})
    return app.parse_generic_po_text(text, prof, CAT)[2]


class TestGenericRead:
    def test_amount_matches_is_ok(self):
        lines = generic(PO_HEAD + "1 | DP-76-1000 | 1.500 | 21.000 | 31.500.000\n")
        assert lines[0]["read"] == "ok"

    def test_qty_and_price_only_is_guess(self):
        lines = generic(PO_HEAD + "1 | DP-76-1000 | 1.500 | 21.000\n")
        assert lines[0]["read"] == "suy_ra" and "SL" in lines[0]["read_note"]

    def test_no_amount_column_flag_accepts_it(self):
        lines = generic(PO_HEAD + "1 | DP-76-1000 | 1.500 | 21.000\n", noAmountCol=True)
        assert lines[0]["read"] == "ok"

    def test_no_price_uses_learned_price(self):
        lines = generic(PO_HEAD + "1 | DP-76-1000 | 1.500\n")
        assert lines[0]["read"] == "suy_ra" and "giá đã học" in lines[0]["read_note"]


class TestConfRead:
    def test_levels(self):
        assert app._conf_read(None)["read"] == "ok" and app._conf_read(3)["read"] == "ok" and app._conf_read(2)["read"] == "ok"
        assert app._conf_read(1)["read"] == "suy_ra" and app._conf_read(0)["read"] == "suy_ra"
        assert app._conf_read(1, no_amount_col=True)["read"] == "ok"
        assert app._conf_read(0, no_amount_col=True)["read"] == "suy_ra"


class TestLooseLine:
    LINE = "1 Ông giấy phi 40 x 4 x 467mm 1,000.00 20,000.00 20,000,000.00"
    ITEMS = [{"code": "B1", "name": "Ống giấy phi 40 x 4 x 467mm", "price": 20000}]

    def test_ex_returns_confidence(self):
        r = app._loose_po_line_ex(self.LINE, self.ITEMS)
        assert r and len(r) == 4 and r[3] == 3 and r[1] == 1000

    def test_old_signature_unchanged(self):
        r = app._loose_po_line(self.LINE, self.ITEMS)
        assert r and len(r) == 3 and r[1] == 1000


class TestLoadPo:
    @pytest.fixture
    def learned(self, store):
        store.save_learned_customer("dai", {"name": "CÔNG TY ĐẠI PHÁT", "label": "Đại Phát",
                                            "po_pattern": app.infer_po_pattern("DP2026-0457")}, CAT)
        yield "dai"
        app.PROFILES.pop("dai", None)

    def test_total_ok_then_mismatch(self, store, learned, tmp_path):
        body = PO_HEAD + "1 | DP-76-1000 | 1.500 | 21.000 | 31.500.000\nTổng cộng 31.500.000\n"
        f = tmp_path / "po.txt"
        f.write_text(body, encoding="utf-8")
        res = app.lot_load_po(store, str(f), learned)
        assert res["ok"] and res["po_check"].startswith("✅")
        f.write_text(body.replace("Tổng cộng 31.500.000", "Tổng cộng 40.000.000"), encoding="utf-8")
        res = app.lot_load_po(store, str(f), learned)
        assert res["po_check"].startswith("⚠") and "⚠" in res["msg"]

    def test_kodi_total_mismatch_in_message(self, store, tmp_path, monkeypatch):
        import test_po_parsers
        f = tmp_path / "po.pdf"
        f.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(app, "extract_text_from_pdf_or_image_offline",
                            lambda *a, **k: test_po_parsers.KODI_PO_TEXT.replace("76.350.000", "70.000.000"))
        res = app.lot_load_po(store, str(f), "kodi")
        assert res["ok"] and res["po_check"].startswith("⚠") and "⚠" in res["msg"]


def test_force_ocr_reads_scanned_pdf(tmp_path):
    pytest.importorskip("pytesseract")
    if not app.ocr_available():
        pytest.skip("máy không có Tesseract")
    pdf = tmp_path / "scan.pdf"
    app.make_scanned_pdf(str(pdf), ["TONG CONG 123456"])
    assert "123456" in app.extract_text_from_pdf_or_image_offline(str(pdf), force_ocr=True)

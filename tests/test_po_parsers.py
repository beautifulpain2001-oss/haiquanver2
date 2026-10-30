import datetime

import pytest

import hongthien_desktop_app as app

KODI_PO_TEXT = """CÔNG TY TNHH KODI NEW MATERIAL VIỆT NAM
ĐƠN ĐẶT HÀNG Số: 03102026 - 01KDHT
Bắc Ninh, ngày 03 tháng 10 năm 2026
1 Ống giấy phi 76 x 9 x 1000mm chiếc 31.500 31.500.000
2 Ống giấy phi 152.4x12x1000mm chiếc 89.700 44.850.000
Tổng cộng 76.350.000
"""

TESA_PAGE = """tesa site Hai Phong
Purchase Order: 8600226354
10 136,000 PC 39778-90019-00 26,500.00 100 36,040,000.00
PAPER CORE 33.2X2.65X19MM, BLACK
Net Value: VND 36,040,000.00
"""


class TestKodi:
    def test_header_and_lines(self, store):
        po, po_date, lines = app.parse_kodi_po_text(KODI_PO_TEXT, store.kodi_items, store)
        assert po == "03102026-01KDHT"
        assert po_date == "03/10/2026"
        assert [(x["ten_sp"], x["qty"], x["price"], x["amount"]) for x in lines] == [
            ("Ống giấy phi 76 x 9 x 1000mm", 1000, 31500, 31_500_000),
            ("Ống giấy phi 152.4 x 12 x 1000mm", 500, 89700, 44_850_000),
        ]

    def test_qty_is_derived_from_amount_over_price(self, store):
        _, _, lines = app.parse_kodi_po_text(KODI_PO_TEXT, store.kodi_items, store)
        first = lines[0]
        assert first["ma_sp"] == "TM91120-001-00001"
        assert first["kien"] == 200  # 1000 / 5 chiếc mỗi kiện
        assert first["net"] == 1960.0  # 1000 x 1.96 kg
        assert first["gross"] == 1961.0  # + bì 1 kg

    def test_remembered_norm_overrides_catalog(self, store):
        store.remember_item_norm("Ống giấy phi 76 x 9 x 1000mm", div=4, kg=2.0)
        _, _, lines = app.parse_kodi_po_text(KODI_PO_TEXT, store.kodi_items, store, tare_val=0.5)
        assert lines[0]["kien"] == 250
        assert lines[0]["net"] == 2000.0
        assert lines[0]["gross"] == 2000.5

    def test_no_product_lines(self, store):
        assert app.parse_kodi_po_text("không có dòng hàng", store.kodi_items, store) == ("", "", [])


class TestTesa:
    def test_single_page(self):
        res = app.parse_tesa_po_page(TESA_PAGE)
        assert res["po"] == "8600226354"
        assert res["code"] == "39778-90019-00"
        assert res["qty"] == 136000
        assert res["price"] == pytest.approx(265)
        assert res["net"] == pytest.approx(36_040_000)
        assert res["check"] is True

    def test_header_strip_po_wins_over_body(self):
        # Dải tiêu đề phóng to 2x được ưu tiên để phân biệt số 5/8
        text = TESA_PAGE.replace("8600226354", "8600226384") + "\n@@HDR@@\n8600226354\n"
        assert app.parse_tesa_po_page(text)["po"] == "8600226354"

    def test_page_without_po_is_skipped(self):
        assert app.parse_tesa_po_page("trang điều khoản chung, không có PO") is None

    def test_multi_page_text_uses_catalog(self, store):
        text = TESA_PAGE + "\n@@PAGE@@\n" + TESA_PAGE.replace("8600226354", "8600226355")
        first_po, lines = app.parse_tesa_po_text(text, store.tesa_items, store)
        assert first_po == "8600226354"
        assert [x["po"] for x in lines] == ["8600226354", "8600226355"]
        line = lines[0]
        assert line["ten_sp"].startswith("Ống lõi giấy phi 33.2 x 2.65 x 19mm_Black")
        assert line["amount"] == 36_040_000
        assert line["kien"] == 4  # 136000 / 34000
        assert line["net"] == 680.0


class TestShiraiExcel:
    def test_splits_schedules_and_maps_catalog(self, store, make_shirai_po):
        path = make_shirai_po(
            [
                ("SVN01", "Carton Box FUL-1080SDNA (W936xD186xH405)", datetime.datetime(2026, 10, 30), 600, 25214),
                ("SVN02", "Carton Box PNN-4585GHNA(W927xD129xH387)", datetime.datetime(2026, 11, 5), 400, 19500),
            ]
        )
        po, schedules = app.parse_shirai_po_excel(path, store)
        assert po == "202637HT"
        assert sorted(schedules) == ["05.11", "30.10"]
        assert schedules["05.11"]["dateStr"] == "2026-11-05"

        box = schedules["05.11"]["items"][0]
        assert box["ten_sp"] == "Thùng Carton Box PNN-4585GHNA(W927xD129xH387)"
        assert box["ma_sp"] == "TM91071-001-00345"
        assert box["kg"] == 0.8
        assert box["net"] == 320.0
        assert box["amount"] == 7_800_000
        assert box["ma_kh"] == "SVN02"

    def test_box_is_moved_before_matching_pad(self, store, make_shirai_po):
        d = datetime.datetime(2026, 10, 30)
        path = make_shirai_po(
            [
                ("SVN03", "Pad PNN-4585GH(AF_1:W810xD5xH95)", d, 400, 3200),
                ("SVN02", "Carton Box PNN-4585GHNA(W927xD129xH387)", d, 400, 19500),
            ]
        )
        _, schedules = app.parse_shirai_po_excel(path, store)
        items = schedules["30.10"]["items"]
        assert [x["ten_sp"].split(" PNN")[0] for x in items] == ["Thùng Carton Box", "Tấm lót Pad"]
        assert [x["stt"] for x in items] == [1, 2]

    def test_khong_in_suffix_is_stripped(self, store, make_shirai_po):
        path = make_shirai_po([("", "Carton Box FUL-1080SDNA (không in)", datetime.datetime(2026, 10, 30), 10, 1000)])
        _, schedules = app.parse_shirai_po_excel(path, store)
        assert schedules["30.10"]["items"][0]["ten_sp"] == "Thùng Carton Box FUL-1080SDNA"

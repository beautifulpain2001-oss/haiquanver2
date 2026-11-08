"""Một khách có hai nhà máy (VD Deli Hải Dương / Deli Bắc Ninh) học thành hai khách riêng: mã chứng từ Bkav riêng từng nhà (`bkavId`),
ĐVT theo mặt hàng trên Invoice, và Phụ lục X Word giữ nguyên in đậm / ngắt dòng của mẫu. Dữ liệu giả."""

import io
import zipfile

import pytest

import hongthien_desktop_app as app
import mau_rieng

FAKE = {"name": "CÔNG TY TNHH HAI NHÀ THỬ", "label": "HaiNha HD", "mst": "0100000088", "addr": "Lô Z, KCN Thử, Hải Phòng", "unit": "Chiếc",
        "tare": 1.0, "payDays": 30, "linePo": False, "poInDocs": False, "nameStyle": "ma_ten", "bkavId": "hainha{dd}/{mm} hd"}
ITEMS = [{"code": "340000001", "name": "340000001 Ống giấy thử 1250*76*3mm", "ten_hq": "Ống giấy thử 1250*76*3mm", "unit": "Chiếc",
          "price": 13944, "div": 5, "kg": 0.78, "hs": "48229090"}]

# đoạn có nhãn thường + giá trị in đậm, và ô ký tên có ngắt dòng <w:br/>
_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    '<w:p><w:r><w:t xml:space="preserve">Số lượng: </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>{{tong_sl}} cái / chiếc</w:t></w:r></w:p>'
    '<w:p><w:r><w:t>-{{ten}}</w:t></w:r></w:p>'
    '<w:p><w:r><w:t xml:space="preserve">ngày </w:t></w:r><w:r><w:t>{{dd}}</w:t></w:r><w:r><w:br/></w:r>'
    '<w:r><w:rPr><w:b/></w:rPr><w:t>Người đại diện</w:t></w:r></w:p>'
    '</w:body></w:document>'
)


def make_docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", _DOC)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def rec(store):
    store.save_learned_customer("hainha_hd", dict(FAKE), [dict(x) for x in ITEMS])
    it = ITEMS[0]
    items = [{"stt": 1, "po": "", "ma_sp": it["code"], "ten_sp": it["name"], "ten_hq": it["ten_hq"], "unit": "Chiếc", "qty": 4505, "price": 13944,
              "amount": 4505 * 13944, "div": 5, "kg": 0.78, "hs": "48229090", "tare": 1.0}]
    app.lot_recalc(items, "hainha_hd", "1")
    return app.lot_build_record(store, {"customer": "hainha_hd", "doc_date": "2026-10-29", "po": "4521707280", "po_date": "10/10/2026",
                                        "pxk": "00000308", "hd": "00004442", "tk": ""}, items)


def test_bkav_id_from_profile(rec):
    assert app.get_vat_and_pxk_ids(rec) == ("hainha29/10 hd", "hainha29/10 hd")
    app.PROFILES["hainha_hd"]["bkavId"] = ""
    assert app.get_vat_and_pxk_ids(rec) == ("hainha_hd29.10", "hainha_hd29.10")  # không đặt thì như cũ: mã khách + ngày.tháng


def test_bkav_id_is_editable_customer_field():
    assert "bkavId" in dict(app.CUSTOMER_FIELDS)


def test_vat_name_has_code_once_and_invoice_unit_follows_item(rec):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = app.build_vat_bkav_sheet(wb, rec)
    assert ws["B6"].value == "hainha29/10 hd"
    assert ws["C6"].value == "340000001 Ống giấy thử 1250*76*3mm"  # tên đã có mã: không ghi lặp mã
    assert not ws["D6"].value  # không ghi PO trên hóa đơn
    ws = app.build_pkl_standard_sheet(wb, rec)
    assert ws["D13"].value == "Chiếc"


def test_word_form_keeps_bold_and_line_breaks(rec):
    prof = app.PROFILES["hainha_hd"]
    consts = {"name": app.HT_NAME, "addr": app.ADDR_HT, "mst": app.MST_HT, "date": app._iso_to_date, "words": app.num_to_vn_words}
    out, unknown = mau_rieng.fill_docx(make_docx(), mau_rieng.batch_values(rec, prof, consts), mau_rieng.item_values(rec))
    assert unknown == []
    xml = zipfile.ZipFile(io.BytesIO(out)).read("word/document.xml").decode()
    assert '<w:t xml:space="preserve">Số lượng: </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">4.505 cái / chiếc</w:t>' in xml
    assert "-340000001 Ống giấy thử 1250*76*3mm" in xml
    assert '<w:t xml:space="preserve">29</w:t></w:r><w:r><w:br/></w:r>' in xml and "Người đại diện" in xml


# ---- Sale Contract: khách không gửi PO, Hồng Thiên lập hợp đồng (số theo quy chuẩn như Sunlu), xuất chung bộ chứng từ ----
def test_po_gen_parts_suffix_and_no_sequence():
    import datetime
    d = datetime.date(2026, 10, 10)
    assert app.po_gen_parts("HT{yyyymmdd}-HD", d) == ("HT", "20261010", 0, "-HD")
    assert app.po_gen_parts("HT{yymm}{nn}-BN", d) == ("HT", "2610", 2, "-BN")
    assert app.po_gen_parts("ABCDE{yymmdd}{nnnn}", d) == ("ABCDE", "261010", 4, "")
    assert app.po_gen_parts("HT", d) is None


@pytest.fixture
def sc_rec(store):
    prof = dict(FAKE, poGen="HT{yyyymmdd}-HD", extraDocs="SC", deliveryTerm="DAP BAC NINH")
    store.save_learned_customer("hainha_sc", prof, [dict(x) for x in ITEMS])
    it = ITEMS[0]
    hit = {"ma_sp": it["code"], "ten_sp": it["name"], "price": it["price"], "unit": "Chiếc", "div": 5, "kg": 0.78, "hs": "48229090"}
    items = [app.lot_item_from_catalog(store, "hainha_sc", hit, 4505, "HT20261010-HD", "1")]
    return app.lot_build_record(store, {"customer": "hainha_sc", "doc_date": "2026-10-29", "po": "HT20261010-HD", "po_date": "10/10/2026",
                                        "pxk": "00000308", "hd": "00004442", "tk": ""}, items)


def test_contract_number_and_bundle(store, sc_rec):
    prof = app.PROFILES["hainha_sc"]
    assert app.is_contract_order(prof) and not app.is_fixed_order(prof)
    d = app.lot_contract_defaults(store, "hainha_sc", "2026-10-10")
    assert (d["po"], d["prefix"], d["date"], d["suffix"], d["po_date"]) == ("HT20261010-HD", "HT", "20261010", "-HD", "10/10/2026")
    assert app.lot_bundle_modes({"customer": "hainha_sc"}) == ["PKL", "VAT", "PXK", "SC"]
    assert app.lot_mode_label("SC") == "Sale Contract 销售合同"


def test_sale_contract_sheet_like_sample(sc_rec):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = app.build_sale_contract_sheet(wb, sc_rec)
    assert ws["A1"].value == "SALE CONTRACT销售合同"
    assert ws["B2"].value == "Contract No: HT20261010-HD" and ws["B3"].value == "Date:  10/10/2026"
    assert ws["D4"].value == FAKE["name"] and ws["D5"].value == FAKE["addr"]
    assert [ws[f"{c}7"].value for c in "ABCDEFG"] == ["Ống giấy thử 1250*76*3mm", 340000001, "Chiếc", 4505, 13944, "=D7*E7", "Theo YC của KH"]
    assert ws["A8"].value == "Tổng tiền hàng" and ws["F8"].value == "=SUM(F7:F7)" and ws["F10"].value == "=F8+F9"
    texts = [ws[f"A{r}"].value for r in range(11, 20)]
    assert "Delivery term: DAP BAC NINH" in texts and "T/T  After receiving goods.  30 days" in texts
    assert any(str(t).startswith("Số tài khoản ngân hàng: ") for t in texts)


def test_full_bundle_has_sale_contract(sc_rec):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    app.build_full_bundle(wb, sc_rec, "29.10")
    assert "SaleContract_29.10" in wb.sheetnames


def test_lot_state_confirm_contract(store, sc_rec):
    from ui_qt.state import Lot
    lot = Lot(app, store)
    lot.select_customer("hainha_sc")
    assert lot.contract_order and not lot.fixed_order
    assert lot.contract_defaults()["suffix"] == "-HD"
    with pytest.raises(ValueError):
        lot.confirm_contract("", "10/10/2026")
    with pytest.raises(ValueError):
        lot.confirm_contract("HT20261010-HD", "2026-10-10")
    lot.items = [dict(sc_rec["items"][0], po="")]
    lot.confirm_contract("HT20261010-HD", "10/10/2026")
    assert lot.form["po"] == "HT20261010-HD" and lot.form["po_date"] == "10/10/2026" and lot.items[0]["po"] == "HT20261010-HD"

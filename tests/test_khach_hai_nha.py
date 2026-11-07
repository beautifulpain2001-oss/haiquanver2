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

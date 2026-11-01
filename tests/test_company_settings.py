"""Thông tin công ty (Cài đặt) và thông tin khách (mục Khách hàng) sửa được, lưu lại, và đi vào các file Excel xuất ra."""

import openpyxl
import pytest

import hongthien_desktop_app as app

ORIGINAL_BANK = [
    "Tên tài khoản: CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN",
    "Vào tài khoản số:  0301101186008  Tại Ngân hàng MB Bank - CN Bắc Ninh",
    "hoặc Tài khoản :   115623456668  Ngân hàng TMCP Công Thương Việt Nam",
]


def all_text(wb):
    return "\n".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None)


def export_all_text(store, customer="kodi"):
    rec = next(r for r in store.records if r["customer"] == customer)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    app.build_full_bundle(wb, rec, rec.get("scheduleKey", "30.10"))
    return all_text(wb)


def test_default_company_reproduces_original_constants(store):
    assert app.DNTT_BANK == ORIGINAL_BANK
    assert (app.HT_NAME, app.MST_HT, app.HT_TEL, app.HT_SWIFT) == (
        "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN", "2300723980", "02223.692.235", "MSCBVNVX")
    assert app.PROFILES["tesa"]["customs"]["exporterCode"] == "2300723980"


def new_company(**kw):
    c = dict(app.COMPANY_DEFAULTS)
    c.update(name="CÔNG TY TNHH THỬ NGHIỆM MỚI", mst="0101234567", addr="1 Đường Thử, Hà Nội", bank1_acc="9999888877", **kw)
    return c


def test_company_edit_flows_into_every_document(store):
    before = export_all_text(store, "tesa")
    assert "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN" in before
    store.set_company(new_company())
    after = export_all_text(store, "tesa")
    assert "CÔNG TY TNHH THỬ NGHIỆM MỚI" in after and "1 Đường Thử, Hà Nội" in after and "0101234567" in after
    assert "9999888877" in after
    assert "BAO BÌ HỒNG THIÊN" not in after.upper().replace("  ", " ") and "2300723980" not in after  # không sót chỗ nào
    assert app.PROFILES["tesa"]["customs"]["exporterCode"] == "0101234567"  # tờ khai: người xuất khẩu


def test_company_edit_persists_and_does_not_leak_to_other_stores(store, data_dir, tmp_path):
    store.set_company(new_company())
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    assert again.company_info()["name"] == "CÔNG TY TNHH THỬ NGHIỆM MỚI" and app.HT_NAME == "CÔNG TY TNHH THỬ NGHIỆM MỚI"
    other = app.DedicatedDataStore(base_dir=str(tmp_path / "kho_khac"))
    assert app.HT_NAME == "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN" and app.DNTT_BANK == ORIGINAL_BANK
    assert other.company_info()["name"] == "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN"


def test_second_bank_is_optional(store):
    store.set_company(new_company(bank2_acc="", bank2_name=""))
    assert len(app.DNTT_BANK) == 2 and "9999888877" in app.DNTT_BANK[1]


@pytest.mark.parametrize("patch,msg", [({"name": " "}, "Tên công ty"), ({"mst": "12ab"}, "Mã số thuế"), ({"addr": ""}, "Địa chỉ")])
def test_company_validation(store, patch, msg):
    bad = new_company()
    bad.update(patch)
    with pytest.raises(ValueError, match=msg):
        store.set_company(bad)
    assert app.HT_NAME == "CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN"  # lỗi thì không đổi gì


def test_builtin_customer_edit_flows_into_documents_and_persists(store, data_dir):
    store.update_customer("kodi", {"name": "CÔNG TY KODI TÊN MỚI", "mst": "2400903599", "addr": "Địa chỉ Kodi mới, Bắc Ninh", "driver": "Nguyễn Văn Thử"})
    text = export_all_text(store, "kodi")
    assert "CÔNG TY KODI TÊN MỚI" in text and "2400903599" in text and "Địa chỉ Kodi mới, Bắc Ninh" in text
    assert "CÔNG TY TNHH KODI NEW MATERIAL VIỆT NAM" not in text
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    assert app.PROFILES["kodi"]["name"] == "CÔNG TY KODI TÊN MỚI" and app.PROFILES["kodi"]["driver"] == "Nguyễn Văn Thử"
    assert app.PROFILES["kodi"]["unit"] == "chiếc"  # phần không sửa vẫn giữ nguyên
    assert again.profile_overrides["kodi"]["mst"] == "2400903599"


def test_builtin_edit_does_not_leak_to_fresh_store(store, tmp_path):
    store.update_customer("tesa", {"name": "TESA ĐÃ SỬA"})
    app.DedicatedDataStore(base_dir=str(tmp_path / "moi"))
    assert app.PROFILES["tesa"]["name"] == "CÔNG TY TNHH TESA SITE HẢI PHÒNG"


def test_customer_validation(store):
    with pytest.raises(ValueError, match="Tên công ty"):
        store.update_customer("kodi", {"name": ""})
    with pytest.raises(ValueError, match="Mã số thuế"):
        store.update_customer("kodi", {"mst": "abc"})
    with pytest.raises(ValueError, match="Không tìm thấy"):
        store.update_customer("khong_co", {"name": "X"})


def test_add_customer_then_edit_it(store, data_dir):
    key = store.add_customer({"name": "CÔNG TY TNHH ABC VIỆT NAM", "mst": "0312345678", "addr": "KCN Test, Hải Phòng"})
    assert key in app.PROFILES and app.PROFILES[key]["mst"] == "0312345678" and app.PROFILES[key]["addrKho"] == "KCN Test, Hải Phòng"
    store.update_customer(key, {"addr": "Địa chỉ mới", "addrKho": "Kho mới", "driver": "Lái A"})
    again = app.DedicatedDataStore(base_dir=str(data_dir))
    assert key in again.custom_profiles and app.PROFILES[key]["addr"] == "Địa chỉ mới" and app.PROFILES[key]["driver"] == "Lái A"
    with pytest.raises(ValueError, match="tên công ty"):
        store.add_customer({"name": ""})


def test_ocr_check_is_remembered(monkeypatch):
    calls = []
    monkeypatch.setattr(app, "pytesseract", type("T", (), {"get_tesseract_version": staticmethod(lambda: calls.append(1))}))
    monkeypatch.setattr(app, "pdfium", object())
    monkeypatch.setattr(app, "_OCR_OK", None)
    assert app.ocr_available() and app.ocr_available() and len(calls) == 1  # lần sau không chạy lại Tesseract
    assert app.ocr_available(refresh=True) and len(calls) == 2


def test_customer_owner_and_machine_user(store):
    """Mỗi khách có nhân viên phụ trách; tên người dùng lưu theo máy; khách của người khác thì được nhận ra."""
    store.update_customer("shirai", {"owner": "Nhân viên A"})
    assert store.customer_owner("shirai") == "Nhân viên A"
    assert store.foreign_owner("shirai") == ""  # máy chưa đặt tên: không chặn, không hỏi
    store.set_user_name("Nhân viên B")
    assert store.user_name() == "Nhân viên B" and store.foreign_owner("shirai") == "Nhân viên A"
    store.set_user_name("nhân viên a")  # không phân biệt hoa thường
    assert store.foreign_owner("shirai") == ""
    assert store.foreign_owner("kodi") == ""  # khách chưa giao cho ai: ai cũng làm được

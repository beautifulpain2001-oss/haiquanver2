"""Học khách hàng mới từ chứng từ mẫu: XML hóa đơn/PXK (TT78), Invoice Excel, PO mẫu."""

import openpyxl
import pytest

import hongthien_desktop_app as app

VAT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HDon><DLHDon Id="data">
  <TTChung><KHMSHDon>1</KHMSHDon><KHHDon>C26TAA</KHHDon><SHDon>412</SHDon><NLap>2026-10-20</NLap></TTChung>
  <NDHDon>
    <NBan><Ten>CÔNG TY CỔ PHẦN GIẤY BAO BÌ HỒNG THIÊN</Ten><MST>2300723980</MST></NBan>
    <NMua><Ten>CÔNG TY TNHH ĐẠI PHÁT VIỆT NAM</Ten><MST>2301234567</MST>
      <DChi>Lô A1, KCN Quế Võ, Bắc Ninh</DChi><DCTDTu>ketoan@daiphat.vn</DCTDTu></NMua>
    <DSHHDVu>
      <HHDVu><TChat>1</TChat><STT>1</STT><MHHDVu>DP-76-1000</MHHDVu><THHDVu>Ống giấy phi 76 x 5 x 1000mm</THHDVu>
        <DVTinh>chiếc</DVTinh><SLuong>1000</SLuong><DGia>21000</DGia><ThTien>21000000</ThTien></HHDVu>
      <HHDVu><TChat>1</TChat><STT>2</STT><MHHDVu>DP-PAD-01</MHHDVu><THHDVu>Tấm lót giấy 1100 x 1100mm</THHDVu>
        <DVTinh>tấm</DVTinh><SLuong>200</SLuong><DGia>15500.5</DGia><ThTien>3100100</ThTien></HHDVu>
      <HHDVu><TChat>4</TChat><THHDVu>Ghi chú: hàng xuất khẩu tại chỗ</THHDVu></HHDVu>
    </DSHHDVu>
  </NDHDon>
</DLHDon></HDon>
"""

PXK_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HDon xmlns="http://example.invalid/tt78"><DLHDon>
  <TTChung><KHMSHDon>6</KHMSHDon><KHHDon>C26NDP</KHHDon><SHDon>77</SHDon></TTChung>
  <NDHDon>
    <NBan><Ten>HỒNG THIÊN</Ten><LDDNBo>LĐĐ20102026-01</LDDNBo><TNVChuyen>Nguyễn Văn Tài</TNVChuyen><PTVChuyen>99C-123.45</PTVChuyen></NBan>
    <NMua><Ten>CÔNG TY TNHH ĐẠI PHÁT VIỆT NAM</Ten><DChi>Kho 2, KCN Quế Võ, Bắc Ninh</DChi></NMua>
    <DSHHDVu><HHDVu><THHDVu>Ống giấy phi 76 x 5 x 1000mm</THHDVu><DVTinh>chiếc</DVTinh><SLuong>1000</SLuong></HHDVu></DSHHDVu>
  </NDHDon>
</DLHDon></HDon>
"""


@pytest.fixture(autouse=True)
def restore_profiles():
    before = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(before)


@pytest.fixture
def sample_docs(tmp_path):
    vat = tmp_path / "HD_0000412.xml"
    vat.write_text(VAT_XML, encoding="utf-8")
    pxk = tmp_path / "PXK_0000077.xml"
    pxk.write_text(PXK_XML, encoding="utf-8")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["", "INVOICE / PACKING LIST"])
    ws.append(["Người mua: CÔNG TY TNHH ĐẠI PHÁT VIỆT NAM"])
    ws.append([])
    ws.append(["STT", "Mã hàng", "Tên hàng", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "Số kiện", "N.W (kg)", "G.W (kg)", "Mã HS"])
    ws.append([1, "DP-76-1000", "Ống giấy phi 76 x 5 x 1000mm", "chiếc", 1000, 21000, 21000000, 200, 1250, 1290, "48229090"])
    ws.append([2, "DP-PAD-01", "Tấm lót giấy 1100 x 1100mm", "tấm", 200, 15500.5, 3100100, 4, 90, 94, "48239099"])
    ws.append(["", "", "Tổng cộng", "", 1200, "", 24100100, 204, 1340, 1384])
    inv = tmp_path / "Invoice_DaiPhat.xlsx"
    wb.save(inv)

    po = tmp_path / "PO_DaiPhat.txt"
    po.write_text(
        "ĐƠN ĐẶT HÀNG\nSố PO: DP2026-0457 Ngày 18/10/2026\n"
        "1 | DP-76-1000 | Ống giấy phi 76 x 5 x 1000mm | 1.500 | 21.000 | 31.500.000\n"
        "2 | Tấm lót giấy 1100 x 1100mm | tấm | 300 | 15.500,5 | 4.650.150\n"
        "Tổng cộng 36.150.150\n",
        encoding="utf-8",
    )
    return {"vat": str(vat), "pxk": str(pxk), "inv": str(inv), "po": str(po)}


@pytest.mark.parametrize("raw, expected", [
    ("1.000", 1000), ("31.500.000", 31500000), ("15.500,5", 15500.5), ("1,234.50", 1234.5),
    ("0.125", 0.125), ("1,5", 1.5), (42, 42), ("", 0),
])
def test_parse_vn_number(raw, expected):
    assert app.parse_vn_number(raw) == expected


def test_learn_from_vat_xml(sample_docs):
    res = app.learn_from_einvoice_xml(sample_docs["vat"])
    assert res["kind"] == "vat"
    assert res["profile"]["name"] == "CÔNG TY TNHH ĐẠI PHÁT VIỆT NAM"
    assert res["profile"]["mst"] == "2301234567"
    assert res["profile"]["emails"] == "ketoan@daiphat.vn"
    assert [x["code"] for x in res["items"]] == ["DP-76-1000", "DP-PAD-01"]  # bỏ dòng ghi chú TChat=4
    assert res["items"][1]["price"] == 15500.5


def test_learn_from_pxk_xml_with_namespace(sample_docs):
    res = app.learn_from_einvoice_xml(sample_docs["pxk"])
    assert res["kind"] == "pxk"
    assert res["profile"]["driver"] == "Nguyễn Văn Tài"
    assert res["profile"]["xe"] == "99C-123.45"
    assert res["profile"]["symbol"] == "6C26NDP"
    assert res["profile"]["addrKho"] == "Kho 2, KCN Quế Võ, Bắc Ninh"


def test_learn_from_invoice_excel_derives_norms(sample_docs):
    res = app.learn_from_invoice_excel(sample_docs["inv"])
    assert len(res["items"]) == 2  # dừng ở dòng Tổng cộng
    ong, pad = res["items"]
    assert ong["div"] == 5 and ong["kg"] == 1.25 and ong["hs"] == "48229090"
    assert pad["div"] == 50 and pad["kg"] == 0.45


def test_infer_po_pattern():
    pat = app.infer_po_pattern("03102026-01KDHT")
    import re
    assert re.search(pat, "PO 05112026-2KDHT ngày").group(0) == "05112026-2KDHT"
    assert not re.search(pat, "05112026-02KDXX")
    assert app.infer_po_pattern("") == ""


def test_customer_key_from_name():
    assert app.customer_key_from_name("CÔNG TY TNHH ĐẠI PHÁT VIỆT NAM") == "dai"
    assert app.customer_key_from_name("CÔNG TY TNHH SHIRAI VIỆT NAM", taken={"shirai"}) == "shirai2"


def test_learn_customer_from_documents_merges_all(sample_docs):
    draft = app.learn_customer_from_documents(list(sample_docs.values()))
    assert not draft["errors"]
    prof = draft["profile"]
    assert prof["mst"] == "2301234567" and prof["driver"] == "Nguyễn Văn Tài"
    assert prof["addr"] == "Lô A1, KCN Quế Võ, Bắc Ninh" and prof["addrKho"] == "Kho 2, KCN Quế Võ, Bắc Ninh"
    by_code = {x["code"]: x for x in draft["items"]}
    assert set(by_code) == {"DP-76-1000", "DP-PAD-01"}
    assert by_code["DP-76-1000"]["price"] == 21000 and by_code["DP-76-1000"]["kg"] == 1.25
    assert draft["sample_po"] == "DP2026-0457"


def test_generic_po_parser_reads_learned_items(sample_docs):
    draft = app.learn_customer_from_documents(list(sample_docs.values()))
    prof = app.build_custom_profile("dai", {"po_pattern": app.infer_po_pattern("DP2026-0457")})
    with open(sample_docs["po"], encoding="utf-8") as f:
        po_no, po_date, lines = app.parse_generic_po_text(f.read(), prof, draft["items"], tare_val=0.5)
    assert po_no == "DP2026-0457" and po_date == "18/10/2026"
    assert [(x["ma_sp"], x["qty"], x["price"]) for x in lines] == [("DP-76-1000", 1500, 21000), ("DP-PAD-01", 300, 15500.5)]
    ong = lines[0]
    assert ong["kien"] == 300 and ong["net"] == 1875.0 and ong["gross"] == 1875.5


def test_save_learned_customer_persists_and_exports(store, data_dir, sample_docs, full_workbook):
    draft = app.learn_customer_from_documents(list(sample_docs.values()))
    key = store.save_learned_customer("dai", dict(draft["profile"], label="Đại Phát"), draft["items"])
    assert key == "dai" and app.PROFILES["dai"]["custom"]

    app.PROFILES.pop("dai")
    reloaded = app.DedicatedDataStore(base_dir=str(data_dir))
    assert app.PROFILES["dai"]["mst"] == "2301234567"
    assert len(reloaded.items_for_customer("dai")) == 2
    assert reloaded.get_item_norm("Ống giấy phi 76 x 5 x 1000mm")["div"] == 5

    _, _, lines = app.parse_generic_po_text(open(sample_docs["po"], encoding="utf-8").read(), app.PROFILES["dai"], reloaded.items_for_customer("dai"), reloaded)
    rec = dict(store.records[0], customer="dai", items=lines, docDate="2026-10-20", poNumber="DP2026-0457")
    wb = full_workbook(rec)
    vat = next(wb[n] for n in wb.sheetnames if n.startswith("VAT_BKAV"))
    values = {c.value for row in vat.iter_rows() for c in row}
    assert "CÔNG TY TNHH ĐẠI PHÁT VIỆT NAM" in values and "2301234567" in values
    assert app.get_vat_and_pxk_ids(rec) == ("dai20.10", "dai20.10")


def test_save_learned_customer_rejects_builtin_key(store):
    with pytest.raises(ValueError):
        store.save_learned_customer("kodi", {"name": "X"}, [])
    assert app.PROFILES["kodi"]["name"] == "CÔNG TY TNHH KODI NEW MATERIAL VIỆT NAM"


def test_saving_again_updates_items_instead_of_duplicating(store):
    store.save_learned_customer("abc", {"name": "ABC"}, [{"code": "A1", "name": "Hàng A", "price": 100}])
    store.save_learned_customer("abc", {"name": "ABC"}, [{"code": "A1", "name": "Hàng A", "price": 120, "kg": 0.3}])
    items = store.items_for_customer("abc")
    assert len(items) == 1 and items[0]["price"] == 120 and items[0]["kg"] == 0.3


@pytest.mark.gui
def test_wizard_adds_customer_and_scans_po(store, sample_docs, monkeypatch):
    if app.tk is None:
        pytest.skip("Không có Tkinter")
    try:
        root = app.tk.Tk()
    except app.tk.TclError as e:
        pytest.skip(f"Không có màn hình: {e}")
    root.withdraw()
    shown = []
    for fn in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(app.messagebox, fn, lambda title, msg, *a, _fn=fn, **k: shown.append((_fn, msg)))
    try:
        ui = app.HongThienCustomsDesktopApp(root, store)
        wz = ui.open_learn_customer_wizard(paths=[sample_docs["vat"], sample_docs["pxk"], sample_docs["inv"]])
        # Cửa sổ học khách mới phải gắn với cửa sổ chính, không bị cửa sổ chính che mất
        assert str(wz["dlg"].transient()) == str(root)
        assert wz["vars"]["mst"].get() == "2301234567"
        assert len(wz["tree"].get_children()) == 2
        wz["vars"]["key"].set("daiphat")
        wz["vars"]["label"].set("Đại Phát")
        wz["vars"]["sample_po"].set("DP2026-0457")
        assert wz["save"]() == "daiphat"
        assert ui.cur_customer.get() == "daiphat" and "daiphat" in ui.cust_radios
        assert ui.cur_items == []

        with open(sample_docs["po"], encoding="utf-8") as f:
            assert ui.scan_custom_po_text(f.read())
        assert ui.cur_po.get() == "DP2026-0457"
        assert len(ui.tree_items.get_children()) == 2

        ui.export_step1_excel("ALL")
        assert shown[-1][0] == "showinfo"
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# Khách có Invoice nhiều sheet + PO scan không cùng cách ghi tên hàng (kiểu ABLE / ARIZON)
# ---------------------------------------------------------------------------
@pytest.fixture
def multi_sheet_invoice(tmp_path):
    wb = openpyxl.Workbook()
    old = wb.active
    old.title = "Thang11"
    old.append(["INVOICE - PACKING LIST", "", "", "", "Ngày: 21/11/2025"])
    old.append(["Người nhận hàng:"])
    old.append(["CÔNG TY TNHH BAO BÌ MẪU"])
    old.append(["Khu A1, KCN Nam Đình Vũ, Hải Phòng"])
    old.append(["STT", "Mã liệu", "Tên Hàng", "ĐVT", "Số Lượng", "Cân Nặng (kg)", "Trọng lượng cả bì (kg)",
                "Trọng lượng tịnh (kg)", "Số kiện", "Đơn Giá VND", "Thành Tiền VND"])
    old.append([1, "", "Ống giấy phi 38 x 5 x 467mm x250g in", "Chiếc", 1380, 0.25, 347, 345, 18.4, 4375, 6037500])
    new = wb.create_sheet("Thang8")
    new.append(["INVOICE - PACKING LIST", "", "", "", "Ngày: 27/08/2026"])
    new.append(["Mã số thuế: 0202226426"])
    new.append(["STT", "Mã hàng", "", "Tên Hàng", "PO", "ĐVT", "Số Lượng", "Trọng lượng(kg)", "Trọng lượng cả bì(kg)",
                "Trọng lượng tịnh(kg)", "Số kiện", "Đơn Giá VND", "Thành Tiền VND"])
    # mã hàng nằm ở cột bên phải tiêu đề 'Mã hàng' (ô tiêu đề bị gộp)
    new.append([1, "", "3609100670001", "Ống giấy phi 38 x 5 x 467mm x250g in", "20260611-00213", "Chiếc", 2500, 0.25, 626, 625, 29.76, 4725, 11812500])
    new.append([2, "", "3609100670002", "Ống giấy phi 38 x 5 x 467mm x280g in", "20260611-00213", "Chiếc", 2500, 0.28, 701, 700, 30, 5239, 13097500])
    new.append(["", "", "", "Tổng", "", "", 5000])
    norms = wb.create_sheet("CN")
    norms.append(["Mã code", "Quy Cách", "Số Lượng ống / 1 túi"])
    norms.append(["3609100670002", "38 x 5 x 467", 90])
    path = tmp_path / "IV_PK.xlsx"
    wb.save(path)
    return str(path)


def test_invoice_excel_reads_all_sheets_newest_first(multi_sheet_invoice):
    res = app.learn_from_invoice_excel(multi_sheet_invoice)
    g250 = res["items"][0]
    assert res["items"][0]["price"] == 4725  # sheet tháng 8/2026 đứng trước sheet 11/2025
    assert g250["code"] == "3609100670001"
    assert g250["kg"] == 0.25
    assert g250["div"] == 75  # 29.76 kiện là số lẻ -> lấy SL/kiện nguyên 1380/18.4 = 75
    g280 = next(x for x in res["items"] if x["code"] == "3609100670002")
    assert g280["div"] == 90  # bảng định mức 'Số lượng ống / 1 túi' thắng
    assert res["meta"]["sample_po"] == "20260611-00213"
    assert res["meta"]["tare"] == 1
    assert res["profile"]["name"] == "CÔNG TY TNHH BAO BÌ MẪU"
    assert res["profile"]["addr"].startswith("Khu A1")
    assert res["profile"]["mst"] == "0202226426"


ITEMS_38 = [
    {"code": "", "name": "Ống giấy phi 38 x 5 x 467mm x280g in", "unit": "Chiếc", "price": 5239, "div": 84, "kg": 0.28},
    {"code": "", "name": "Ống giấy phi 38 x 5 x467 mm x 250g in", "unit": "Chiếc", "price": 4725, "div": 84, "kg": 0.25},
    {"code": "3609400670001", "name": "Ống giấy phi 25.4 (1inch) x 6 x 67mm", "unit": "Chiếc", "price": 2314, "div": 400, "kg": 0.032},
    {"code": "3609100670001", "name": "Ống giấy phi 76.2( 3inch) x 5 x 67 mm", "unit": "chiếc", "price": 3098, "div": 196, "kg": 0.067},
]


def test_generic_po_matches_by_spec_and_price_when_names_differ():
    # Hợp đồng tiếng Trung đọc qua OCR: tên hàng là chữ Hán (đọc ra rác), chỉ còn quy cách, định lượng, số
    text = (
        "合同编号: 20260821-00231\n"
        "| 1 [am 2508. 38*5*467 2500 725.00 d 11,812,500.00 4\n"   # 250g đọc nhầm '2508', 4,725 mất chữ '4'
        "EAL CURIA 280g 38°5*467 2500 5,239.00 4 13,097,500.00 #\n"
    )
    prof = {"po_pattern": app.infer_po_pattern("20260611-00213")}
    po, _, lines = app.parse_generic_po_text(text, prof, ITEMS_38, tare_val=1)
    assert po == "20260821-00231"
    assert [(x["ten_sp"][-8:], x["qty"], x["price"], x["amount"], x["net"], x["gross"]) for x in lines] == [
        (" 250g in", 2500, 4725, 11_812_500, 625.0, 626.0),
        ("x280g in", 2500, 5239, 13_097_500, 700.0, 701.0),
    ]


def test_generic_po_tolerates_ocr_spacing_misread_code_and_dates():
    text = (
        "Source N0./Mã đơn xin mua: VN-3101-202609090002\n"
        "PO N0. /Đơn mua hàng: VN-3501-2026091 10005\n"
        "PO Date/Ngày xuống đơn: 2026-09-11\n"
        "3609100870001 U:#j6mn 3, 098. 000000 12, 000. 0000 i ỐNG GIẤY PHI 76.2 (3 inch) x 5 x 67 mm 2026-09-18\n"
        "3609400670001 U: 67mm, (4/220) | 2,314. 000000 16, 000. 0000 m Ống giấy phi 25.4 (linch) x 6 x 67mm 2026-09-18\n"
    )
    prof = {"po_pattern": app.infer_po_pattern("VN-3501-202609110005")}
    po, po_date, lines = app.parse_generic_po_text(text, prof, ITEMS_38, tare_val=1)
    assert po == "VN-3501-202609110005"  # số đứng sau chữ 'PO', không lấy mã đơn xin mua
    assert po_date == "11/09/2026"
    assert [(x["ma_sp"], x["qty"], x["price"], x["amount"], x["kien"]) for x in lines] == [
        ("3609100670001", 12000, 3098, 37_176_000, 62),
        ("3609400670001", 16000, 2314, 37_024_000, 40),
    ]


def test_learned_customer_invoice_has_line_po_unit_and_code(store, multi_sheet_invoice):
    draft = app.learn_customer_from_documents([multi_sheet_invoice])
    fields = {**draft["profile"], "po_pattern": app.infer_po_pattern(draft["sample_po"]), "tare": draft["tare"]}
    key = store.save_learned_customer("baobimau", fields, draft["items"])
    prof = app.PROFILES[key]
    assert prof["linePo"] is True and prof["tare"] == 1
    _, _, lines = app.parse_generic_po_text(
        "PO 20260901-00001\n3609100670002 38*5*467 280g 3000 5,239 15,717,000\n",
        prof, store.items_for_customer(key), data_store=store, tare_val=prof["tare"])
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = app.build_invoice_pkl_sheet(wb, {"customer": key, "poNumber": "20260901-00001", "items": lines, "docDate": "2026-09-21"})
    assert ws["B13"].value.startswith("3609100670002\n")
    assert (ws["C13"].value, ws["D13"].value, ws["E13"].value, ws["G13"].value, ws["J13"].value) == (
        "20260901-00001", "Chiếc", 3000, 841.0, 5239)

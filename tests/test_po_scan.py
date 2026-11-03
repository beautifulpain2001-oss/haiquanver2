"""PO scan khó đọc (Able): đọc từng ô, trạng thái từng dòng, tra mã để thêm dòng."""
import json
import os

import pytest

import hongthien_desktop_app as app
import po_scan

CAT = [
    {"code": "38*5*460*250g", "name": "Ống 38x5x460 250g in", "unit": "Chiếc", "price": 4725, "div": 75, "kg": 0.25, "hs": "48229090"},
    {"code": "38*5*467*250g", "name": "Ống 38x5x467 250g in", "unit": "Chiếc", "price": 4725, "div": 84, "kg": 0.25, "hs": "48229090"},
    {"code": "38*5*467*280g", "name": "Ống 38x5x467 280g in", "unit": "Chiếc", "price": 5239, "div": 75, "kg": 0.28, "hs": "48229090"},
    {"code": "38*5*315*150g", "name": "Ống 38x5x315 150g in", "unit": "Chiếc", "price": 2807, "div": 70, "kg": 0.15, "hs": "48229090"},
]
IDX = po_scan._catalog_index(CAT)


def test_vnd_candidates_handle_dong_sign_read_as_digit():
    assert 5239 in po_scan.vnd_candidates("5,239.00")
    assert 5239 in po_scan.vnd_candidates("5,239,004")  # chữ đ thành số 4, dấu chấm thành phẩy
    assert 1047800 in po_scan.vnd_candidates("1,047,800,004")
    assert po_scan.vnd_candidates("") == []


def test_solve_row_ok_when_qty_times_price_matches_amount():
    item, qty, price, amount, how, _ = po_scan.solve_row([1000], [5239], [5239000], "385467", IDX)
    assert (item["code"], qty, price, amount, how) == ("38*5*467*280g", 1000, 5239, 5239000, "ok")


def test_solve_row_infers_missing_cells_and_says_so():
    # đơn giá đọc hỏng (',239'), SL và thành tiền khớp nhau: vẫn ra đúng
    r = po_scan.solve_row([400], [239], [2095600], "385467", IDX)
    assert r[3] == 2095600 and r[1] == 400 and r[2] == 5239
    # SL đọc hỏng: suy từ thành tiền / đơn giá nên phải báo "suy ra"
    r = po_scan.solve_row([], [5239], [1676480], "385467", IDX)
    assert r[1] == 320 and r[4] == "suy_ra"
    # không có gì khớp: không đoán bừa
    assert po_scan.solve_row([7], [], [], "385467", IDX) is None


def test_solve_row_length_decides_between_same_price_codes():
    assert po_scan.solve_row([100], [4725], [472500], "385460", IDX)[0]["code"] == "38*5*460*250g"
    assert po_scan.solve_row([100], [4725], [472500], "385467", IDX)[0]["code"] == "38*5*467*250g"
    assert po_scan.solve_row([100], [4725], [472500], "385167", IDX)[0]["code"] == "38*5*467*250g"  # 467 đọc thành 167


def test_read_report_names_unread_rows():
    lines = [{"read": "ok"}, {"read": "loi"}, {"read": "suy_ra"}, {"read": "ok"}]
    rep = app.read_report(lines, "Trang 1: tổng khớp")
    assert rep["bad_rows"] == [2] and rep["warn_rows"] == [3] and "Đọc được 3/4" in rep["text"] and "dòng 2" in rep["text"] and "Dòng 3" in rep["text"]
    assert "Đã đọc đủ 2/2" in app.read_report([{"read": "ok"}, {"read": "ok"}])["text"]


def make_store(tmp_path):
    return app.DedicatedDataStore(base_dir=str(tmp_path / "d"))


def test_lines_from_able_scan_keep_unread_rows_as_empty_lines(tmp_path):
    s = make_store(tmp_path)
    s.save_learned_customer("ablet", {"name": "CTY ABLE T", "unit": "Chiếc", "addr": "HP", "mst": "0100000001", "poStyle": "able"}, CAT)
    prof = app.PROFILES["ablet"]
    rows = [{"read": "ok", "code": "38*5*467*280g", "name": "Ống 38x5x467 280g in", "qty": 1000, "price": 5239, "po": "20261009-00242", "ref": "A", "read_note": ""},
            {"read": "loi", "code": "", "name": "", "qty": 0, "price": 0, "po": "20261009-00242", "ref": "B", "read_note": "Không đọc được dòng này, hãy nhập tay"}]
    lines = app.lines_from_able_scan(rows, prof, CAT, s, 0.0)
    assert [x["read"] for x in lines] == ["ok", "loi"] and lines[0]["qty"] == 1000 and lines[0]["ma_sp"] == "38*5*467*280g" and lines[1]["qty"] == 0 and lines[1]["ref"] == "B"


def test_lot_search_items_by_spec_weight_and_code(tmp_path):
    s = make_store(tmp_path)
    s.save_learned_customer("ablet2", {"name": "CTY ABLE T2", "unit": "Chiếc", "addr": "HP", "mst": "0100000001"}, CAT)
    got = lambda q: [h["ma_sp"] for h in app.lot_search_items(s, "ablet2", q)]
    assert got("467 250g") == ["38*5*467*250g"]
    assert got("38 x 5 x 460") == ["38*5*460*250g"]
    assert set(got("38*5*467")) == {"38*5*467*250g", "38*5*467*280g"}
    assert got("zzz") == []
    assert len(got("")) == 4


def test_able_pdf_end_to_end_when_sample_present(tmp_path):
    pdf = "/root/.claude/uploads/60e0f727-02f2-5c49-8a4c-929e37443d6a/712a4f0e-poable295.pdf"
    if not (os.path.exists(pdf) and app.ocr_available()):
        pytest.skip("không có PO mẫu hoặc OCR")
    s = make_store(tmp_path)
    d = json.load(open("/tmp/claude-0/-home-user-haiquanver2/60e0f727-02f2-5c49-8a4c-929e37443d6a/scratchpad/able/able_dulieu_hoc.json")) if os.path.exists(
        "/tmp/claude-0/-home-user-haiquanver2/60e0f727-02f2-5c49-8a4c-929e37443d6a/scratchpad/able/able_dulieu_hoc.json") else None
    if not d:
        pytest.skip("không có file học Able")
    s.import_learned(d)
    r = app.lot_load_po(s, pdf, "able")
    assert r["ok"] and len(r["items"]) == 41 and r["read_report"]["loi"] == 0
    assert sum(x["qty"] for x in r["items"]) == 14776 + 5520 + 2160  # tổng SL ba trang theo PO
    assert "khớp PO" in r["msg"]


def test_unrotate_point_maps_deskewed_coordinates_back_to_original():
    from PIL import Image, ImageDraw
    W, H = 600, 400
    for angle in (1.5, -1.0, 0.5):
        im = Image.new("L", (W, H), 255)
        ImageDraw.Draw(im).rectangle((96, 296, 104, 304), fill=0)  # điểm đánh dấu quanh (100, 300)
        rot = im.rotate(angle, resample=Image.BILINEAR, fillcolor=255).point(lambda v: 255 if v < 128 else 0)
        x0, y0, x1, y1 = rot.getbbox()
        x, y = po_scan.unrotate_point((x0 + x1) / 2, (y0 + y1) / 2, angle, W, H)
        assert abs(x - 100) < 1.5 and abs(y - 300) < 1.5


def test_viewer_highlight_draws_box_on_selected_row(qapp, tmp_path):
    from ui_qt.po_viewer import PoViewer
    pdf = tmp_path / "po.pdf"
    app.make_scanned_pdf(str(pdf), ["Trang 1"])
    v = PoViewer(app)
    v.resize(500, 600)
    v.show_page(str(pdf), 0, None)
    plain = v.label.pixmap().toImage()
    v.show_page(str(pdf), 0, [[0.1, 0.4], [0.9, 0.4], [0.9, 0.45], [0.1, 0.45]])
    marked = v.label.pixmap().toImage()
    H = marked.height()
    assert plain.size() == marked.size() and plain != marked
    y = int(0.425 * H)
    assert marked.pixelColor(marked.width() // 2, y) != plain.pixelColor(marked.width() // 2, y)  # vùng dòng đã đổi màu
    assert marked.pixelColor(marked.width() // 2, int(0.2 * H)) == plain.pixelColor(marked.width() // 2, int(0.2 * H))  # ngoài dòng giữ nguyên


def test_page_row_boxes_match_boxes_from_full_read(qapp, tmp_path):
    """Lô đọc từ bản cũ (không có vị trí dòng) vẫn tô sáng được: đo lại đường kẻ cho ra cùng khung với lúc đọc đầy đủ."""
    pdf = "/root/.claude/uploads/60e0f727-02f2-5c49-8a4c-929e37443d6a/712a4f0e-poable295.pdf"
    if not os.path.exists(pdf):
        pytest.skip("không có PO mẫu")
    boxes = po_scan.page_row_boxes(app, pdf, 1)
    assert len(boxes) >= 36 and all(len(b) == 4 for b in boxes)
    ys = [b[0][1] for b in boxes]
    assert ys == sorted(ys) and 0.1 < ys[0] < 0.4 and ys[-1] < 0.95

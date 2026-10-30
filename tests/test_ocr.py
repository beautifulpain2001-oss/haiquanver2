"""OCR PDF scan (PO dạng ảnh) bằng Tesseract offline.

Tự bỏ qua khi máy không có Tesseract + pytesseract + pypdfium2 (CI Linux cài sẵn tesseract-ocr-vie).
"""

import pytest

import hongthien_desktop_app as app

pytestmark = pytest.mark.skipif(not app.ocr_available(), reason="chưa cài Tesseract OCR / pytesseract / pypdfium2")


def test_scanned_kodi_po(tmp_path, store):
    pdf = tmp_path / "kodi_scan.pdf"
    app.make_scanned_pdf(str(pdf), [app.OCR_SAMPLE_KODI])
    txt = app.extract_text_from_pdf_or_image_offline(str(pdf))
    po, po_date, lines = app.parse_kodi_po_text(txt, store.kodi_items, store)
    assert (po, po_date) == ("03102026-01KDHT", "03/10/2026")
    assert [(x["ma_sp"], x["qty"], x["amount"]) for x in lines] == [
        ("TM91120-001-00001", 1000, 31_500_000),
        ("TM91120-001-00072", 500, 44_850_000),
    ]


def test_scanned_tesa_po_reads_even_pages_with_header_strip(tmp_path, store):
    pdf = tmp_path / "tesa_scan.pdf"
    other = app.OCR_SAMPLE_TESA.replace("8600226354", "8600226355")
    # Trang 1, 3: điều khoản (bỏ qua); trang 2, 4: PO
    app.make_scanned_pdf(str(pdf), ["GENERAL TERMS AND CONDITIONS", app.OCR_SAMPLE_TESA, "GENERAL TERMS", other])
    txt = app.extract_text_from_pdf_or_image_offline(str(pdf), is_tesa=True)
    assert txt.count("@@HDR@@") == 2  # chỉ OCR 2 trang chẵn, mỗi trang có dải tiêu đề phóng to
    first_po, lines = app.parse_tesa_po_text(txt, store.tesa_items, store)
    assert first_po == "8600226354"
    assert [(x["po"], x["ma_sp"], x["qty"]) for x in lines] == [
        ("8600226354", "39778-90019-00", 136000),
        ("8600226355", "39778-90019-00", 136000),
    ]


def test_scanned_image_file(tmp_path):
    pdf = tmp_path / "scan.pdf"
    app.make_scanned_pdf(str(pdf), [app.OCR_SAMPLE_KODI])
    png = tmp_path / "scan.png"
    app.pdfium.PdfDocument(str(pdf))[0].render(scale=1).to_pil().save(png)
    assert "03102026" in app.extract_text_from_pdf_or_image_offline(str(png))


def test_ocr_self_test_entry_point(store, monkeypatch):
    # Lệnh mà bản .exe chạy khi build (--ocr-self-test)
    monkeypatch.setattr(app, "DedicatedDataStore", lambda: store)
    app.run_ocr_self_test()

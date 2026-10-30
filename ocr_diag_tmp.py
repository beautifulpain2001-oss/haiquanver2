import os, sys, pytesseract
from PIL import ImageFont
import hongthien_desktop_app as a
for n in ("arial.ttf", "DejaVuSans.ttf"):
    try:
        f = ImageFont.truetype(n, 26); print("font", n, "->", f.path)
    except OSError as e:
        print("font", n, "missing", e)
print("tess", pytesseract.get_tesseract_version(), pytesseract.pytesseract.tesseract_cmd, os.environ.get("TESSDATA_PREFIX"))
print("langs", pytesseract.get_languages(config=""))
a.make_scanned_pdf("d.pdf", [a.OCR_SAMPLE_KODI])
img = a.pdfium.PdfDocument("d.pdf")[0].render(scale=2.5).to_pil()
img.save("d.png")
for lang in ("vie", "vie+eng", "eng+vie"):
    print("==", lang); print(pytesseract.image_to_string(img, lang=lang))

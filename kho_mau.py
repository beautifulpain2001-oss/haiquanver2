"""Mẫu có sẵn cho KHO MẪU CHUNG (thư mục MAU_CHUNG_TU/_KHO): file Word/Excel có ô {{...}} để mọi khách dùng lại.

Tên file theo quy ước <LOẠI>_<Khách nguồn>_<số thứ tự>, ví dụ PLX_Arizon_01.xlsx, PLX_Sunlu_01.docx.
Kho chỉ được gieo mẫu có sẵn MỘT LẦN, lúc thư mục kho chưa tồn tại (xóa mẫu nào thì không bị tự thêm lại).
"""

import io

import mau_word

LOAI = {"PLX": "Phụ lục X", "BBGH": "Biên bản giao nhận", "PO": "Đơn đặt hàng", "BDC": "Bảng đối chiếu hàng hóa", "DNTT": "Đề nghị thanh toán",
        "DCCN": "Đối chiếu công nợ", "KHAC": "Khác"}


def plx_sunlu_docx():
    """Phụ lục X Word của Sunlu: mẫu Word khách đưa, chỗ thay đổi theo lô đã chuyển thành ô {{...}}."""
    texts = {
        6: "Số lượng: {{tong_sl}} PCS , {{ten_hang}} , trị giá DAP {{tong_tri_gia}}  VND",
        7: "Tờ khai xuất khẩu tại chỗ số : {{so_tk}}   ngày {{ngay}},  Hóa Đơn Số: {{so_hd}} ngày {{ngay}}",
        8: "{{ben_ban_ten}} xác nhận rằng nguyên liệu/hàng hóa: {{ten_hang}}",
        9: ", HS CODE: {{hs}}. khai tại văn bản này được sản xuất tại nhà máy của Công ty chúng tôi tại địa chỉ：{{ben_ban_dia_chi}}, "
           "có xuất xứ Việt Nam và đáp ứng tiêu chí CTH  theo quy định tại  Thông tư số 44/2023/TT-BCT ",
        12: "         Bắc Ninh, ngày {{dd}} tháng {{mm}}  năm {{yyyy}}",
    }
    return mau_word.fill_paragraphs(mau_word.template_bytes(mau_word.PLX_SUNLU_B64), texts)


def plx_arizon_xlsx():
    """Phụ lục X Excel của Arizon: STT | Mã hàng | Tên hàng | Số lượng; tổng SL, trị giá (FOB), số hóa đơn và ngày."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "PLX"
    for col, w in zip("ABCD", (8, 24, 58, 16)):
        ws.column_dimensions[col].width = w

    def put(addr, rng, val, size=13, bold=False, italic=False, h="left"):
        if rng:
            ws.merge_cells(rng)
        c = ws[addr]
        c.value = val
        c.font = Font(name="Times New Roman", size=size, bold=bold, italic=italic)
        c.alignment = Alignment(horizontal=h, vertical="center", wrap_text=True)
        return c

    put("A1", "A1:D1", "PHỤ LỤC X", 14, True, h="center")
    put("A2", "A2:D2", "BẢN KHAI BÁO XUẤT XỨ CỦA NHÀ SẢN XUẤT/NHÀ CUNG CẤP NGUYÊN LIỆU TRONG NƯỚC", 12, True, h="center")
    put("A3", "A3:D3", "(ban hành kèm theo Thông tư số 05/2018/TT-BCT ngày 03 tháng 4 năm 2018 quy định về xuất xứ hàng hóa)", 11, italic=True, h="center")
    put("A4", "A4:D4", "Tên nhà sản xuất: {{ben_ban_ten}}")
    put("A5", "A5:D5", "Mã số Doanh nghiệp: {{ben_ban_mst}}")
    put("A6", "A6:B6", "Số lượng:")
    put("C6", None, "{{tong_sl}}", 13, True)
    put("D6", None, "(Chiếc)", 12)
    put("A7", "A7:B7", "Trị giá (FOB):")
    put("C7", None, "{{tong_tri_gia}}", 13, True)
    put("D7", None, "VNĐ", 12)
    put("A8", "A8:D8", "Hóa đơn giá trị gia tăng: {{so_hd}} Ngày {{ngay}}")
    put("A9", "A9:D9", "{{ben_ban_ten}} xác nhận rằng:")
    thin = Side(style="thin", color="000000")
    box = Border(top=thin, bottom=thin, left=thin, right=thin)
    for col, h in zip("ABCD", ("STT", "Mã hàng", "Tên hàng", "Số lượng")):
        put(f"{col}10", None, h, 13, h="center").border = box
    for col, v, al in (("A", "{{stt}}", "left"), ("B", "{{ma}}", "center"), ("C", "{{ten}}", "left"), ("D", "{{sl}}", "right")):
        c = put(f"{col}11", None, v, 12, h=al)
        c.border = box
        if col == "D":
            c.number_format = "#,##0"
    put("A13", "A13:D13", "Khai tại văn bản này được sản xuất tại Công ty chúng tôi có địa chỉ tại {{ben_ban_dia_chi}}, có xuất xứ việt nam và đáp ứng tiêu chí xuất xứ “CTH” "
        "theo quy định tại phụ lục I- quy tắc cụ thể mặt hàng ban hành kèm theo thông tư 03/2023/TT-BCT ngày 14 tháng 02 năm 2023")
    put("A14", "A14:D14", "Công ty cam kết thông tin khai báo trên là đúng và chịu trách nhiệm trước pháp luật về thông tin đã khai.")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def seeds():
    """{tên file trong kho: nội dung} các mẫu có sẵn."""
    return {"PLX_Sunlu_01.docx": plx_sunlu_docx(), "PLX_Arizon_01.xlsx": plx_arizon_xlsx()}

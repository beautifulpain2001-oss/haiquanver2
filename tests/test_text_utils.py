import pytest

import hongthien_desktop_app as app


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Thùng Carton Box PNN-4585GHNA(W927xD129xH387)", "cartonboxpnn4585ghnaw927xd129xh387"),
        ("Carton Box PNN-4585GHNA(W927xD129xH387)", "cartonboxpnn4585ghnaw927xd129xh387"),
        ("Tấm lót Pad PNN-4585GH", "padpnn4585gh"),
        ("Pad PNN-4585GH", "padpnn4585gh"),
        ("Carton Box ABC không in", "cartonboxabc"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_str_normalises_names_for_matching(raw, expected):
    assert app.clean_str(raw) == expected


def test_strip_accents_upper():
    assert app.strip_accents_upper("Công ty TNHH Tesa Site Hải Phòng") == "CONG TY TNHH TESA SITE HAI PHONG"
    assert app.strip_accents_upper("Đông Hải") == "DONG HAI"
    assert app.strip_accents_upper("") == ""


@pytest.mark.parametrize(
    "num, words",
    [
        (0, "Không đồng"),
        (None, "Không đồng"),
        (-5, "Không đồng"),
        (1, "Một đồng"),
        (10, "Mười đồng"),
        (15, "Mười lăm đồng"),
        (21, "Hai mươi mốt đồng"),
        (105, "Một trăm lẻ năm đồng"),
        (1005, "Một nghìn không trăm lẻ năm đồng"),
        (1_000_000, "Một triệu đồng"),
        (76_350_000, "Bảy mươi sáu triệu ba trăm năm mươi nghìn đồng"),
        (268_468_500, "Hai trăm sáu mươi tám triệu bốn trăm sáu mươi tám nghìn năm trăm đồng"),
        (1_000_000_000, "Một tỷ đồng"),
    ],
)
def test_num_to_vn_words(num, words):
    assert app.num_to_vn_words(num) == words


@pytest.mark.xfail(strict=True, reason="Lỗi đã biết: từ 1.000 tỷ trở lên đơn vị bị quay vòng (units[g % 4]) nên mất chữ 'nghìn tỷ'")
def test_num_to_vn_words_trillions():
    assert app.num_to_vn_words(1_000_000_000_000) == "Một nghìn tỷ đồng"

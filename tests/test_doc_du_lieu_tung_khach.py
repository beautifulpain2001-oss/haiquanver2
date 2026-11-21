"""Từ 21/11/2026: mở app là tự chuyển sang mỗi khách một file; mọi khách có trong app đều có thư mục + DU_LIEU_<MÃ>.json;
định mức theo tên riêng từng khách; không tra ERP chung; Deli Bắc Ninh / Hải Phòng có 2 bản dữ liệu giống nhau."""
import json
import os

import pytest

import hongthien_desktop_app as app


@pytest.fixture(autouse=True)
def keep_profiles():
    saved = dict(app.PROFILES)
    yield
    app.PROFILES.clear()
    app.PROFILES.update(saved)


def make_store(data_dir, tmp_path, name):
    s = app.DedicatedDataStore(base_dir=str(data_dir))
    s.config_file = str(tmp_path / f"config_{name}.json")
    return s


def add_deli(store):
    store.save_learned_customer("deli_bn", {"name": "CÔNG TY TNHH DELI VIỆT NAM", "label": "Deli Bắc Ninh", "mst": "2301075570", "unit": "Chiếc"},
                                [{"name": "340025128 Ống giấy 1250*76*3mm", "code": "340025128", "div": 20, "kg": 1.2}])
    store.save_learned_customer("deli_hd", {"name": "CÔNG TY TNHH CÔNG NGHỆ VĂN PHÒNG DELI VIỆT NAM", "label": "Deli Hải Phòng",
                                            "mst": "0801409926", "unit": "Chiếc"},
                                [{"name": "340025472 Ống giấy 1250*38*3mm", "code": "340025472", "div": 30, "kg": 0.8}])


def test_mo_app_tu_chuyen_va_moi_khach_co_file(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.save_learned_customer("minhanh", {"name": "CÔNG TY MINH ANH", "label": "Minh Anh", "mst": "0100000001", "addr": "HN"},
                            [{"name": "Ống A", "code": "A1", "div": 10, "kg": 1}])
    assert not a.theo_khach()
    res = a.tu_chuyen_theo_khach()
    assert a.theo_khach() and res["chuyen"] and os.path.isdir(res["chuyen"]["sao_luu"])
    for key in ("shirai", "kodi", "tesa", "minhanh"):  # kể cả khách có sẵn chưa có dữ liệu riêng
        assert os.path.isfile(a._khach_path(key)), key
    head = json.load(open(a._khach_path("minhanh"), encoding="utf-8"))
    assert head["thong_tin"]["mst"] == "0100000001" and head["ten"] == "Minh Anh"
    assert os.path.isfile(os.path.splitext(a.catalog_file)[0] + ".DA_CHUYEN.json")  # file cũ giữ lại, không xóa
    b = make_store(data_dir, tmp_path, "b")  # máy/lần mở sau: đọc khách từ file của từng khách
    assert b.tu_chuyen_theo_khach()["chuyen"] is None
    assert "minhanh" in b.custom_profiles and b.custom_items["minhanh"][0]["code"] == "A1"


def test_hoan_tac_thi_khong_tu_chuyen_lai(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.tu_chuyen_theo_khach()
    a.chuyen_doi_hoan_tac()
    b = make_store(data_dir, tmp_path, "b")
    res = b.tu_chuyen_theo_khach()
    assert not b.theo_khach() and res["chuyen"] is None and "hoàn tác" in res["loi"]
    b.chuyen_doi_thuc_hien()  # bấm chuyển bằng tay vẫn được, và bỏ dấu đã hoàn tác
    assert b.theo_khach() and not os.path.exists(b._hoan_tac_marker())


def test_khach_moi_nap_sau_khi_chuyen_cung_co_file(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    a.tu_chuyen_theo_khach()
    a.save_learned_customer("quangich", {"name": "CÔNG TY QUANG ÍCH", "label": "Quang Ích"}, [{"name": "Ống Q", "code": "Q1"}])
    assert os.path.isfile(a._khach_path("quangich"))
    assert json.load(open(a._khach_path("quangich"), encoding="utf-8"))["danh_muc"]["custom_items"]["quangich"][0]["code"] == "Q1"


def test_dinh_muc_theo_ten_rieng_tung_khach(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    name = "Ống giấy phi 76 x 9 x 1000mm"  # cùng tên với một mã Kodi
    a.save_learned_customer("minhanh", {"name": "CÔNG TY MINH ANH", "label": "Minh Anh"}, [{"name": name, "code": "MA1", "div": 7, "kg": 1.5}])
    a.tu_chuyen_theo_khach()
    a.remember_item_norm(name, 3, 2.0, "48229090", customer="minhanh")
    assert a.get_item_norm(name, "minhanh")["div"] == 3
    assert (a.get_item_norm(name, "kodi") or {}).get("div") != 3  # khách khác cùng tên hàng không bị đổi
    assert next(it for it in a.kodi_items if it["name"] == name)["div"] != 3
    b = make_store(data_dir, tmp_path, "b")
    assert b.get_item_norm(name, "minhanh")["div"] == 3
    mine = json.load(open(b._khach_path("minhanh"), encoding="utf-8"))["danh_muc"]
    assert mine["dinh_muc_kh"]["minhanh"][name]["div"] == 3  # nằm trong file của chính khách đó


def test_chia_dinh_muc_chung_cu_vao_tung_khach(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    kodi_name = a.kodi_items[0]["name"]
    a.item_mem = {kodi_name: {"div": 9, "kg": 1.1, "hs": ""}, "Thùng Carton Box ABC-1": {"div": 20, "kg": 0.5, "hs": ""},
                  "Hàng lạ không rõ khách": {"div": 1, "kg": 1, "hs": ""}}
    a.erp_catalog = [{"ma_sp": "TM1", "ten_sp": "Thùng Carton Box ABC-1"}, {"ma_sp": "TM2", "ten_sp": "Hàng khác của khách khác"}]
    a.dinh_muc_kh, a.dinh_muc_kh_v, a.erp_rieng = {}, 0, {}
    assert a.tach_dinh_muc_theo_khach()
    assert a.get_item_norm(kodi_name, "kodi")["div"] == 9
    assert a.get_item_norm("Thùng Carton Box ABC-1", "shirai")["div"] == 20
    assert not any("Hàng lạ không rõ khách" in v for v in a.dinh_muc_kh.values())  # không rõ khách: không gán bừa
    assert [x["ma_sp"] for x in a.erp_rieng["shirai"]] == ["TM1"]  # Shirai chỉ giữ mã ERP của hàng Shirai
    assert set(a.erp_map.values()) == {"TM1"}
    assert a.item_mem[kodi_name]["div"] == 9  # bảng cũ giữ nguyên, không xóa
    assert not a.tach_dinh_muc_theo_khach()  # chỉ làm một lần


def test_khong_dung_erp():
    assert not app.uses_erp(app.PROFILES["shirai"]) and not app.uses_erp(app.PROFILES["tesa"])
    assert not app.bo_so_erp(app.PROFILES["shirai"])  # số kg/kiện ERP cũ trong Kg & kiện của khách: giữ làm dự phòng
    assert app.bo_so_erp({"noErp": True})


def test_lot_erp_info_rong(store):
    store.data_tong.append({"khach": "Tesa", "ten": "Ống tesa", "ma_hang": "39753-91390-00", "ma_erp": "TM9", "kg": 0.8, "kg_nguon": "erp"})
    store._dt_cache = {}
    assert app.lot_erp_info(store, "tesa", {"ma_sp": "39753-91390-00"}) == {}


def test_deli_bac_ninh_hai_phong_hai_ban_nhu_nhau(data_dir, tmp_path):
    a = make_store(data_dir, tmp_path, "a")
    add_deli(a)
    a.data_tong.append({"khach": "Deli Bắc Ninh", "ten": "340025128 Ống giấy 1250*76*3mm", "ma_hang": "340025128", "kg": 1.25, "kg_nguon": "tay",
                        "kien": 20, "kien_nguon": "tay", "ts": "2026-11-21 10:00:00"})
    a.dt_save()
    a.tu_chuyen_theo_khach()
    b = make_store(data_dir, tmp_path, "b")
    bn = json.load(open(b._khach_path("deli_bn"), encoding="utf-8"))
    hd = json.load(open(b._khach_path("deli_hd"), encoding="utf-8"))
    assert os.path.dirname(b._khach_path("deli_bn")) != os.path.dirname(b._khach_path("deli_hd"))  # mỗi bên một thư mục, một file
    codes = lambda d, k: sorted(x["code"] for x in d["danh_muc"]["custom_items"][k])
    assert codes(bn, "deli_bn") == codes(hd, "deli_hd") == ["340025128", "340025472"]
    rows = lambda d: sorted((r["ten"], r["kg"], r["kien"]) for r in d["data_tong"])
    assert rows(bn) == rows(hd) == [("340025128 Ống giấy 1250*76*3mm", 1.25, 20)]
    # sửa định mức ở một bên: bên kia cũng có
    b.remember_item_norm("340025472 Ống giấy 1250*38*3mm", 40, 0.9, customer="deli_hd")
    c = make_store(data_dir, tmp_path, "c")
    assert c.get_item_norm("340025472 Ống giấy 1250*38*3mm", "deli_bn")["div"] == 40
    assert next(x for x in c.custom_items["deli_bn"] if x["code"] == "340025472")["div"] == 40

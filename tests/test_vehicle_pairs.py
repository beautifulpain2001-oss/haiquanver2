"""Lái xe + biển số xe đi thành cặp, mỗi lô chọn ngẫu nhiên 1 cặp; khách đặt cố định thì giữ cặp của khách."""

import random

import pytest

import hongthien_desktop_app as app
from ui_qt.state import Lot


@pytest.fixture
def lot(store):
    return Lot(app, store)


def test_default_list_has_three_pairs(store):
    assert store.vehicle_list() == app.VEHICLE_DEFAULTS


def test_each_lot_gets_a_whole_pair(store):
    seen = set()
    for i in range(60):
        lot = Lot(app, store)
        lot.select_customer(("shirai", "kodi", "tesa")[i % 3])
        pair = {"driver": lot.form["driver"], "xe": lot.form["xe"]}
        assert pair in app.VEHICLE_PAIRS  # lái xe nào thì đúng biển số đó
        seen.add(pair["driver"])
    assert len(seen) > 1  # không còn cố định một lái xe cho mỗi khách


def test_pick_uses_random_source():
    picks = {app.pick_vehicle("kodi", rng=random.Random(s))["driver"] for s in range(30)}
    assert picks == {p["driver"] for p in app.VEHICLE_DEFAULTS}


def test_fixed_customer_keeps_its_pair(store, lot):
    store.update_customer("kodi", {"driver": "Lái Riêng", "xe": "Ô tô tải: 99X-111.11"})
    for _ in range(10):
        assert app.pick_vehicle("kodi") == {"driver": "Lái Riêng", "xe": "99X-111.11"}
    lot.select_customer("kodi")
    assert (lot.form["driver"], lot.form["xe"]) == ("Lái Riêng", "99X-111.11")


def test_old_saved_default_is_not_treated_as_fixed(data_dir):
    """Bản lưu cũ chỉ chép lại lái xe mặc định cũ của khách: nay coi như chưa đặt cố định (vẫn ngẫu nhiên)."""
    s = app.DedicatedDataStore(base_dir=str(data_dir))
    s.profile_overrides = {"tesa": {"driver": "Tô Anh Tiến", "xe": "99C-052.64", "name": "TESA SỬA"}}
    s.save_catalog()
    app.DedicatedDataStore(base_dir=str(data_dir))
    assert app.PROFILES["tesa"]["name"] == "TESA SỬA" and app.PROFILES["tesa"]["driver"] == ""
    assert app.fixed_vehicle("tesa") is None


def test_set_vehicles_persists_and_validates(store, data_dir):
    store.set_vehicles([{"driver": " Nguyễn Văn A ", "xe": "Ô tô tải: 98C-111.11"}, {"driver": "", "xe": ""},
                        {"driver": "Nguyễn Văn A", "xe": "98C-111.11"}, {"driver": "Trần B", "xe": "99H-222.22"}])
    want = [{"driver": "Nguyễn Văn A", "xe": "98C-111.11"}, {"driver": "Trần B", "xe": "99H-222.22"}]
    assert store.vehicle_list() == want
    assert app.DedicatedDataStore(base_dir=str(data_dir)).vehicle_list() == want
    assert app.pick_vehicle("shirai") in want
    with pytest.raises(ValueError, match="cả tên lái xe và biển số"):
        store.set_vehicles([{"driver": "Chỉ Tên", "xe": ""}])
    with pytest.raises(ValueError, match="ít nhất một cặp"):
        store.set_vehicles([])
    assert store.vehicle_list() == want  # lỗi thì không đổi gì


def test_fresh_store_uses_default_list(store, tmp_path):
    store.set_vehicles([{"driver": "X", "xe": "1"}])
    app.DedicatedDataStore(base_dir=str(tmp_path / "moi"))
    assert app.VEHICLE_PAIRS == app.VEHICLE_DEFAULTS


def test_editing_driver_switches_plate(lot):
    lot.select_customer("shirai")
    lot.form["driver"], lot.form["xe"] = "hồ quang hoàng".title(), "60H238.07"
    assert lot.match_vehicle("driver") and lot.form["xe"] == "99C-158.08"
    lot.form["driver"], lot.form["xe"] = "Hồ Quang Hoàng", "99C-052.64"
    assert lot.match_vehicle("xe") and lot.form["driver"] == "Tô Anh Tiến"
    lot.form["driver"] = "Người Ngoài Danh Sách"
    assert not lot.match_vehicle("driver") and lot.form["xe"] == "99C-052.64"


def test_fill_missing_half_from_same_pair(lot):
    lot.select_customer("kodi")
    lot.form["driver"], lot.form["xe"] = "Sẩm Ngọc Huy", ""
    lot.fill_vehicle_defaults()
    assert lot.form["xe"] == "60H238.07"

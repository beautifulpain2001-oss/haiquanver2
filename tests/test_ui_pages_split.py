"""Kiểm tra việc tách ui_qt/pages_other.py thành mỗi trang một file (T8)."""

import importlib
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

PAGE_MODULES = {
    "DeclarationsPage": "ui_qt.pages.declarations",
    "AddFilesDialog": "ui_qt.pages.declarations",
    "DataTongPage": "ui_qt.pages.data_tong",
    "RecordsPage": "ui_qt.pages.records",
    "CatalogPage": "ui_qt.pages.catalog",
    "CustomersPage": "ui_qt.pages.customers",
    "SettingsPage": "ui_qt.pages.settings",
}


def test_pages_live_in_own_module_and_are_reexported_from_pages_other():
    po = importlib.import_module("ui_qt.pages_other")
    for name, module_name in PAGE_MODULES.items():
        cls = getattr(importlib.import_module(module_name), name)
        assert cls.__module__ == module_name, name
        assert getattr(po, name) is cls, name


def test_main_window_uses_the_split_pages():
    mw = importlib.import_module("ui_qt.main_window")
    assert mw.CustomersPage.__module__ == "ui_qt.pages.customers"
    assert mw.RecordsPage.__module__ == "ui_qt.pages.records"

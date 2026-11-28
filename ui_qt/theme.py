"""Màu và kiểu chữ dùng chung cho giao diện mới.

Theo file thiết kế mẫu "Hệ thống Đối soát & Hải quan" Huy gửi (28/11/2026): hai kiểu giao diện, chuyển bằng công tắc ở thanh trên cùng.
- "kinh_mo"  (Kính mờ, kiểu Cupertino Glass): nền xám rất nhạt có vệt màu loang, khối nội dung trắng trong mờ bo 20px,
  nút chính đen #1D1D1F, chữ #1D1D1F / #6E6E73, nhấn xanh #0071E3.
- "tactile" (Soft Tactile / neumorphism): mọi thứ cùng nền #E0E5EC, khối nổi bằng viền sáng trên-trái + tối dưới-phải,
  ô nhập lõm ngược lại, chữ #4A5568, nhấn xanh #2B6CB0.
Mọi màu nằm ở PALETTES; QSS dựng từ token bằng build_style(). Đổi kiểu lúc đang chạy: apply(app, name).
"""

from PySide6.QtCore import QSettings

PALETTES = {
    "kinh_mo": {
        "label": "Kính mờ",
        "bg": "#F5F5F7",
        "side": "rgba(255,255,255,55%)",
        "side_line": "rgba(0,0,0,6%)",
        "surface": "rgba(255,255,255,72%)",
        "surface_solid": "#FFFFFF",
        "card_border": "1px solid rgba(255,255,255,90%)",
        "line": "rgba(0,0,0,8%)",
        "grid": "rgba(0,0,0,4%)",
        "text": "#1D1D1F",
        "muted": "#6E6E73",
        "deep": "#1D1D1F",
        "accent": "#0071E3",
        "accent_soft": "rgba(0,113,227,12%)",
        "focus": "#0071E3",
        # nút chính
        "p_bg": "#1D1D1F", "p_fg": "#FFFFFF", "p_hover": "#000000", "p_press": "#3A3A3C", "p_border": "2px solid #1D1D1F",
        "p_border_hover": "#000000", "p_border_press": "#3A3A3C",
        # nút phụ
        "s_bg": "rgba(0,0,0,5%)", "s_fg": "#1D1D1F", "s_hover": "rgba(0,0,0,10%)", "s_press": "rgba(0,0,0,14%)",
        "s_border": "2px solid transparent", "s_border_press": "transparent",
        # nút xuất (hành động lớn)
        "big_bg": "#248A3D", "big_fg": "#FFFFFF", "big_hover": "#1E7434", "big_border": "2px solid #248A3D",
        # ô nhập
        "in_bg": "rgba(255,255,255,60%)", "in_border": "1px solid rgba(0,0,0,10%)", "in_focus": "2px solid #0071E3", "in_radius": "12px",
        # bảng
        "tbl_bg": "rgba(255,255,255,70%)", "tbl_alt": "rgba(0,0,0,1.5%)", "head_bg": "rgba(0,0,0,2%)", "head_fg": "#6E6E73",
        "sel_bg": "rgba(0,113,227,12%)", "sel_fg": "#1D1D1F",
        # menu trái
        "nav_fg": "#6E6E73", "nav_hover": "rgba(0,0,0,4%)", "nav_sel_bg": "rgba(255,255,255,95%)", "nav_sel_fg": "#1D1D1F",
        "nav_sel_border": "1px solid rgba(0,0,0,6%)",
        # bước
        "step_cur_bg": "#1D1D1F", "step_cur_fg": "#FFFFFF", "step_cur_border": "none",
        # trạng thái
        "ok": "#248A3D", "ok_soft": "rgba(52,199,89,15%)", "warn": "#B26800", "warn_soft": "rgba(255,149,0,15%)",
        "err": "#C41C13", "err_soft": "rgba(255,59,48,12%)", "info_soft": "rgba(0,113,227,10%)",
        "dng_border": "2px solid rgba(255,59,48,25%)",
        "radius_card": "20px", "radius_btn": "12px",
        # màu biểu tượng theo vai trò nút
        "icon": {"": "#FFFFFF", "sec": "#1D1D1F", "dng": "#C41C13", "ghost": "#0071E3", "big": "#FFFFFF", "chip": "#1D1D1F"},
        "icon_off": "#AEAEB2", "nav_icon": "#6E6E73",
        "logo_bg": "#1D1D1F", "logo_fg": "#FFFFFF",
    },
    "tactile": {
        "label": "Tactile",
        "bg": "#E0E5EC",
        "side": "#E0E5EC",
        "side_line": "#C8D0DC",
        "surface": "#E0E5EC",
        "surface_solid": "#E0E5EC",
        "card_border": "2px solid; border-color: #FFFFFF #BAC5D5 #BAC5D5 #FFFFFF",
        "line": "#C8D0DC",
        "grid": "rgba(163,177,198,25%)",
        "text": "#4A5568",
        "muted": "#718096",
        "deep": "#2D3748",
        "accent": "#2B6CB0",
        "accent_soft": "rgba(43,108,176,12%)",
        "focus": "#2B6CB0",
        "p_bg": "#E0E5EC", "p_fg": "#2B6CB0", "p_hover": "#E6EBF1", "p_press": "#D5DCE5",
        "p_border": "2px solid; border-color: #FFFFFF #A3B1C6 #A3B1C6 #FFFFFF",
        "p_border_hover": "#FFFFFF #95A5BC #95A5BC #FFFFFF", "p_border_press": "#A3B1C6 #FFFFFF #FFFFFF #A3B1C6",
        "s_bg": "#E0E5EC", "s_fg": "#4A5568", "s_hover": "#E6EBF1", "s_press": "#D5DCE5",
        "s_border": "2px solid; border-color: #FFFFFF #B4C0D0 #B4C0D0 #FFFFFF", "s_border_press": "#A3B1C6 #FFFFFF #FFFFFF #A3B1C6",
        "big_bg": "#E0E5EC", "big_fg": "#2F855A", "big_hover": "#E6EBF1", "big_border": "2px solid; border-color: #FFFFFF #A3B1C6 #A3B1C6 #FFFFFF",
        "in_bg": "#D9DFE7", "in_border": "2px solid; border-color: #A3B1C6 #FFFFFF #FFFFFF #A3B1C6", "in_focus": "2px solid #2B6CB0", "in_radius": "12px",
        "tbl_bg": "#E4E8EE", "tbl_alt": "#DDE2EA", "head_bg": "#E0E5EC", "head_fg": "#718096",
        "sel_bg": "#CFD9E6", "sel_fg": "#2B6CB0",
        "nav_fg": "#718096", "nav_hover": "#E6EBF1", "nav_sel_bg": "#D7DDE6", "nav_sel_fg": "#2B6CB0",
        "nav_sel_border": "2px solid; border-color: #A3B1C6 #FFFFFF #FFFFFF #A3B1C6",
        "step_cur_bg": "#D7DDE6", "step_cur_fg": "#2B6CB0", "step_cur_border": "2px solid; border-color: #A3B1C6 #FFFFFF #FFFFFF #A3B1C6",
        "ok": "#2F855A", "ok_soft": "#D6E8DF", "warn": "#B26800", "warn_soft": "#ECE2D3",
        "err": "#C53030", "err_soft": "#EBD8DA", "info_soft": "#D5DFEB",
        "dng_border": "2px solid; border-color: #FFFFFF #B4C0D0 #B4C0D0 #FFFFFF",
        "radius_card": "20px", "radius_btn": "12px",
        "icon": {"": "#2B6CB0", "sec": "#4A5568", "dng": "#C53030", "ghost": "#2B6CB0", "big": "#2F855A", "chip": "#4A5568"},
        "icon_off": "#A0AEC0", "nav_icon": "#718096",
        "logo_bg": "#E0E5EC", "logo_fg": "#2B6CB0",
    },
}
DEFAULT = "kinh_mo"
_SETTINGS = ("HongThien", "HaiQuan")
_KEY = "giao_dien"

# Hằng số cũ (các trang đang dùng theme.OK / WARN / MUTED...): luôn trỏ tới kiểu đang bật
NAVY = NAVY_DARK = BG = CARD = LINE = TEXT = MUTED = OK = WARN = ERR = DEEP = SOFT = CARD_LINE = ""
CURRENT = DEFAULT
_listeners = []


def _set_constants(name):
    global CURRENT, NAVY, NAVY_DARK, BG, CARD, LINE, TEXT, MUTED, OK, WARN, ERR, DEEP, SOFT, CARD_LINE
    t = PALETTES[name]
    CURRENT = name
    NAVY, NAVY_DARK = t["accent"], t["accent"]
    BG, CARD, LINE, CARD_LINE = t["bg"], t["surface_solid"], t["line"], t["line"]
    TEXT, MUTED, DEEP, SOFT = t["text"], t["muted"], t["deep"], t["accent_soft"]
    OK, WARN, ERR = t["ok"], t["warn"], t["err"]


def tokens(name=None):
    return PALETTES[name or CURRENT]


def build_style(name=DEFAULT):
    t = PALETTES[name]
    return f"""
* {{ font-family: "Be Vietnam Pro", "Segoe UI", "Noto Sans", sans-serif; font-size: 11pt; color: {t['text']}; }}
QMainWindow, QDialog, QMessageBox, QInputDialog {{ background: {t['bg']}; }}
QWidget#page {{ background: transparent; }}
QWidget#inner {{ background: transparent; }}
QWidget#side {{ background: {t['side']}; border-right: 1px solid {t['side_line']}; }}
QLabel#brand {{ color: {t['deep']}; font-size: 11pt; font-weight: 700; }}
QLabel#brandsub {{ color: {t['muted']}; font-size: 9pt; }}
QLabel#themelabel {{ color: {t['muted']}; font-size: 9pt; font-weight: 600; }}
QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
QListWidget#nav::item {{ color: {t['nav_fg']}; font-size: 9pt; margin: 3px 8px; border-radius: 16px; border: 2px solid transparent; }}
QListWidget#nav::item:hover {{ background: {t['nav_hover']}; }}
QListWidget#nav::item:selected {{ background: {t['nav_sel_bg']}; color: {t['nav_sel_fg']}; font-weight: 600; border: {t['nav_sel_border']}; }}
QWidget#topbar {{ background: transparent; }}
QLabel#title {{ font-size: 16pt; font-weight: 700; color: {t['deep']}; }}
QLabel#hint {{ color: {t['muted']}; }}
QLabel[step="done"] {{ color: {t['ok']}; font-weight: 600; padding: 6px 10px; }}
QLabel[step="current"] {{ color: {t['step_cur_fg']}; background: {t['step_cur_bg']}; border: {t['step_cur_border']}; border-radius: 16px; padding: 6px 16px; font-weight: 600; }}
QLabel[step="todo"] {{ color: {t['muted']}; padding: 6px 14px; }}
QFrame#card {{ background: {t['surface']}; border: {t['card_border']}; border-radius: {t['radius_card']}; }}
QPushButton {{ background: {t['p_bg']}; color: {t['p_fg']}; border: {t['p_border']}; border-radius: {t['radius_btn']}; padding: 0 20px; min-height: 40px; font-weight: 600; }}
QPushButton:hover {{ background: {t['p_hover']}; border-color: {t['p_border_hover']}; }}
QPushButton:pressed {{ background: {t['p_press']}; border-color: {t['p_border_press']}; padding-top: 2px; }}
QPushButton:focus {{ outline: none; }}
QPushButton:disabled {{ background: {t['s_bg']}; color: {t['icon_off']}; border-color: transparent; }}
QPushButton#cust {{ background: {t['surface']}; color: {t['text']}; border: {t['card_border']}; border-radius: 16px; padding: 16px 12px; text-align: left; }}
QPushButton#cust:hover {{ background: {t['surface_solid']}; }}
QPushButton#cust:checked {{ border: 2px solid {t['accent']}; background: {t['accent_soft']}; color: {t['deep']}; font-weight: 600; }}
QPushButton#drop {{ background: {t['in_bg']}; color: {t['accent']}; border: 2px dashed {t['muted']}; border-radius: 16px; padding: 28px; font-size: 12pt; }}
QPushButton#drop:hover {{ border-color: {t['accent']}; background: {t['accent_soft']}; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 700; color: {t['deep']}; }}
QPushButton#sec {{ background: {t['s_bg']}; color: {t['s_fg']}; border: {t['s_border']}; font-weight: 600; }}
QPushButton#sec:hover {{ background: {t['s_hover']}; }}
QPushButton#sec:pressed {{ background: {t['s_press']}; border-color: {t['s_border_press']}; }}
QPushButton#sec:disabled {{ color: {t['icon_off']}; }}
QPushButton#dng {{ background: {t['err_soft']}; color: {t['err']}; border: {t['dng_border']}; font-weight: 600; }}
QPushButton#dng:hover {{ background: {t['err_soft']}; border-color: {t['err']}; }}
QPushButton#dng:pressed {{ background: {t['s_press']}; }}
QPushButton#dng:disabled {{ background: {t['s_bg']}; color: {t['icon_off']}; border-color: transparent; }}
QPushButton#ghost {{ background: transparent; color: {t['accent']}; border: 2px solid transparent; font-weight: 600; }}
QPushButton#ghost:hover {{ background: {t['s_bg']}; }}
QPushButton#ghost:pressed {{ background: {t['s_hover']}; }}
QPushButton#ghost:disabled {{ background: transparent; color: {t['icon_off']}; }}
QPushButton#big {{ background: {t['big_bg']}; color: {t['big_fg']}; border: {t['big_border']}; font-size: 13pt; font-weight: 700; padding: 0 24px; min-height: 48px; border-radius: 16px; }}
QPushButton#big:hover {{ background: {t['big_hover']}; }}
QPushButton#big:pressed {{ background: {t['p_press']}; border-color: {t['p_border_press']}; }}
QPushButton#big:disabled {{ background: {t['s_bg']}; color: {t['icon_off']}; border-color: transparent; }}
QPushButton#chip {{ background: {t['s_bg']}; color: {t['s_fg']}; border: {t['s_border']}; border-radius: 15px; padding: 0 14px; min-height: 30px; font-weight: 500; }}
QPushButton#chip:hover {{ background: {t['s_hover']}; }}
QPushButton#chip:checked {{ background: {t['step_cur_bg']}; color: {t['step_cur_fg']}; border: {t['step_cur_border'] if t['step_cur_border'] != 'none' else '2px solid ' + t['step_cur_bg']}; font-weight: 600; }}
QGroupBox {{ background: {t['surface']}; border: {t['card_border']}; border-radius: 16px; margin-top: 14px; padding: 16px 12px 10px 12px; font-weight: 700; color: {t['deep']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; }}
QLabel#banner_ok {{ background: {t['ok_soft']}; color: {t['ok']}; border-radius: 12px; padding: 8px 14px; font-weight: 600; }}
QLabel#banner_warn {{ background: {t['warn_soft']}; color: {t['warn']}; border-radius: 12px; padding: 8px 14px; font-weight: 600; }}
QLabel#banner_bad {{ background: {t['err_soft']}; color: {t['err']}; border-radius: 12px; padding: 8px 14px; font-weight: 600; }}
QLabel#banner_info {{ background: {t['info_soft']}; color: {t['accent']}; border-radius: 12px; padding: 8px 14px; }}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{ background: {t['in_bg']}; border: {t['in_border']}; border-radius: {t['in_radius']}; padding: 0 14px; min-height: 38px; font-size: 11pt; }}
QPlainTextEdit, QTextEdit {{ background: {t['in_bg']}; border: {t['in_border']}; border-radius: {t['in_radius']}; padding: 6px 10px; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {t['surface_solid']}; border: 1px solid {t['line']}; selection-background-color: {t['sel_bg']}; selection-color: {t['sel_fg']}; outline: 0; }}
QTableWidget QLineEdit, QTableWidget QComboBox {{ border-radius: 6px; padding: 2px 6px; min-height: 22px; border: 1px solid {t['accent']}; background: {t['surface_solid']}; }}
QLineEdit[warn="true"] {{ border: 2px solid {t['warn']}; background: {t['warn_soft']}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: {t['in_focus']}; }}
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 6px; background: {t['in_bg']}; border: {t['in_border']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border: 2px solid {t['accent']}; }}
QTableWidget, QTableView, QTreeWidget {{ font-size: 10pt; background: {t['tbl_bg']}; alternate-background-color: {t['tbl_alt']}; border: {t['in_border'] if name == 'tactile' else '1px solid ' + t['line']}; border-radius: 14px; gridline-color: {t['grid']}; selection-background-color: {t['sel_bg']}; selection-color: {t['sel_fg']}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {t['head_bg']}; color: {t['head_fg']}; font-size: 10pt; font-weight: 600; border: none; border-bottom: 1px solid {t['line']}; padding: 8px 4px; }}
QTableCornerButton::section {{ background: {t['head_bg']}; border: none; }}
QTableWidget::item:selected, QTableView::item:selected {{ background: {t['sel_bg']}; color: {t['sel_fg']}; }}
QListWidget {{ background: {t['tbl_bg']}; border: {t['in_border'] if name == 'tactile' else '1px solid ' + t['line']}; border-radius: 12px; outline: 0; }}
QListWidget::item {{ padding: 9px 10px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {t['sel_bg']}; color: {t['sel_fg']}; }}
QProgressBar {{ background: {t['in_bg']}; border: none; border-radius: 5px; text-align: center; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 5px; }}
QTabWidget::pane {{ border: {t['card_border']}; border-radius: 14px; background: {t['surface']}; top: -1px; }}
QTabBar::tab {{ padding: 8px 18px; background: transparent; color: {t['muted']}; border: none; border-bottom: 2px solid transparent; margin-right: 4px; font-weight: 600; }}
QTabBar::tab:hover {{ color: {t['text']}; }}
QTabBar::tab:selected {{ color: {t['deep'] if name == 'kinh_mo' else t['accent']}; border-bottom: 2px solid {t['deep'] if name == 'kinh_mo' else t['accent']}; }}
QFrame#textcard {{ background: {t['surface']}; border: {t['card_border']}; border-radius: 14px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['line'] if name == 'kinh_mo' else '#B4C0D0'}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['line'] if name == 'kinh_mo' else '#B4C0D0'}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {'rgba(29,29,31,92%)' if name == 'kinh_mo' else '#E0E5EC'}; color: {'#FFFFFF' if name == 'kinh_mo' else '#4A5568'}; border: 1px solid {t['line']}; border-radius: 8px; padding: 6px 10px; }}
QMenu {{ background: {t['surface_solid']}; border: 1px solid {t['line']}; border-radius: 10px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['sel_bg']}; color: {t['sel_fg']}; }}
QTableWidget QPushButton {{ padding: 2px 10px; min-height: 26px; border-radius: 10px; border-width: 1px; }}
"""


def saved_name():
    try:
        v = QSettings(*_SETTINGS).value(_KEY, DEFAULT)
    except Exception:
        v = DEFAULT
    return v if v in PALETTES else DEFAULT


def save_name(name):
    try:
        QSettings(*_SETTINGS).setValue(_KEY, name)
    except Exception:
        pass


def on_change(fn):
    """Đăng ký hàm gọi lại sau khi đổi kiểu giao diện (vẽ lại banner, đổi màu biểu tượng...)."""
    _listeners.append(fn)


def apply(app, name, save=True):
    """Bật kiểu giao diện `name` cho cả phần mềm (đang chạy vẫn đổi được)."""
    if name not in PALETTES:
        name = DEFAULT
    _set_constants(name)
    app.setStyleSheet(build_style(name))
    if save:
        save_name(name)
    for fn in list(_listeners):
        try:
            fn(name)
        except RuntimeError:  # widget đã bị hủy
            _listeners.remove(fn)


_set_constants(DEFAULT)
STYLE = build_style(DEFAULT)  # giữ cho code/test cũ: app.setStyleSheet(theme.STYLE)

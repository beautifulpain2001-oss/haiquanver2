"""Màu và kiểu chữ dùng chung cho giao diện mới."""

NAVY = "#1570D8"  # primary (nút chính, mục đang chọn)
NAVY_DARK = "#0F5CB8"  # primary khi rê chuột
BG = "#F7FAFF"
CARD = "#FFFFFF"
LINE = "#D4E4F7"
TEXT = "#12263F"
MUTED = "#4A5B73"
OK = "#0B6B3A"
WARN = "#8A4400"
ERR = "#A21B1B"
DEEP = "#0B3F85"  # tiêu đề
SOFT = "#E1EFFF"  # nền mục đang chọn
CARD_LINE = "#E3EEFB"

STYLE = f"""
* {{ font-family: "Be Vietnam Pro", "Segoe UI", "Noto Sans", sans-serif; font-size: 11pt; color: {TEXT}; }}
QMainWindow, QWidget#page {{ background: {BG}; }}
QWidget#inner {{ background: transparent; }}
QWidget#side {{ background: #FFFFFF; border-right: 1px solid {CARD_LINE}; }}
QLabel#brand {{ color: {DEEP}; font-size: 11pt; font-weight: 700; }}
QLabel#brandsub {{ color: {MUTED}; font-size: 9pt; }}
QListWidget#nav {{ background: #FFFFFF; border: none; outline: 0; }}
QListWidget#nav::item {{ color: #36506F; font-size: 9pt; margin: 2px 6px; border-radius: 14px; }}
QListWidget#nav::item:hover {{ background: #F2F7FE; }}
QListWidget#nav::item:selected {{ background: {SOFT}; color: {DEEP}; font-weight: 600; }}
QWidget#topbar {{ background: {BG}; }}
QLabel#title {{ font-size: 16pt; font-weight: 700; color: {DEEP}; }}
QLabel#hint {{ color: {MUTED}; }}
QLabel[step="done"] {{ color: {OK}; font-weight: 600; }}
QLabel[step="current"] {{ color: #FFFFFF; background: {NAVY}; border-radius: 14px; padding: 6px 14px; font-weight: 600; }}
QLabel[step="todo"] {{ color: {MUTED}; padding: 6px 14px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {CARD_LINE}; border-radius: 20px; }}
QPushButton {{ background: {NAVY}; color: #FFFFFF; border: 2px solid {NAVY}; border-radius: 22px; padding: 0 20px; min-height: 40px; font-weight: 600; }}
QPushButton:hover {{ background: {NAVY_DARK}; border-color: {NAVY_DARK}; }}
QPushButton:pressed {{ background: #0F2038; border-color: #0F2038; padding-top: 6px; padding-bottom: 4px; }}
QPushButton:focus {{ border-color: #8CC2FF; }}
QPushButton:disabled {{ background: #EDF2F7; color: #7A8CA5; border-color: #E3EEFB; }}
QPushButton#cust {{ background: {CARD}; color: {TEXT}; border: 2px solid {LINE}; border-radius: 10px; padding: 16px 12px; text-align: left; }}
QPushButton#cust:hover {{ border-color: #63B3ED; background: #EBF8FF; }}
QPushButton#cust:checked {{ border-color: {NAVY}; background: #EBF4FF; font-weight: 600; }}
QPushButton#drop {{ background: #FAFBFD; color: {NAVY}; border: 2px dashed {LINE}; border-radius: 10px; padding: 28px; font-size: 12pt; }}
QPushButton#drop:hover {{ border-color: {NAVY}; background: #EBF4FF; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 700; color: {DEEP}; }}
QPushButton#sec {{ background: #FFFFFF; color: #0B4FA8; border: 2px solid #BFD8F5; font-weight: 600; }}
QPushButton#sec:hover {{ background: #EEF6FF; border-color: #8CC2FF; }}
QPushButton#sec:pressed {{ background: #E1EFFF; border-color: #8CC2FF; }}
QPushButton#sec:focus {{ border-color: #8CC2FF; }}
QPushButton#sec:disabled {{ background: #F7FAFC; color: #A0AEC0; border-color: #EDF2F7; }}
QPushButton#dng {{ background: #FFFFFF; color: {ERR}; border: 2px solid #F8B4B4; font-weight: 600; }}
QPushButton#dng:hover {{ background: #FDE8E8; border-color: #F05252; }}
QPushButton#dng:pressed {{ background: #FBD5D5; border-color: #F05252; }}
QPushButton#dng:focus {{ border-color: #8CC2FF; }}
QPushButton#dng:disabled {{ background: #F7FAFC; color: #A0AEC0; border-color: #EDF2F7; }}
QPushButton#ghost {{ background: transparent; color: #0B4FA8; border: 2px solid transparent; font-weight: 600; }}
QPushButton#ghost:hover {{ background: #EDF2F7; }}
QPushButton#ghost:pressed {{ background: #E2E8F0; }}
QPushButton#ghost:focus {{ border-color: #8CC2FF; }}
QPushButton#ghost:disabled {{ background: transparent; color: #A0AEC0; }}
QPushButton#big {{ background: #2F855A; border-color: #2F855A; font-size: 13pt; font-weight: 700; padding: 0 22px; min-height: 48px; border-radius: 24px; }}
QPushButton#big:hover {{ background: #276749; border-color: #276749; }}
QPushButton#big:focus {{ border-color: #8CC2FF; }}
QPushButton#big:disabled {{ background: {LINE}; }}
QGroupBox {{ border: 1px solid {CARD_LINE}; border-radius: 16px; margin-top: 12px; padding: 14px 12px 10px 12px; font-weight: 700; color: {DEEP}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
QLabel#banner_ok {{ background: #DEF7EC; color: {OK}; border-left: 5px solid #0E9F6E; border-radius: 4px; padding: 8px 12px; font-weight: 600; }}
QLabel#banner_warn {{ background: #FDF6B2; color: {WARN}; border-left: 5px solid #C27803; border-radius: 4px; padding: 8px 12px; font-weight: 600; }}
QLabel#banner_bad {{ background: #FDE8E8; color: {ERR}; border-left: 5px solid #E02424; border-radius: 4px; padding: 8px 12px; font-weight: 600; }}
QLabel#banner_info {{ background: #EBF4FF; color: {NAVY}; border-left: 5px solid #3F83F8; border-radius: 4px; padding: 8px 12px; }}
QPushButton#chip {{ background: #FFFFFF; color: {TEXT}; border: 1px solid {LINE}; border-radius: 16px; padding: 0 14px; min-height: 30px; }}
QPushButton#chip:hover {{ background: #EEF6FF; }}
QPushButton#chip:checked {{ background: {NAVY}; color: #FFFFFF; border-color: {NAVY}; font-weight: 600; }}
QPushButton#chip:focus {{ border: 1px solid #8CC2FF; }}
QLineEdit, QComboBox {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 20px; padding: 0 14px; min-height: 38px; font-size: 11pt; }}
QTableWidget QLineEdit, QTableWidget QComboBox {{ border-radius: 6px; padding: 2px 6px; min-height: 22px; }}
QLineEdit[warn="true"] {{ border: 1px solid #C27803; background: #FFFBEB; }}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid #8CC2FF; }}
QTableWidget {{ font-size: 10pt; background: #FFFFFF; alternate-background-color: #F7FAFF; border: 1px solid {LINE}; border-radius: 12px; gridline-color: #EEF4FC; }}
QHeaderView::section {{ background: #F2F7FE; color: #36506F; font-size: 10pt; font-weight: 600; border: none; border-right: 1px solid {LINE}; padding: 8px 4px; }}
QTableWidget::item:selected {{ background: {SOFT}; color: {DEEP}; }}
QListWidget {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 6px; }}
QProgressBar {{ background: #E2E8F0; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {NAVY}; border-radius: 4px; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 6px; }}
QTabBar::tab {{ padding: 8px 18px; background: #E8EEF7; color: #3F516B; border-top-left-radius: 14px; border-top-right-radius: 14px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {NAVY}; color: #FFFFFF; }}
QFrame#textcard {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 6px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QListWidget::item {{ padding: 9px 10px; }}
QListWidget::item:selected {{ background: {SOFT}; color: {DEEP}; }}
QTableWidget QPushButton {{ padding: 2px 10px; min-height: 26px; border-radius: 13px; border-width: 1px; }}
"""

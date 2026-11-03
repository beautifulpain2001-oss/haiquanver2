"""Màu và kiểu chữ dùng chung cho giao diện mới."""

NAVY = "#1B365D"
NAVY_DARK = "#142A4A"
BG = "#F4F6F9"
CARD = "#FFFFFF"
LINE = "#CBD5E0"
TEXT = "#1A202C"
MUTED = "#4A5568"
OK = "#03543F"
WARN = "#92400E"
ERR = "#9B1C1C"

STYLE = f"""
* {{ font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 11pt; color: {TEXT}; }}
QMainWindow, QWidget#page {{ background: {BG}; }}
QWidget#inner {{ background: transparent; }}
QWidget#side {{ background: {NAVY}; }}
QLabel#brand {{ color: #FFFFFF; font-size: 14pt; font-weight: 700; padding: 22px 20px 0 20px; }}
QLabel#brandsub {{ color: #A0AEC0; font-size: 9pt; padding: 2px 20px 18px 20px; }}
QListWidget#nav {{ background: {NAVY}; border: none; outline: 0; }}
QListWidget#nav::item {{ color: #E2E8F0; padding: 13px 20px; margin: 2px 8px; border-radius: 6px; }}
QListWidget#nav::item:hover {{ background: #24487C; }}
QListWidget#nav::item:selected {{ background: #2C5282; color: #FFFFFF; font-weight: 600; }}
QLabel#title {{ font-size: 16pt; font-weight: 600; color: {NAVY}; }}
QLabel#hint {{ color: {MUTED}; }}
QLabel[step="done"] {{ color: {OK}; font-weight: 600; }}
QLabel[step="current"] {{ color: #FFFFFF; background: {NAVY}; border-radius: 14px; padding: 6px 14px; font-weight: 600; }}
QLabel[step="todo"] {{ color: {MUTED}; padding: 6px 14px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QPushButton {{ background: {NAVY}; color: #FFFFFF; border: 2px solid {NAVY}; border-radius: 6px; padding: 5px 16px; min-height: 26px; font-weight: 600; }}
QPushButton:hover {{ background: {NAVY_DARK}; border-color: {NAVY_DARK}; }}
QPushButton:pressed {{ background: #0F2038; border-color: #0F2038; padding-top: 6px; padding-bottom: 4px; }}
QPushButton:focus {{ border-color: #3F83F8; }}
QPushButton:disabled {{ background: #EDF2F7; color: #94A3B8; border-color: #E2E8F0; }}
QPushButton#cust {{ background: {CARD}; color: {TEXT}; border: 2px solid {LINE}; border-radius: 10px; padding: 16px 12px; text-align: left; }}
QPushButton#cust:hover {{ border-color: #63B3ED; background: #EBF8FF; }}
QPushButton#cust:checked {{ border-color: {NAVY}; background: #EBF4FF; font-weight: 600; }}
QPushButton#drop {{ background: #FAFBFD; color: {NAVY}; border: 2px dashed {LINE}; border-radius: 10px; padding: 28px; font-size: 12pt; }}
QPushButton#drop:hover {{ border-color: {NAVY}; background: #EBF4FF; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; color: {NAVY}; }}
QPushButton#sec {{ background: #FFFFFF; color: {NAVY}; border: 2px solid {LINE}; font-weight: 600; }}
QPushButton#sec:hover {{ background: #EDF2F7; border-color: #A0AEC0; }}
QPushButton#sec:pressed {{ background: #E2E8F0; border-color: #A0AEC0; }}
QPushButton#sec:focus {{ border-color: #3F83F8; }}
QPushButton#sec:disabled {{ background: #F7FAFC; color: #A0AEC0; border-color: #EDF2F7; }}
QPushButton#dng {{ background: #FFFFFF; color: {ERR}; border: 2px solid #F8B4B4; font-weight: 600; }}
QPushButton#dng:hover {{ background: #FDE8E8; border-color: #F05252; }}
QPushButton#dng:pressed {{ background: #FBD5D5; border-color: #F05252; }}
QPushButton#dng:focus {{ border-color: #3F83F8; }}
QPushButton#dng:disabled {{ background: #F7FAFC; color: #A0AEC0; border-color: #EDF2F7; }}
QPushButton#ghost {{ background: transparent; color: {NAVY}; border: 2px solid transparent; font-weight: 600; }}
QPushButton#ghost:hover {{ background: #EDF2F7; }}
QPushButton#ghost:pressed {{ background: #E2E8F0; }}
QPushButton#ghost:focus {{ border-color: #3F83F8; }}
QPushButton#ghost:disabled {{ background: transparent; color: #A0AEC0; }}
QPushButton#big {{ background: #2F855A; border-color: #2F855A; font-size: 13pt; font-weight: 700; padding: 12px 18px; border-radius: 8px; }}
QPushButton#big:hover {{ background: #276749; border-color: #276749; }}
QPushButton#big:focus {{ border-color: #3F83F8; }}
QPushButton#big:disabled {{ background: {LINE}; }}
QGroupBox {{ border: 1px solid {LINE}; border-radius: 8px; margin-top: 12px; padding: 14px 12px 10px 12px; font-weight: 600; color: {NAVY}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
QLabel#banner_ok {{ background: #DEF7EC; color: {OK}; border-left: 5px solid #0E9F6E; border-radius: 4px; padding: 8px 12px; font-weight: 600; }}
QLabel#banner_warn {{ background: #FDF6B2; color: {WARN}; border-left: 5px solid #C27803; border-radius: 4px; padding: 8px 12px; font-weight: 600; }}
QLabel#banner_bad {{ background: #FDE8E8; color: {ERR}; border-left: 5px solid #E02424; border-radius: 4px; padding: 8px 12px; font-weight: 600; }}
QLabel#banner_info {{ background: #EBF4FF; color: {NAVY}; border-left: 5px solid #3F83F8; border-radius: 4px; padding: 8px 12px; }}
QPushButton#chip {{ background: #FFFFFF; color: {TEXT}; border: 1px solid {LINE}; border-radius: 14px; padding: 5px 14px; }}
QPushButton#chip:hover {{ background: #EDF2F7; }}
QPushButton#chip:checked {{ background: {NAVY}; color: #FFFFFF; border-color: {NAVY}; font-weight: 600; }}
QPushButton#chip:focus {{ border: 1px solid #3F83F8; }}
QLineEdit, QComboBox {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 6px; padding: 6px 10px; min-height: 24px; font-size: 11pt; }}
QLineEdit[warn="true"] {{ border: 1px solid #C27803; background: #FFFBEB; }}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {NAVY}; }}
QTableWidget {{ font-size: 10pt; background: #FFFFFF; alternate-background-color: #F7FAFC; border: 1px solid {LINE}; border-radius: 6px; gridline-color: #EDF2F7; }}
QHeaderView::section {{ background: #EDF2F7; color: {NAVY}; font-size: 10pt; font-weight: 600; border: none; border-right: 1px solid {LINE}; padding: 8px 4px; }}
QTableWidget::item:selected {{ background: #BEE3F8; color: {TEXT}; }}
QListWidget {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 6px; }}
QProgressBar {{ background: #E2E8F0; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {NAVY}; border-radius: 4px; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 6px; }}
QTabBar::tab {{ padding: 8px 16px; background: #EDF2F7; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {NAVY}; color: #FFFFFF; }}
QFrame#textcard {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 6px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QListWidget::item {{ padding: 9px 10px; }}
QListWidget::item:selected {{ background: #BEE3F8; color: {TEXT}; }}
QTableWidget QPushButton {{ padding: 5px 10px; }}
"""

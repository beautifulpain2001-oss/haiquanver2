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
QPushButton {{ background: {NAVY}; color: #FFFFFF; border: none; border-radius: 6px; padding: 8px 18px; }}
QPushButton:hover {{ background: {NAVY_DARK}; }}
QPushButton:disabled {{ background: {LINE}; color: {MUTED}; }}
QPushButton#cust {{ background: {CARD}; color: {TEXT}; border: 2px solid {LINE}; border-radius: 10px; padding: 16px 12px; text-align: left; }}
QPushButton#cust:hover {{ border-color: #63B3ED; background: #EBF8FF; }}
QPushButton#cust:checked {{ border-color: {NAVY}; background: #EBF4FF; font-weight: 600; }}
QPushButton#drop {{ background: #FAFBFD; color: {NAVY}; border: 2px dashed {LINE}; border-radius: 10px; padding: 28px; font-size: 12pt; }}
QPushButton#drop:hover {{ border-color: {NAVY}; background: #EBF4FF; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; color: {NAVY}; }}
"""

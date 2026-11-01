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
QListWidget#nav {{ background: {NAVY}; border: none; padding-top: 8px; outline: 0; }}
QListWidget#nav::item {{ color: #E2E8F0; padding: 12px 18px; }}
QListWidget#nav::item:selected {{ background: {NAVY_DARK}; color: #FFFFFF; border-left: 4px solid #63B3ED; }}
QLabel#title {{ font-size: 16pt; font-weight: 600; color: {NAVY}; }}
QLabel#hint {{ color: {MUTED}; }}
QLabel[step="done"] {{ color: {OK}; font-weight: 600; }}
QLabel[step="current"] {{ color: #FFFFFF; background: {NAVY}; border-radius: 14px; padding: 6px 14px; font-weight: 600; }}
QLabel[step="todo"] {{ color: {MUTED}; padding: 6px 14px; }}
QFrame#card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; }}
QPushButton {{ background: {NAVY}; color: #FFFFFF; border: none; border-radius: 6px; padding: 8px 18px; }}
QPushButton:hover {{ background: {NAVY_DARK}; }}
QPushButton:disabled {{ background: {LINE}; color: {MUTED}; }}
"""

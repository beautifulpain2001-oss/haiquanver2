@echo off
chcp 65001 >nul
echo =====================================================================
echo   KHOI DONG PHAN MEM DESKTOP HO SO HAI QUAN - HONG THIEN
echo   (Chay Offline 100%% tren Desktop - Tap luu tru du lieu rieng)
echo =====================================================================
python -c "import openpyxl" 2>nul || pip install openpyxl pypdf
start "" pythonw hongthien_desktop_app.py || python hongthien_desktop_app.py

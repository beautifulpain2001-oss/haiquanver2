@echo off
chcp 65001 >nul
echo =====================================================================
echo   DONG GOI THANH FILE .EXE DOC LAP TREN WINDOWS DESKTOP
echo =====================================================================
pip install pyinstaller openpyxl pypdf
pyinstaller --noconsole --onefile --name "HongThien_HaiQuan_Desktop" hongthien_desktop_app.py
echo.
echo Da tao xong file dist\HongThien_HaiQuan_Desktop.exe!
pause

@echo off
chcp 65001 >nul
echo =====================================================================
echo   DONG GOI THANH FILE .EXE DOC LAP TREN WINDOWS DESKTOP
echo   (Khong can tu lam: co the tai ban .exe san tu GitHub Actions/Releases)
echo =====================================================================
pip install -r requirements-build.txt || goto :loi
python build_exe.py || goto :loi
echo.
echo Da tao xong dist\HongThien_HaiQuan_Desktop.exe va dist\HongThien_HaiQuan_Desktop_Windows.zip
pause
exit /b 0
:loi
echo.
echo DONG GOI THAT BAI - xem thong bao loi o tren.
pause
exit /b 1

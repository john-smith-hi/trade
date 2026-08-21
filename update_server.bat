@echo off
cd /d "%~dp0"
REM =============================================================================
REM Cap nhat THU CONG (tuy chon). Thuong khong can: start_server.bat tu git pull
REM + copy_www khi phat hien commit moi tren remote (~2 phut/lan).
REM
REM Dung file nay khi muon pull ngay lap tuc, khong doi chu ky auto-update.
REM =============================================================================

echo === 1/4 git pull ===
git pull
if errorlevel 1 (
  echo git pull that bai. Dung lai.
  pause
  exit /b 1
)

echo.
echo === 2/4 copy UI len WAMP ===
python copy_www.py
if errorlevel 1 (
  echo copy_www.py that bai. Dung lai.
  pause
  exit /b 1
)

echo.
echo === 3/4 dung API cu ===
wmic process where "CommandLine like '%%api.py%%'" call terminate >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo === 4/4 khoi dong start_server.bat (cua so moi) ===
start "MT5 API 24/7" cmd /k start_server.bat

echo.
echo Xong. Kiem tra cua so "MT5 API 24/7" co dong: Running on http://127.0.0.1:5001
pause

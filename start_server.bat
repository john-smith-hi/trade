@echo off
cd /d "%~dp0"
REM =============================================================================
REM Chay API 24/7 tren Windows Server (khong pause, tu khoi dong lai neu crash).
REM
REM Tu dong (khi TRADE_SERVER=1):
REM   - Moi ~2 phut: git fetch; neu remote co commit moi → reset --hard + pull
REM     → copy_www.py → thoat api.py → vong loop bat nay chay lai.
REM   - Tat auto-update: set TRADE_AUTO_UPDATE=0
REM   - Doi chu ky: set TRADE_UPDATE_SEC=60
REM
REM Khong dung Flask-reloader (tranh timeout UI).
REM Sua accounts.xml / paths.xml → soft-reload, khong can restart.
REM
REM Task Scheduler: At log on, user dang ngoi may,
REM   "Run only when user is logged on" (MT5 can session desktop).
REM KHONG disconnect RDP bang cach dong cua so — session bi kill, terminal chet.
REM Dung tscon ve console hoac de session mo.
REM
REM Telegram: copy xml\telegram.example.xml -> xml\telegram.xml, dien token/chat_id,
REM   enabled=true. Cai app Telegram tren dien thoai (cung tai khoan / group).
REM =============================================================================
set TRADE_SERVER=1
echo Dang chay MT5 API 24/7 tai http://127.0.0.1:5001
echo Watcher Telegram + auto git pull/copy_www khi co code moi tren remote.
echo Ctrl+C de dung. Neu python thoat, se tu chay lai sau 5 giay.
echo.

:loop
python api.py
echo.
echo API da dung. Khoi dong lai sau 5 giay...
timeout /t 5 /nobreak
goto loop

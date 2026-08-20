@echo off
cd /d "%~dp0"
REM =============================================================================
REM Chay API 24/7 tren Windows Server (khong pause, tu khoi dong lai neu crash).
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
echo Watcher Timer + lenh -> Telegram. Tat auto-reload.
echo Ctrl+C de dung. Neu python thoat, se tu chay lai sau 5 giay.
echo.

:loop
python api.py
echo.
echo API da dung. Khoi dong lai sau 5 giay...
timeout /t 5 /nobreak
goto loop

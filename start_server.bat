@echo off
cd /d "%~dp0"
REM =============================================================================
REM Chay API 24/7 tren Windows Server (khong pause, tu khoi dong lai neu crash).
REM Sua file .py hoac .xml cau hinh → api.py thoat ma 3, vong lap chay lai ngay.
REM Khong dung Flask-reloader (tren Windows de 2 process cung cong → UI timeout).
REM Crash (ma thoat khac 3) → doi 5 giay roi chay lai.
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
echo Sua file .py hoac .xml cau hinh se tu nap lai. Ctrl+C de dung.
echo Neu python crash, se tu chay lai sau 5 giay.
echo.

:loop
python api.py
if errorlevel 4 goto crashed
if errorlevel 3 goto reload
goto crashed

:reload
echo.
echo Code thay doi. Khoi dong lai ngay.
goto loop

:crashed
echo.
echo API da dung. Khoi dong lai sau 5 giay...
timeout /t 5 /nobreak
goto loop

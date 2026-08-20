@echo off
cd /d "%~dp0"
echo Dang khoi dong MT5 API tai http://127.0.0.1:5001 ...
echo May dev: auto-reload khi sua .py / .xml. Watcher Timer+Telegram chay o process con.
echo Server 24/7: dung start_server.bat
python api.py
pause

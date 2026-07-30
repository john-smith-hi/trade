@echo off
cd /d "%~dp0"
echo Dang khoi dong MT5 API tai http://127.0.0.1:5001 ...
echo Auto-reload: sua .py hoac bat ky file .xml se restart API va nap lai noi dung.
python api.py
pause

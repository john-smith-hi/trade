@echo off
cd /d "%~dp0"
echo Dang khoi dong MT5 API tai http://127.0.0.1:5001 ...
echo Auto-reload: sua .py se restart API; sua xml\accounts.xml se nap lai o request tiep theo.
python api.py
pause

@echo on
setlocal
cd /d "%~dp0"
echo BAT_DIR=%~dp0
echo CWD=%CD%
set PYTHONIOENCODING=utf-8
call .venv310\Scripts\activate.bat
if exist "%LOCALAPPDATA%\HughesCompany\TCP\production.env" call "%LOCALAPPDATA%\HughesCompany\TCP\production.env"
python tcp_ts_v2.py

@echo on
setlocal
cd /d "%~dp0"
echo BAT_DIR=%~dp0
echo CWD=%CD%
call .venv310\Scripts\activate.bat
python tcp_ts.py

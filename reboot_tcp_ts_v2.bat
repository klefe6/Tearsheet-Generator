@echo on
setlocal
cd /d "%~dp0"
echo BAT_DIR=%~dp0
echo CWD=%CD%
echo TCP v2 PREVIEW ONLY - port 8312 - does not affect production TCP on 8302
REM Avoid UnicodeEncodeError on emoji/symbol logs when console is cp1252
set PYTHONIOENCODING=utf-8
call .venv310\Scripts\activate.bat
python tcp_ts_v2.py

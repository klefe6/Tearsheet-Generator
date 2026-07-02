@echo on
setlocal
cd /d "%~dp0"
echo BAT_DIR=%~dp0
echo CWD=%CD%
echo TCP v2 PREVIEW ONLY - port 8312 - does not affect production TCP on 8302
REM Avoid UnicodeEncodeError on emoji/symbol logs when console is cp1252
set PYTHONIOENCODING=utf-8
REM Set preview JSON mode after seeding: set TCP_V2_STATE_MODE=json_active
REM Required for admin writes: set TCP_V2_ADMIN_TOKEN=... and set TCP_V2_SESSION_SECRET=...
call .venv310\Scripts\activate.bat
python tcp_ts_v2.py

@echo off
cd /d "%~dp0Momentum Pacer"
if exist "%~dp0.local_dev.env" call "%~dp0.local_dev.env"
set MP_TS_PRODUCTION=1
"%~dp0.venv310\Scripts\python.exe" mp_ts.py

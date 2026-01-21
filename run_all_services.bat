@echo off
REM ----------------------------------------------------
REM run_all_services.bat
REM Launches the Python script no matter where this .bat lives.
REM ----------------------------------------------------

REM 1) Change into THIS folder (where the .bat lives)
cd /d "%~dp0"

REM 2) Kick off the Python launcher
REM    If python.exe isn’t on your PATH, replace 'python' with the full path.
python "%~dp0launch_all_services.py"

REM 3) Keep the window open so you see errors (if any)
pause

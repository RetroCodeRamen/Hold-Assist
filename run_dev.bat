@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    where python >nul 2>&1
    if errorlevel 1 (
        echo Install Python 3.10+ from https://www.python.org/downloads/
        echo Check "Add python.exe to PATH" — avoid Microsoft Store Python if possible.
        pause
        exit /b 1
    )
    python -m venv .venv
)

set PY=.venv\Scripts\python.exe
%PY% -m pip install -r requirements.txt -q
%PY% scripts\generate_assets.py

REM Microsoft Store Python in pyvenv.cfg causes heap crashes with the tray icon.
set TRAY_ARGS=
findstr /i /c:"WindowsApps" /c:"PythonSoftwareFoundation" .venv\pyvenv.cfg >nul 2>&1
if not errorlevel 1 (
    echo.
    echo *** Store Python venv detected — starting WITHOUT system tray ***
    echo *** To fix: powershell -ExecutionPolicy Bypass -File scripts\recreate_venv.ps1 ***
    echo.
    set TRAY_ARGS=--no-tray
)

%PY% main.py %TRAY_ARGS%

if errorlevel 1 (
    echo.
    echo Hold Assist exited with an error. Check hold_assist.log
    pause
)

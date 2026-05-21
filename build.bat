@echo off
REM Build HoldAssist-Setup.exe for deployment (run on BUILD PC only, not end users).
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
if errorlevel 1 pause

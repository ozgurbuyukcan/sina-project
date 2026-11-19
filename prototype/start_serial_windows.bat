@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run run_windows.bat to install dependencies.
  pause
  exit /b 1
)
set /p SERIAL_PORT=Enter Arduino COM port (example COM3):
if "%SERIAL_PORT%"=="" set "SERIAL_PORT=COM3"
set /p SOURCE_ID=Enter source identifier (example field-01):
if "%SOURCE_ID%"=="" set "SOURCE_ID=field-01"
".venv\Scripts\python.exe" live_gateway.py --mode serial --port "%SERIAL_PORT%" --baud 115200 --source "%SOURCE_ID%"
pause

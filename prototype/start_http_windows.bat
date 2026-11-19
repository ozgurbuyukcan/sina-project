@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run run_windows.bat to install dependencies.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" launch_local_http.py
pause

@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Once run run_windows.bat to set up Python packages, then close the app window.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip show pytest >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install "pytest>=7,<10"
  if errorlevel 1 (
    echo pytest installation failed.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pytest -q
set CODE=%ERRORLEVEL%
if not "%CODE%"=="0" echo Some tests failed. Please copy the visible error output.
pause
exit /b %CODE%

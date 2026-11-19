@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run run_windows.bat to install Python in .venv.
  pause
  exit /b 1
)
echo Stop all old and new SINA processes before copying SQLite databases.
set /p OLD_DIR=Paste full path of the old SINA_FRESH_0_2 folder: 
if "%OLD_DIR%"=="" (
  echo No old folder entered. No files changed.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" migrate_from_02.py --from-dir "%OLD_DIR%"
if errorlevel 1 echo Migration stopped without replacing any existing target databases.
pause

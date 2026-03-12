@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] python not found in PATH.
  exit /b 1
)

echo Running my_ticket_bot with CRNN model...
python rb\my_ticket_bot.py

if errorlevel 1 (
  echo [ERROR] bot exited with error.
  exit /b 1
)

echo Done.
exit /b 0

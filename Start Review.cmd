@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-review.ps1"
if errorlevel 1 (
  echo.
  echo Review interface stopped with an error. Press any key to close.
  pause >nul
  exit /b 1
)

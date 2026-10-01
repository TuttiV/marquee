@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run "Run Syncplay.bat" once first so the setup can finish.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" syncplayClient.py %*
pause

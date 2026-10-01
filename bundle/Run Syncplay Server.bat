@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run "Run Syncplay.bat" once first so the setup can finish.
  pause
  exit /b 1
)
echo Starting a Syncplay server on port 8999. Share your IP address and this port with friends.
".venv\Scripts\python.exe" syncplayServer.py --port 8999 %*
pause

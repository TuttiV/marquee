@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" goto :launch

set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo Python 3.9 or newer is required. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run this again.
  pause
  exit /b 1
)
echo First run: setting things up, this takes a minute. This window closes when it's done...
%PY% -m venv .venv || goto :fail
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt PySide6 pywin32 || goto :fail

:launch
rem Start with pythonw (no console window) and close this window straight away
start "" ".venv\Scripts\pythonw.exe" "%~dp0program\launch-syncplay.pyw" %*
exit /b 0

:fail
echo Setup failed - check your internet connection and try again.
rmdir /s /q .venv 2>nul
pause
exit /b 1

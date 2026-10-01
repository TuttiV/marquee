@echo off
rem One-time setup used by Syncplay.exe on its first run: creates a private Python environment next to it.
setlocal
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo Python 3.9 or newer is required. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then open Syncplay Marquee.exe again.
  pause
  exit /b 1
)
echo Setting up Syncplay for the first time. This takes a minute and this window closes when it is done...
%PY% -m venv .venv || goto :fail
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt PySide6 pywin32 || goto :fail
exit /b 0
:fail
echo.
echo Setup failed - check your internet connection and open Syncplay Marquee.exe to try again.
rmdir /s /q .venv 2>nul
pause
exit /b 1

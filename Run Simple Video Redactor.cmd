@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo Please install Python 3.11 or newer from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist ".venv\ready" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    pause
    exit /b 1
  )
  type nul > ".venv\ready"
)
".venv\Scripts\pythonw.exe" simple_video_redactor.py

@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo Creating virtual environment...
  where python >nul 2>nul
  if errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto :error
)

if not exist ".venv\.installed" (
  echo Installing dependencies...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  type nul > ".venv\.installed"
)

"%VENV_PY%" scripts\download_model.py
if errorlevel 1 goto :error

"%VENV_PY%" app.py
if errorlevel 1 goto :error

goto :eof

:error
echo.
echo MiniCPM5-Librarian failed to start.
pause
exit /b 1

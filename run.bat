@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "STARTED_SERVER=0"

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

rem Load settings saved by the Settings dialog into this shell.
set "ENV_SCRIPT=.llama-env.cmd"
"%VENV_PY%" -c "import os; from dotenv import load_dotenv; load_dotenv(); keys=[('LLM_MODEL','MiniCPM5-2B'),('N_CTX','6144'),('N_BATCH','512'),('N_THREADS',''),('N_GPU_LAYERS','0'),('LLAMA_SERVER_HOST','127.0.0.1'),('LLAMA_SERVER_PORT','5001')]; f=open('.llama-env.cmd','w',encoding='utf-8'); [f.write(f'set {k}={os.getenv(k,d)}\n') for k,d in keys]; f.close()"
if errorlevel 1 goto :error
call "%ENV_SCRIPT%"
del "%ENV_SCRIPT%" >nul 2>nul

if defined N_THREADS goto :threads_ready
set /a N_THREADS=%NUMBER_OF_PROCESSORS%/2
if %N_THREADS% LSS 1 set "N_THREADS=1"
:threads_ready

"%VENV_PY%" download_and_check_model.py
if errorlevel 1 goto :error

for /f "usebackq delims=" %%M in (`"%VENV_PY%" -c "from download_and_check_model import model_path; print(model_path())"`) do set "MODEL_PATH=%%M"

set "LLAMA_BIN="
if defined LLAMA_SERVER_BIN if exist "%LLAMA_SERVER_BIN%" set "LLAMA_BIN=%LLAMA_SERVER_BIN%"
if defined LLAMA_BIN goto :llama_found

for /f "delims=" %%L in ('where llama 2^>nul') do set "LLAMA_BIN=%%L"
if defined LLAMA_BIN goto :llama_found
if exist "%USERPROFILE%\.local\bin\llama.exe" (
  set "LLAMA_BIN=%USERPROFILE%\.local\bin\llama.exe"
  goto :llama_found
)
if exist "%USERPROFILE%\.llama-app\llama.exe" (
  set "LLAMA_BIN=%USERPROFILE%\.llama-app\llama.exe"
  goto :llama_found
)

echo llama.cpp was not found; installing it with the official installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://llama.app/install.ps1 | iex"
if errorlevel 1 goto :error
if exist "%USERPROFILE%\.local\bin\llama.exe" set "LLAMA_BIN=%USERPROFILE%\.local\bin\llama.exe"
if not defined LLAMA_BIN goto :error

:llama_found
where curl.exe >nul 2>nul
if errorlevel 1 (
  echo curl.exe is required to check the llama.cpp server.
  goto :error
)

curl.exe -fsS "http://%LLAMA_SERVER_HOST%:%LLAMA_SERVER_PORT%/health" >nul 2>nul
if not errorlevel 1 (
  echo Using the llama.cpp server already running at http://%LLAMA_SERVER_HOST%:%LLAMA_SERVER_PORT%
  goto :server_ready
)

echo Starting llama.cpp server in a new window...
set "SERVER_ARGS=-m ""%MODEL_PATH%"" --alias ""%LLM_MODEL%"" --host %LLAMA_SERVER_HOST% --port %LLAMA_SERVER_PORT% --ctx-size %N_CTX% --batch-size %N_BATCH% --threads %N_THREADS% --gpu-layers %N_GPU_LAYERS% --jinja --no-webui"
for %%B in ("%LLAMA_BIN%") do set "LLAMA_NAME=%%~nxB"
if /i "%LLAMA_NAME%"=="llama-server.exe" (
  start "llama.cpp server" "%LLAMA_BIN%" %SERVER_ARGS%
) else (
  start "llama.cpp server" "%LLAMA_BIN%" serve %SERVER_ARGS%
)
set "STARTED_SERVER=1"

echo Waiting for llama.cpp at http://%LLAMA_SERVER_HOST%:%LLAMA_SERVER_PORT%...
set /a WAIT=0
:wait_server
curl.exe -fsS "http://%LLAMA_SERVER_HOST%:%LLAMA_SERVER_PORT%/health" >nul 2>nul
if not errorlevel 1 goto :server_ready
set /a WAIT+=1
if %WAIT% GEQ 180 goto :server_failed
timeout /t 1 /nobreak >nul
goto :wait_server

:server_failed
echo llama.cpp server failed to start. Check the llama.cpp window for details.
goto :error

:server_ready
echo llama.cpp ready at http://%LLAMA_SERVER_HOST%:%LLAMA_SERVER_PORT%
"%VENV_PY%" app.py
if errorlevel 1 goto :error
goto :done

:error
echo.
echo Study-Notes-Librarian failed to start.
if "%STARTED_SERVER%"=="1" taskkill /FI "WINDOWTITLE eq llama.cpp server" /T /F >nul 2>nul
pause
exit /b 1

:done
if "%STARTED_SERVER%"=="1" (
  echo Stopping llama.cpp server...
  taskkill /FI "WINDOWTITLE eq llama.cpp server" /T /F >nul 2>nul
)
goto :eof

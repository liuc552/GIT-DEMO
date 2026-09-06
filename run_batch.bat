@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "RUNTIME=%CD%\.runtime"
set "HF_HOME=%RUNTIME%\hf"
set "PLAYWRIGHT_BROWSERS_PATH=%RUNTIME%\ms-playwright"
set "PIP_CACHE_DIR=%RUNTIME%\pip-cache"
set "TMP=%RUNTIME%\tmp"
set "TEMP=%RUNTIME%\tmp"

if not exist "%RUNTIME%" mkdir "%RUNTIME%"
if not exist "%TMP%" mkdir "%TMP%"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.10+ not found in PATH.
  pause
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git not found in PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [SETUP] Creating local Python environment...
  python -m venv .venv
  if errorlevel 1 goto :fail
)

set "PY=.venv\Scripts\python.exe"

echo [SETUP] Checking Python dependencies...
"%PY%" -m pip install --disable-pip-version-check -q -r local_batch\requirements.txt
if errorlevel 1 goto :fail

if not exist "%PLAYWRIGHT_BROWSERS_PATH%\chromium-*" (
  echo [SETUP] Installing Playwright Chromium into this folder...
  "%PY%" -m playwright install chromium
  if errorlevel 1 goto :fail
)

if not exist "urls.txt" (
  echo # One public video URL per line> urls.txt
  echo.
  echo Created urls.txt. Paste Douyin/Bilibili/YouTube links into it, one per line, then run this file again.
  start "" notepad.exe urls.txt
  pause
  exit /b 0
)

echo.
echo [RUN] Batch transcription started. Existing successful items will be skipped.
echo [RUN] Model: small
echo [RUN] Output: %CD%\results
echo.
"%PY%" local_batch\batch_worker.py --urls urls.txt --model small --output-dir results --runtime-dir .runtime
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo [DONE] Batch finished. Open results folder for TXT / MD / JSONL.
  if exist "results" start "" explorer.exe "%CD%\results"
) else (
  echo [DONE WITH ERRORS] Check results\_batch_state.json for per-link errors.
)
pause
exit /b %RC%

:fail
echo.
echo [ERROR] Setup failed. Nothing in your private code or Northstar was touched.
pause
exit /b 1

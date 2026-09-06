@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "TARGET=D:\VideoTranscript"
set "REPO=https://github.com/liuc552/GIT-DEMO.git"

if not exist "D:\" (
  echo [ERROR] D drive not found.
  pause
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git for Windows is required.
  pause
  exit /b 1
)

if exist "%TARGET%\.git" (
  echo [UPDATE] %TARGET% already exists. Updating...
  git -C "%TARGET%" pull --ff-only
  if errorlevel 1 goto :fail
) else (
  if exist "%TARGET%" (
    echo [ERROR] %TARGET% exists but is not this Git repository.
    echo Rename or remove that folder, then run again.
    pause
    exit /b 1
  )
  echo [INSTALL] Cloning to %TARGET% ...
  git clone "%REPO%" "%TARGET%"
  if errorlevel 1 goto :fail
)

echo.
echo [OK] Installed on D drive:
echo      %TARGET%
echo.
echo Runtime/model/browser/cache/temp/output will stay under this D-drive folder.
echo Starting batch worker...
call "%TARGET%\run_batch.bat"
exit /b %ERRORLEVEL%

:fail
echo.
echo [ERROR] D-drive installation/update failed.
pause
exit /b 1

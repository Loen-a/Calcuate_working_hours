@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\start-workhours.ps1"
set "WORKHOURS_EXIT=%ERRORLEVEL%"

if not "%WORKHOURS_EXIT%"=="0" (
    echo.
    echo Workhours failed to start. Review the error above.
    pause
)

exit /b %WORKHOURS_EXIT%

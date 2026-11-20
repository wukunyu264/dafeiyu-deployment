@echo off
REM Backup AstrBot\data to Desktop as a zip.
REM Stop AstrBot first for a consistent SQLite copy (recommended).
setlocal
set "SRC=%~dp0AstrBot\data"
if not exist "%SRC%" (
    echo [ERROR] %SRC% not found.
    pause
    exit /b 1
)
set "OUT=%USERPROFILE%\Desktop\dafeiyu-data-backup.zip"
echo Backing up:
echo   from  %SRC%
echo   to    %OUT%
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -LiteralPath $env:SRC -DestinationPath $env:OUT -CompressionLevel Optimal -Force"
if errorlevel 1 (
    echo [ERROR] backup failed.
) else (
    echo [OK] backup done.
)
pause
endlocal
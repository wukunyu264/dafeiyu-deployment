@echo off
REM Close QQ gracefully, then start NapCat again.
REM Do NOT force-kill QQ: it leaves NapCat injection patches unreverted and QQ
REM will report "files corrupted" on the next launch.
setlocal
taskkill /im QQ.exe >nul 2>&1
if errorlevel 1 (
    echo QQ is not running.
) else (
    echo Closing QQ gracefully, waiting 8s...
    timeout /t 8 >nul
)
tasklist /fi "imagename eq QQ.exe" | find /i "QQ.exe" >nul
if not errorlevel 1 (
    echo [WARN] QQ is still running. Please quit it from the tray icon,
    echo        then run start-napcat.bat. Force-kill is intentionally skipped.
    pause
    exit /b 1
)
call "%~dp0start-napcat.bat" %1
endlocal
@echo off
REM Start NapCat. Usage: start-napcat.bat [QQ_NUMBER]
REM If the QQ number is omitted, NapCat shows a QR code to log in.
setlocal
cd /d "%~dp0NapCat"
if not exist "launcher.bat" (
    echo [ERROR] launcher.bat not found in %CD%
    pause
    exit /b 1
)
if "%~1"=="" (
    echo No QQ number given, NapCat will show a QR code.
    call launcher.bat
) else (
    echo Quick-login as %~1
    call launcher.bat %~1
)
endlocal
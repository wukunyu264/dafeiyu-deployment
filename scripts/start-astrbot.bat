@echo off
REM Start AstrBot. Put this .bat in the deploy root (same level as AstrBot\ and NapCat\).
setlocal
cd /d "%~dp0AstrBot"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run: python -m venv .venv  then install requirements.
    pause
    exit /b 1
)
start "AstrBot" ".venv\Scripts\python.exe" main.py
echo AstrBot starting... wait 40s, then open http://127.0.0.1:6185
timeout /t 5 >nul
endlocal
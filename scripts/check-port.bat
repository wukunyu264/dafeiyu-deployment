@echo off
REM Health check: ports, ffmpeg, python venv.
setlocal
echo ===== ports =====
netstat -ano | findstr ":6185"
netstat -ano | findstr ":6199"
echo.
echo ===== ffmpeg =====
ffmpeg -version 2>nul | findstr /i "ffmpeg version"
if errorlevel 1 echo [WARN] ffmpeg not found in PATH - voice messages will fail to send
echo.
echo ===== python =====
"%~dp0AstrBot\.venv\Scripts\python.exe" -V 2>nul
if errorlevel 1 echo [WARN] venv not found
echo.
pause
endlocal
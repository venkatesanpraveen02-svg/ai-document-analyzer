@echo off
title AI Document Analyzer
echo ====================================================
echo   AI Document Analyzer  --  Starting...
echo ====================================================
echo.

:: Activate venv
call .\venv310\Scripts\activate.bat 2>nul
if errorlevel 1 (
    echo [ERROR] Could not activate venv310. Check it exists at .\venv310\
    pause & exit /b 1
)

:: Launch via Python -- auto-picks a free port
python start.py

pause

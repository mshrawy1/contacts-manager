@echo off
REM Contacts Manager - run the test suite
cd /d "%~dp0"
chcp 65001 >nul
python tests\run_all.py
echo.
pause

@echo off
REM Contacts Manager - launcher
cd /d "%~dp0"
where pythonw >/dev/null 2>&1
if errorlevel 1 goto nopython
start "" pythonw "%~dp0main.py"
exit /b 0

:nopython
echo.
echo Python was not found on this computer.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo During setup, tick the box "Add python.exe to PATH".
echo.
pause
exit /b 1

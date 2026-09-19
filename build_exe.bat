@echo off
REM Contacts Manager - build a single portable .exe
cd /d "%~dp0"
chcp 65001 >nul
echo Building ContactsManager.exe ...
echo.
python -m PyInstaller ContactsManager.spec --noconfirm --clean
if errorlevel 1 goto failed
echo.
echo Done. The program is in the dist folder, named with its version.
echo It is self-contained - copy that one file anywhere.
echo.
pause
exit /b 0

:failed
echo.
echo Build failed. Read the messages above.
echo If PyInstaller is missing, run:  python -m pip install pyinstaller
echo.
pause
exit /b 1

@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   ZapretDeskop - Build
echo ========================================
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

echo [1/4] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller --quiet

echo.
echo [2/4] Cleaning previous build...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo.
echo [3/4] Building with PyInstaller...
pyinstaller --noconfirm --onefile --windowed --name ZapretDeskop --icon "icon.ico" --hidden-import pywinstyles --hidden-import PyQt6.QtSvg --noupx ZapretDeskop.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Copying winws folder to dist...
if exist "winws" (
    xcopy /E /I /Y "winws" "dist\winws" >nul
    echo winws folder copied.
) else (
    echo winws folder not found - skipped.
)

echo.
echo ========================================
echo   Build completed successfully!
echo   Output: dist\ZapretDeskop.exe
echo ========================================
echo.
pause

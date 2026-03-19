@echo off
title Wolfy's Media Downloader - Build Script
echo.
echo  ^>^> Building Wolfy's Media Downloader V2.0...
echo.

REM Check uv is available
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] uv not found. Install it from https://docs.astral.sh/uv/
    pause
    exit /b 1
)

REM Install pyinstaller into the project venv if not present
echo  ^>^> Checking PyInstaller...
uv pip install pyinstaller --quiet

REM Clean previous build
if exist dist\WolfysMediaDownloader.exe (
    echo  ^>^> Removing old build...
    del /f /q dist\WolfysMediaDownloader.exe
)

REM Build via python -m PyInstaller to avoid AppControl blocking the binary
echo  ^>^> Running PyInstaller...
uv run python -m PyInstaller WolfysMediaDownloader.spec --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo  ^>^> Build complete!
echo  ^>^> Executable: dist\WolfysMediaDownloader.exe
echo.
pause
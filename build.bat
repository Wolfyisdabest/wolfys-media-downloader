@echo off
title Wolfy's Media Downloader - Build Script
echo.
echo  ^>^> Building Wolfy's Media Downloader V2.0...
echo.

tasklist /FI "IMAGENAME eq WolfysMediaDownloader.exe" 2>NUL | find /I "WolfysMediaDownloader.exe" >NUL
if %errorlevel% equ 0 (
    echo [ERROR] WolfysMediaDownloader.exe is currently running.
    echo [ERROR] Close the app before building so dist files are not locked.
    pause
    exit /b 1
)
tasklist /FI "IMAGENAME eq WolfysMediaDownloader-standalone.exe" 2>NUL | find /I "WolfysMediaDownloader-standalone.exe" >NUL
if %errorlevel% equ 0 (
    echo [ERROR] WolfysMediaDownloader-standalone.exe is currently running.
    echo [ERROR] Close the app before building so dist files are not locked.
    pause
    exit /b 1
)

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

REM Download portable ffmpeg binaries into tools\ if missing.
REM These are bundled into the dist folder, so users do not need to install ffmpeg.
if not exist tools\ffmpeg.exe (
    echo  ^>^> Downloading portable FFmpeg...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop';" ^
        "$url='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip';" ^
        "$zip=Join-Path $env:TEMP 'wmd-ffmpeg.zip';" ^
        "$tmp=Join-Path $env:TEMP ('wmd-ffmpeg-' + [guid]::NewGuid());" ^
        "New-Item -ItemType Directory -Force -Path 'tools' | Out-Null;" ^
        "Invoke-WebRequest -Uri $url -OutFile $zip;" ^
        "Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force;" ^
        "$bin=Get-ChildItem -Path $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1 -ExpandProperty DirectoryName;" ^
        "Copy-Item -LiteralPath (Join-Path $bin 'ffmpeg.exe') -Destination 'tools\ffmpeg.exe' -Force;" ^
        "Copy-Item -LiteralPath (Join-Path $bin 'ffprobe.exe') -Destination 'tools\ffprobe.exe' -Force;" ^
        "Remove-Item -LiteralPath $zip -Force;" ^
        "Remove-Item -LiteralPath $tmp -Recurse -Force;"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to download portable FFmpeg.
        echo [ERROR] You can manually place ffmpeg.exe and ffprobe.exe in the tools folder.
        pause
        exit /b 1
    )
)

REM Clean previous build
if exist dist\WolfysMediaDownloader.exe (
    echo  ^>^> Removing old build...
    del /f /q dist\WolfysMediaDownloader.exe
)
if exist dist\WolfysMediaDownloader (
    echo  ^>^> Removing old build folder...
    rmdir /s /q dist\WolfysMediaDownloader
)
if exist dist\WolfysMediaDownloader-standalone.exe (
    echo  ^>^> Removing old standalone exe...
    del /f /q dist\WolfysMediaDownloader-standalone.exe
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

REM Create portable release archive for GitHub Releases.
REM The updater intentionally only selects portable .zip assets.
for /f "usebackq delims=" %%v in (`uv run python -c "from core.version import APP_VERSION; print(APP_VERSION)"`) do set APP_VERSION=%%v
set PORTABLE_ZIP=dist\WolfysMediaDownloader-portable-v%APP_VERSION%.zip
set RELEASE_STAGE=dist\release_stage
if exist "%PORTABLE_ZIP%" del /f /q "%PORTABLE_ZIP%"
if exist "%RELEASE_STAGE%" rmdir /s /q "%RELEASE_STAGE%"
echo  ^>^> Creating portable release archive...
robocopy dist\WolfysMediaDownloader "%RELEASE_STAGE%\WolfysMediaDownloader" /E /XD Data >nul
if %errorlevel% geq 8 (
    echo.
    echo [ERROR] Failed to stage portable archive.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -LiteralPath '%RELEASE_STAGE%\WolfysMediaDownloader' -DestinationPath '%PORTABLE_ZIP%' -Force"
if exist "%RELEASE_STAGE%" rmdir /s /q "%RELEASE_STAGE%"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Portable archive creation failed.
    pause
    exit /b 1
)

echo.
echo  ^>^> Build complete!
echo  ^>^> Executable: dist\WolfysMediaDownloader\WolfysMediaDownloader.exe
echo  ^>^> Standalone exe: dist\WolfysMediaDownloader-standalone.exe
echo  ^>^> Portable zip: %PORTABLE_ZIP%
echo.
pause

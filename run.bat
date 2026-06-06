@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" /min "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
    exit /b 0
)

where uv >nul 2>&1
if %errorlevel% equ 0 (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath 'uv' -ArgumentList @('run','pythonw','main.py') -WorkingDirectory '%~dp0'"
    exit /b 0
)

echo Python virtual environment not found. Run build.bat or install dependencies first.
pause
exit /b 1

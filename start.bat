@echo off
setlocal
cd /d "%~dp0"

REM Prefer a regular Python installation, but avoid the Windows Store alias.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 server.py
    exit /b %errorlevel%
)

REM Codex's bundled Python is available in this workspace environment.
set "CODEX_PYTHON=%LOCALAPPDATA%\..\..\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PYTHON%" (
    "%CODEX_PYTHON%" server.py
    exit /b %errorlevel%
)

REM Fall back to a standard python.exe on PATH, if one is installed.
where python >nul 2>nul
if not errorlevel 1 (
    python server.py
    exit /b %errorlevel%
)

echo Python 3.9 or newer is required. Install Python and run this file again.
pause
exit /b 1

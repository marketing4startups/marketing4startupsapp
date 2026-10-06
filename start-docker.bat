@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo Docker Desktop is required. Install and start Docker Desktop, then run this again.
    pause
    exit /b 1
)

if not exist .env (
    copy .env.example .env >nul
    echo Created .env from .env.example.
    echo Edit .env and set separate random passwords for PostgreSQL and pgAdmin.
    echo Then run start-docker.bat again.
    pause
    exit /b 1
)

docker compose up --build


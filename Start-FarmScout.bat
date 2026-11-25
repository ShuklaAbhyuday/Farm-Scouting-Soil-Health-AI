@echo off
title FarmScout AI - Local Launcher
cd /d "%~dp0"

echo Starting FastAPI Backend (port 8000)...
start "FarmScout Backend" cmd /k "set PYTHONPATH=%~dp0 && .venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend"

echo Starting Vite Frontend (port 5173)...
start "FarmScout Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 4 /nobreak >nul
start http://localhost:5173
echo.
echo App opened at http://localhost:5173
pause

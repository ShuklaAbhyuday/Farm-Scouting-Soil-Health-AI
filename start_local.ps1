# One-click local launcher for EPICS Farm Scouting AI System
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Virtual environment .venv not found. Using system python..." -ForegroundColor Yellow
    $PythonExe = "python"
}

Write-Host "Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; `$env:PYTHONPATH='$Root'; & '$PythonExe' -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend"

Write-Host "Starting Vite frontend on http://localhost:5173 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; npm run dev"

Write-Host ""
Write-Host "Local servers launching:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://localhost:8000/docs"

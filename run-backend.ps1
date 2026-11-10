# ResolveGrid AI - Backend Runner Script (PowerShell)
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  ResolveGrid AI - Autonomous Incident Resolution Platform " -ForegroundColor Cyan
Write-Host "  Starting FastAPI Backend on http://127.0.0.1:8000       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VENV_PYTHON = ".\backend\.venv\Scripts\python.exe"
$VENV_UVICORN = ".\backend\.venv\Scripts\uvicorn.exe"

if (-not (Test-Path $VENV_UVICORN)) {
    Write-Host "Virtual environment not detected. Creating and installing..." -ForegroundColor Yellow
    python -m venv backend\.venv
    & $VENV_PYTHON -m pip install -r backend\requirements.txt
}

# Run database migrations and seed data
Write-Host "Ensuring database is up to date..." -ForegroundColor Green
& $VENV_PYTHON -m backend.app.seeds.seed_data

Write-Host "Launching Uvicorn server..." -ForegroundColor Green
& $VENV_UVICORN backend.app.main:app --host 127.0.0.1 --port 8000 --reload


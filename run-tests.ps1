# ResolveGrid AI - Test Suite Runner (PowerShell)
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  ResolveGrid AI - Executing Complete Verification Suite  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VENV_PYTEST = ".\backend\.venv\Scripts\pytest.exe"

Write-Host "Running Pytest across services, API, and agent workflows..." -ForegroundColor Green
& $VENV_PYTEST -v


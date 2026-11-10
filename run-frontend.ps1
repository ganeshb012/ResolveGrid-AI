# ResolveGrid AI - Frontend Runner Script (PowerShell)
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  ResolveGrid AI - Four Integrated Portal Frontend        " -ForegroundColor Cyan
Write-Host "  Starting Vite Dev Server on http://localhost:5173       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Set-Location -Path "frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
    npm install
}

npm run dev


# DSA Coach - One-click startup script for Windows
# Save this file as start.ps1 in your project folder
# Run: .\start.ps1

$PROJECT = "C:\ME\MY\PROJECTS\dsa-coach-backend-ollama"

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "  DSA Coach - Starting up..." -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# 1. Celery Worker (solo pool - fixes Windows PermissionError)
Write-Host "[1/3] Starting Celery Worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PROJECT'; .venv\Scripts\activate; Write-Host 'CELERY WORKER' -ForegroundColor Yellow; celery -A app.workers.celery_app worker --loglevel=info --pool=solo"

Start-Sleep -Seconds 2

# 2. Celery Beat (6 PM daily scheduler)
Write-Host "[2/3] Starting Celery Beat..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PROJECT'; .venv\Scripts\activate; Write-Host 'CELERY BEAT' -ForegroundColor Magenta; celery -A app.workers.celery_app beat --loglevel=info"

Start-Sleep -Seconds 2

# 3. FastAPI backend (runs in this window)
Write-Host "[3/3] Starting FastAPI..." -ForegroundColor Yellow
Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "  All services launched!" -ForegroundColor Green
Write-Host "  API  -> http://localhost:8000" -ForegroundColor Green
Write-Host "  Docs -> http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  UI   -> open dsa-coach-ui.html in browser" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""

cd $PROJECT
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
vate
uvicorn app.main:app --reload --port 8000

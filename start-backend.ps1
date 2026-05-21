# Script untuk menjalankan backend Carter Island
# Jalankan dari root project: .\start-backend.ps1
#
# Kenapa pakai python main.py bukan uvicorn --reload?
# - uvicorn --reload mencegat Ctrl+C sebelum sampai ke Python
# - python main.py memberi kontrol penuh ke signal handler kita
# - Ctrl+C akan berhenti dalam maks 8 detik

Set-Location "$PSScriptRoot\src\backend"
Write-Host "Starting Carter Island Backend..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop (will force-exit in 8s if stuck)" -ForegroundColor Yellow
python main.py

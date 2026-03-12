$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python not found in PATH."
}

Write-Host "Running my_ticket_bot with CRNN model..."
python .\rb\my_ticket_bot.py

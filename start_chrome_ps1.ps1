# A 模式用：關閉所有 Chrome 後，以 --remote-debugging-port=9333 開啟
# 用法：PowerShell 執行 Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; .\start_chrome_ps1.ps1
# 或：powershell -ExecutionPolicy Bypass -File start_chrome_ps1.ps1

$port = 9333
$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$chrome = $null
foreach ($p in $chromePaths) {
    if (Test-Path $p) { $chrome = $p; break }
}
if (-not $chrome) {
    Write-Host "找不到 Chrome。請手動指定路徑並加上 --remote-debugging-port=$port"
    exit 1
}

Write-Host "========================================"
Write-Host "  關閉所有 Chrome，再以 port $port 開啟"
Write-Host "========================================"
Get-Process -Name chrome -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "已關閉既有 Chrome（若有的話）。等待 3 秒..."
Start-Sleep -Seconds 3

Write-Host "正在啟動 Chrome (port $port)..."
Start-Process -FilePath $chrome -ArgumentList "--remote-debugging-port=$port"
Write-Host "請執行: python rb\generic_ticket_bot.py"
Write-Host "========================================"

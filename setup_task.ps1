# =========================================================================
# Windows Task Scheduler Registration Script for ETF 00997A Daily Scraper
# =========================================================================
#
# Instructions:
# 1. Open PowerShell as Administrator
# 2. Navigate to this workspace folder
# 3. Execute: .\setup_task.ps1
#

$scriptPath = Join-Path (Get-Location) "backend\daily_scrape.py"
$pythonPath = (Get-Command python.exe -ErrorAction SilentlyContinue).Source

if (-not $pythonPath) {
    Write-Host "[ERROR] Python is not found in your system PATH. Please make sure Python is installed and added to PATH." -ForegroundColor Red
    Exit
}

Write-Host "Configuring scheduled task..." -ForegroundColor Cyan
Write-Host "Python Path: $pythonPath" -ForegroundColor DarkGray
Write-Host "Scraper Script: $scriptPath" -ForegroundColor DarkGray

# Setup task elements
# Argument includes quotes to handle potential spaces in the directory path
$Action = New-ScheduledTaskAction -Execute "$pythonPath" -Argument "`"$scriptPath`""
$Trigger = New-ScheduledTaskTrigger -Daily -At 18:30
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register task
try {
    Register-ScheduledTask -TaskName "ETFTracker_Scrape" `
                           -Action $Action `
                           -Trigger $Trigger `
                           -Settings $Settings `
                           -Description "Automatically crawls 00997A ETF NAV and holdings daily at 6:30 PM." `
                           -Force | Out-Null
                           
    Write-Host "`n[SUCCESS] Windows Scheduled Task 'ETFTracker_Scrape' registered successfully!" -ForegroundColor Green
    Write-Host "The scraper will run automatically every day at 18:30 (6:30 PM)." -ForegroundColor Green
    Write-Host "You can inspect it in Windows 'Task Scheduler' (工作排程器)." -ForegroundColor Green
} catch {
    Write-Host "`n[ERROR] Failed to register task: $_" -ForegroundColor Red
    Write-Host "Please make sure you are running PowerShell as Administrator!" -ForegroundColor Yellow
}

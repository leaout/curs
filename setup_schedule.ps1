# 创建 Windows 定时任务，每天自动导入 GitHub Actions 采集数据
# 以管理员身份运行

$taskName = "CursDailyImport"
$scriptPath = Join-Path $PSScriptRoot "daily_import.bat"

# 使用 schtasks 创建交互式任务（使用当前用户的 SSH 凭据）
$cmd = "schtasks /create /tn `"$taskName`" /tr `"cmd.exe /c $scriptPath`" /sc daily /st 21:00 /f /ru $env:USERNAME /it"
Invoke-Expression $cmd

Write-Host "Scheduled task created: $taskName (runs daily at 21:00)"
Write-Host "Test run: schtasks /run /tn $taskName"

# 可选：立即执行一次测试
$run = Read-Host "Run now? (y/n)"
if ($run -eq "y") {
    schtasks /run /tn $taskName
    Write-Host "Triggered. Check result with: schtasks /query /tn $taskName /v"
}

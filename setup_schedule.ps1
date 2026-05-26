# 创建 Windows 定时任务，每天自动导入 GitHub Actions 采集数据
$taskName = "Curs每日数据导入"
$scriptPath = Join-Path $PSScriptRoot "daily_import.bat"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At 9pm
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "定时任务已创建: $taskName (每天 21:00 执行)"
Write-Host "手动运行: Start-ScheduledTask -TaskName '$taskName'"

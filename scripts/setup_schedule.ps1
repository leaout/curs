# Run as administrator. Only CursBoot and CursPreMarket are changed.
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path $PSScriptRoot -Parent
$powershellPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + "$PSScriptRoot\start_curs.ps1" + '"'
$backupPath = Join-Path $projectPath ('logs\task-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
# SYSTEM needs no interactive login or stored account password. The app remains signal-only.
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
foreach ($name in @('CursBoot', 'CursPreMarket')) {
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction Stop
    Export-ScheduledTask -TaskName $name | Out-File -LiteralPath (Join-Path $backupPath "$name.xml") -Encoding Unicode
    $taskArguments = $arguments
    if ($name -eq 'CursPreMarket') { $taskArguments += ' -Restart' }
    $action = New-ScheduledTaskAction -Execute $powershellPath -Argument $taskArguments -WorkingDirectory $projectPath
    if ($name -eq 'CursBoot') {
        $triggers = @(New-ScheduledTaskTrigger -AtStartup)
        $triggers[0].Delay = 'PT90S'
    } else {
        $triggers = $existing.Triggers
    }
    Set-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Principal $principal -Settings $settings | Out-Null
}
Write-Output "Unattended boot/premarket startup configured. Backup: $backupPath. After-market/import tasks unchanged."

$ErrorActionPreference = 'Stop'
$projectPath = Split-Path $PSScriptRoot -Parent
$logPath = Join-Path $projectPath 'logs'
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$process = Start-Process -FilePath "$projectPath\.venv\Scripts\python.exe" -ArgumentList '-m', 'curs.collection.public_limit_up' -WorkingDirectory $projectPath -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput "$logPath\limit_up_collection.stdout.log" -RedirectStandardError "$logPath\limit_up_collection.stderr.log"
exit $process.ExitCode

param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path $PSScriptRoot -Parent
$logPath = Join-Path $projectPath 'logs'
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$mutexSecurity = New-Object System.Security.AccessControl.MutexSecurity
foreach ($sid in @('S-1-5-18', 'S-1-5-32-544')) {
    $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object System.Security.AccessControl.MutexAccessRule($identity, 'FullControl', 'Allow')
    $mutexSecurity.AddAccessRule($rule)
}
$createdNew = $false
# Global scope prevents a logged-in admin and session-0 startup from racing.
$startupLock = New-Object System.Threading.Mutex($false, 'Global\CursSignalStartup', [ref]$createdNew, $mutexSecurity)
if (-not $startupLock.WaitOne(0)) { $startupLock.Dispose(); exit 0 }
try {
    Add-Content -LiteralPath (Join-Path $logPath 'startup.log') -Value ("{0:o} identity={1} restart={2}" -f (Get-Date), [System.Security.Principal.WindowsIdentity]::GetCurrent().Name, $Restart)
    $processes = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
    $launchers = @($processes | Where-Object {
        $_.ExecutablePath -eq "$projectPath\.venv\Scripts\python.exe" -and
        $_.CommandLine -match '\brun\.py\b' -and $_.CommandLine -notmatch '--import-data'
    })
    if ($Restart) {
        foreach ($launcher in $launchers) {
            $processes | Where-Object { $_.ParentProcessId -eq $launcher.ProcessId -and $_.CommandLine -match '\brun\.py\b' } |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            Stop-Process -Id $launcher.ProcessId -Force -ErrorAction SilentlyContinue
        }
        $launchers = @()
    }
    if (-not $launchers) {
        $listener = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
        if ($listener) { throw 'Port 5000 is occupied by another service. Curs was not started.' }
        Start-Process -FilePath "$projectPath\.venv\Scripts\python.exe" -ArgumentList 'run.py' -WorkingDirectory $projectPath -WindowStyle Hidden -RedirectStandardOutput "$logPath\curs.stdout.log" -RedirectStandardError "$logPath\curs.stderr.log"
    }
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 2
            if ($response.service -eq 'curs' -and $response.running -and $response.quotes.running) { Write-Output 'Curs ready: http://127.0.0.1:5000 (public quotes, signals only)'; exit 0 }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw 'Curs did not become ready. Check logs/curs.stderr.log.'
} finally {
    $startupLock.ReleaseMutex()
    $startupLock.Dispose()
}

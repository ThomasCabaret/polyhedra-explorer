$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root 'campaign\runtime'
$lock = Join-Path $runtime 'runner.lock'
if (Test-Path -LiteralPath $lock) {
    $lockPid = 0
    [void][int]::TryParse((Get-Content -LiteralPath $lock -Raw).Trim(), [ref]$lockPid)
    $running = $false
    if ($lockPid -gt 0) {
        $running = $null -ne (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)
    }
    if ($running) {
        Write-Host "Campaign already running (PID $lockPid). Use status_campaign.bat."
        exit 2
    }
    Remove-Item -LiteralPath $lock -Force
    Write-Host "Removed stale campaign lock (PID $lockPid)."
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$stop = Join-Path $runtime 'STOP'
if (Test-Path -LiteralPath $stop) { Remove-Item -LiteralPath $stop -Force }
$env:PYTHONPATH = Join-Path $root 'src'
$workerOut = Join-Path $runtime 'worker.log'
$workerErr = Join-Path $runtime 'worker.err.log'
$process = Start-Process -FilePath $python -ArgumentList @(
    '-m', 'totocaedres', 'campaign-run',
    '--config', 'campaign\config.json',
    '--runtime', 'campaign\runtime'
) -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $workerOut -RedirectStandardError $workerErr
Write-Host "Campaign started in background (launcher PID $($process.Id))."
Write-Host 'Use status_campaign.bat to inspect progress.'

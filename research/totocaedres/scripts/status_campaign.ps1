$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root 'src'
& $python -m totocaedres campaign-status --runtime 'campaign\runtime'

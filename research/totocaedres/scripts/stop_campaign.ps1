$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root 'campaign\runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$stop = Join-Path $runtime 'STOP'
Set-Content -LiteralPath $stop -Value "stop requested $(Get-Date -Format o)" -Encoding UTF8
Write-Host 'Graceful stop requested. Use status_campaign.bat to watch shutdown.'

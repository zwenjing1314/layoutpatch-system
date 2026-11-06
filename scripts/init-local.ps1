$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path .env) { throw '.env already exists; preserve the existing key.' }
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$key = [Convert]::ToBase64String($bytes)
[IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), "QDRANT_API_KEY=$key`n", (New-Object Text.UTF8Encoding($false)))
Write-Host 'Created ignored .env with a random Qdrant key (not displayed).'

# Beach, Please - kill any backend/frontend processes for this repo.

#Requires -Version 5.1
$ErrorActionPreference = 'Continue'

function Ok($t)   { Write-Host "[OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "[!]  $t" -ForegroundColor Yellow }

$Root   = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir = Join-Path $Root "logs"

$killedAny = $false

# Pidfiles from dev.ps1
foreach ($pf in @("backend.pid", "frontend.pid")) {
    $path = Join-Path $LogDir $pf
    if (Test-Path $path) {
        $procId = (Get-Content $path | Select-Object -First 1).Trim()
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Ok "killed pid $procId (from $pf)"
            $killedAny = $true
        } catch {
            # process already gone, ignore
        }
        Remove-Item -Force $path -ErrorAction SilentlyContinue
    }
}

# Belt + suspenders: any stray uvicorn / next dev processes from this repo.
$strays = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -like "*uvicorn*app.main:app*" -or
        $_.CommandLine -like "*next dev*" -or
        $_.CommandLine -like "*next start*"
    }
foreach ($p in $strays) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Ok "killed stray pid $($p.ProcessId)"
        $killedAny = $true
    } catch { }
}

if (-not $killedAny) { Warn "Nothing to stop - Beach, Please wasn't running." }

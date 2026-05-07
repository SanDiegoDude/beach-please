# Beach, Please - kill any backend/frontend processes for this repo.

#Requires -Version 5.1
$ErrorActionPreference = 'Continue'

function Ok($t)   { Write-Host "[OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "[!]  $t" -ForegroundColor Yellow }

$Root   = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir = Join-Path $Root "logs"

$killedAny = $false

# Cache the full process snapshot once -- we need it for descendant-tree
# walks, and Win32_Process is slow enough that one CIM call beats N of them.
$AllProcs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)

function Get-Descendants {
    param([int]$ParentId)
    $kids = $AllProcs | Where-Object { $_.ParentProcessId -eq $ParentId }
    foreach ($k in $kids) {
        $k
        Get-Descendants -ParentId ([int]$k.ProcessId)
    }
}

function Stop-Tree {
    param([int]$RootId, [string]$Label)
    $tree = @(Get-Descendants -ParentId $RootId) + @($AllProcs | Where-Object { $_.ProcessId -eq $RootId })
    # Kill leaves first so children don't get reparented to PID 1 / explorer.
    $tree = $tree | Sort-Object -Property ProcessId -Descending -Unique
    $killed = $false
    foreach ($p in $tree) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Ok "killed $($p.Name) pid $($p.ProcessId) ($Label)"
            $killed = $true
        } catch {
            # process already gone, ignore
        }
    }
    return $killed
}

# Pidfiles from dev.ps1 -- kill the recorded process AND all its descendants.
# Spawning npm.cmd in a Start-Process means Windows leaves the .cmd's child
# `node next dev` running after we kill the wrapper, so we have to walk down.
foreach ($pf in @("backend.pid", "frontend.pid")) {
    $path = Join-Path $LogDir $pf
    if (Test-Path $path) {
        $procIdText = (Get-Content $path | Select-Object -First 1).Trim()
        $procId = 0
        if ([int]::TryParse($procIdText, [ref]$procId)) {
            if (Stop-Tree -RootId $procId -Label $pf) { $killedAny = $true }
        }
        Remove-Item -Force $path -ErrorAction SilentlyContinue
    }
}

# Belt + suspenders: any stray uvicorn / next dev / npm-run-dev from this
# repo path. Match on the repo dir so we never touch unrelated processes.
$repoLike = "*$Root*"
$strays = $AllProcs | Where-Object {
    $_.CommandLine -and ($_.CommandLine -like $repoLike) -and
    (
        $_.CommandLine -like "*uvicorn*"        -or
        $_.CommandLine -like "*next*dev*"       -or
        $_.CommandLine -like "*next*start*"     -or
        $_.CommandLine -like "*npm*run*dev*"    -or
        $_.CommandLine -like "*node*next*"
    )
}
foreach ($p in $strays) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Ok "killed stray $($p.Name) pid $($p.ProcessId)"
        $killedAny = $true
    } catch { }
}

if (-not $killedAny) { Warn "Nothing to stop - Beach, Please wasn't running." }

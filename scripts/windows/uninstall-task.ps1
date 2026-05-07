# Beach, Please - remove the Windows Scheduled Tasks.

#Requires -Version 5.1
$ErrorActionPreference = 'Continue'

function Ok($t)   { Write-Host "[OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "[!]  $t" -ForegroundColor Yellow }

$removedAny = $false
foreach ($name in @("BeachPleaseBackend", "BeachPleaseFrontend")) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Ok "removed scheduled task $name"
        $removedAny = $true
    }
}

# Also stop any running uvicorn/next from this repo.
$strays = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -like "*uvicorn*app.main:app*" -or
        $_.CommandLine -like "*next start*" -or
        $_.CommandLine -like "*next dev*"
    }
foreach ($p in $strays) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Ok "killed running pid $($p.ProcessId)"
        $removedAny = $true
    } catch { }
}

if (-not $removedAny) { Warn "Nothing to remove - no Beach, Please tasks or processes found." }

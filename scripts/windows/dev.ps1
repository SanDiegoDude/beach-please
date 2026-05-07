# Beach, Please - Windows dev runner (PowerShell).
#
# Starts backend (uvicorn on 0.0.0.0:8765) and frontend (next dev) as
# background jobs. Logs go to logs\{backend,frontend}.{out,err}.log.
# PIDs written to logs\*.pid. Ctrl-C cleans both up.
#
# Usage:
#   .\scripts\windows\dev.ps1

#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

function Write-Color($Color, $Text) { Write-Host $Text -ForegroundColor $Color }
function Ok($t)   { Write-Color Green   "[OK] $t" }
function Info($t) { Write-Color Cyan    "==> $t" }
function Warn($t) { Write-Color Yellow  "[!]  $t" }
function Die($t)  { Write-Color Red     "[X]  $t"; exit 1 }

$Root    = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$LogDir  = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$BackendDir      = Join-Path $Root "backend"
$FrontendDir     = Join-Path $Root "frontend"
$BackendOutLog   = Join-Path $LogDir "backend.out.log"
$BackendErrLog   = Join-Path $LogDir "backend.err.log"
$FrontendOutLog  = Join-Path $LogDir "frontend.out.log"
$FrontendErrLog  = Join-Path $LogDir "frontend.err.log"
$BackendPid      = Join-Path $LogDir "backend.pid"
$FrontendPid     = Join-Path $LogDir "frontend.pid"
$VenvUvicorn     = Join-Path $BackendDir ".venv\Scripts\uvicorn.exe"

# Find npm the same way install.ps1 does: editor-bundled `node` stubs (Cursor,
# VS Code) sit on PATH without npm beside them, so we walk every candidate and
# pick the one that has npm in the same directory.
function Resolve-Npm {
    foreach ($c in @(Get-Command node -All -ErrorAction SilentlyContinue)) {
        $dir  = Split-Path $c.Source -Parent
        $npm  = Join-Path $dir "npm.cmd"
        if (Test-Path $npm) { return $npm }
    }
    $direct = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($direct) { return $direct.Source }
    return $null
}
$NpmCmd = Resolve-Npm
if (-not $NpmCmd) { Die "npm not found. Re-run .\scripts\windows\install.ps1 to diagnose." }

if (-not (Test-Path $VenvUvicorn))   { Die "No .venv\Scripts\uvicorn.exe - run .\scripts\windows\install.ps1 first." }
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) { Die "No node_modules - run .\scripts\windows\install.ps1 first." }

# Wipe old log + pid files for a clean start.
$AllLogs = @($BackendOutLog, $BackendErrLog, $FrontendOutLog, $FrontendErrLog)
Remove-Item -Force -ErrorAction Ignore @($AllLogs + @($BackendPid, $FrontendPid))
New-Item -ItemType File -Force -Path $AllLogs | Out-Null

Info "Backend (uvicorn on 0.0.0.0:8765)"
# Start-Process can't merge stdout+stderr to one file on Windows, so we keep
# them as two and tail both below.
$backendProc = Start-Process -FilePath $VenvUvicorn `
    -ArgumentList "app.main:app", "--host", "0.0.0.0", "--port", "8765" `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $BackendOutLog `
    -RedirectStandardError  $BackendErrLog `
    -PassThru -WindowStyle Hidden
$backendProc.Id | Out-File -Encoding ascii $BackendPid
Ok "backend pid $($backendProc.Id), logs at logs\backend.{out,err}.log"

Info "Frontend (npm run dev)"
# npm.cmd is a batch script. Start-Process can run .cmd files directly when
# given the resolved path, no cmd.exe wrapper needed.
$frontendProc = Start-Process -FilePath $NpmCmd `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $FrontendOutLog `
    -RedirectStandardError  $FrontendErrLog `
    -PassThru -WindowStyle Hidden
$frontendProc.Id | Out-File -Encoding ascii $FrontendPid
Ok "frontend pid $($frontendProc.Id), logs at logs\frontend.{out,err}.log"

# LAN IP detection.
$lanIP = $null
try {
    $lanIP = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
              Where-Object {
                  $_.PrefixOrigin -ne 'WellKnown' -and
                  $_.IPAddress -notlike '169.254.*' -and
                  $_.IPAddress -ne '127.0.0.1'
              } |
              Select-Object -First 1 -ExpandProperty IPAddress)
} catch { }

Write-Host ""
Ok "Beach, Please is running."
Write-Host "  Local:   http://localhost:5757"
if ($lanIP) {
    Write-Host "  LAN:     http://$lanIP`:5757   (open this on your phone)"
}
Write-Host "  Backend: http://localhost:8765/api/beaches"
Write-Host ""
Write-Host "Streaming logs below (Ctrl-C to stop everything)..."
Write-Host ""

# Trap Ctrl-C so we can clean up child processes.
$cleanup = {
    Write-Host ""
    Info "Stopping..."
    foreach ($pf in @($BackendPid, $FrontendPid)) {
        if (Test-Path $pf) {
            $procId = (Get-Content $pf | Select-Object -First 1).Trim()
            try {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Ok "killed pid $procId"
            } catch { }
            Remove-Item -Force $pf -ErrorAction SilentlyContinue
        }
    }
    # Belt + suspenders kill of any uvicorn / next leftovers from this repo.
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object {
          $_.CommandLine -like "*uvicorn*app.main:app*" -or
          $_.CommandLine -like "*next dev*"
      } | ForEach-Object {
          try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch { }
      }
}
# [Console]::TreatControlCAsInput throws "The handle is invalid" when the
# script runs without an attached console (CI, background launches, IDE
# terminals that proxy stdio). Best-effort, swallow the failure.
try { [Console]::TreatControlCAsInput = $false } catch { }
Register-EngineEvent PowerShell.Exiting -Action $cleanup | Out-Null

# Tail all four log streams (stdout + stderr per process) so the operator
# sees live output, just like tail -F on Unix.
$tailJobs = @(
    @{ Tag = "backend"; Path = $BackendOutLog  },
    @{ Tag = "backend"; Path = $BackendErrLog  },
    @{ Tag = "front"  ; Path = $FrontendOutLog },
    @{ Tag = "front"  ; Path = $FrontendErrLog }
) | ForEach-Object {
    $tag  = $_.Tag
    $path = $_.Path
    $job  = Start-Job { param($p) Get-Content -Path $p -Wait -Tail 200 } -ArgumentList $path
    [pscustomobject]@{ Tag = $tag; Job = $job }
}

try {
    while ($true) {
        foreach ($t in $tailJobs) {
            Receive-Job $t.Job | ForEach-Object { Write-Host "[$($t.Tag)] $_" }
        }
        if ($backendProc.HasExited -or $frontendProc.HasExited) {
            Warn "A child process exited - shutting down the other one."
            break
        }
        Start-Sleep -Milliseconds 250
    }
} finally {
    $jobs = $tailJobs | ForEach-Object { $_.Job }
    Stop-Job   $jobs -ErrorAction SilentlyContinue
    Remove-Job $jobs -ErrorAction SilentlyContinue
    & $cleanup
}

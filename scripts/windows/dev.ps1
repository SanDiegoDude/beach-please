# Beach, Please - Windows dev runner (PowerShell).
#
# Starts backend (uvicorn on 0.0.0.0:8765) and frontend (next dev) as
# background jobs. Logs go to logs\backend.log and logs\frontend.log.
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

$BackendDir   = Join-Path $Root "backend"
$FrontendDir  = Join-Path $Root "frontend"
$BackendLog   = Join-Path $LogDir "backend.log"
$FrontendLog  = Join-Path $LogDir "frontend.log"
$BackendPid   = Join-Path $LogDir "backend.pid"
$FrontendPid  = Join-Path $LogDir "frontend.pid"
$VenvUvicorn  = Join-Path $BackendDir ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $VenvUvicorn))   { Die "No .venv\Scripts\uvicorn.exe - run .\scripts\windows\install.ps1 first." }
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) { Die "No node_modules - run .\scripts\windows\install.ps1 first." }

# Wipe old log + pid files for a clean start.
Remove-Item -Force -ErrorAction Ignore $BackendLog, $FrontendLog, $BackendPid, $FrontendPid
New-Item -ItemType File -Force -Path $BackendLog, $FrontendLog | Out-Null

Info "Backend (uvicorn on 0.0.0.0:8765)"
$backendProc = Start-Process -FilePath $VenvUvicorn `
    -ArgumentList "app.main:app", "--host", "0.0.0.0", "--port", "8765" `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError  $BackendLog `
    -PassThru -WindowStyle Hidden
$backendProc.Id | Out-File -Encoding ascii $BackendPid
Ok "backend pid $($backendProc.Id), logs at logs\backend.log"

Info "Frontend (npm run dev)"
$npmCmd = (Get-Command npm).Source
# npm on Windows is a .cmd shim; Start-Process needs cmd.exe to run it.
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm", "run", "dev" `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError  $FrontendLog `
    -PassThru -WindowStyle Hidden
$frontendProc.Id | Out-File -Encoding ascii $FrontendPid
Ok "frontend pid $($frontendProc.Id), logs at logs\frontend.log"

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
[Console]::TreatControlCAsInput = $false
Register-EngineEvent PowerShell.Exiting -Action $cleanup | Out-Null

try {
    # Tail both logs so the operator sees live output.
    $job1 = Start-Job { param($p) Get-Content -Path $p -Wait -Tail 200 } -ArgumentList $BackendLog
    $job2 = Start-Job { param($p) Get-Content -Path $p -Wait -Tail 200 } -ArgumentList $FrontendLog
    while ($true) {
        Receive-Job $job1 | ForEach-Object { Write-Host "[backend] $_" }
        Receive-Job $job2 | ForEach-Object { Write-Host "[front]   $_" }
        if ($backendProc.HasExited -or $frontendProc.HasExited) {
            Warn "A child process exited - shutting down the other one."
            break
        }
        Start-Sleep -Milliseconds 250
    }
} finally {
    Stop-Job  $job1, $job2 -ErrorAction SilentlyContinue
    Remove-Job $job1, $job2 -ErrorAction SilentlyContinue
    & $cleanup
}

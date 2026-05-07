# Beach, Please - install as Windows Scheduled Tasks for always-on home use.
#
# Creates two tasks:
#   - BeachPleaseBackend   (uvicorn on 0.0.0.0:8765)
#   - BeachPleaseFrontend  (next start on 5757)
#
# Both:
#   - Trigger at user logon (your account).
#   - Run hidden, with no visible windows.
#   - Restart on failure (every 1 min, up to 999 times).
#   - Use the current user's session - no SYSTEM, no admin needed for install
#     IF you only need them while you're logged in. (Most home setups: fine.)
#
# To survive logout completely, see the README for the SYSTEM-account version
# (requires running this script in an elevated PowerShell once).
#
# Usage:
#   .\scripts\windows\install-task.ps1
#
# Uninstall:
#   .\scripts\windows\uninstall-task.ps1

#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

function Ok($t)   { Write-Host "[OK] $t" -ForegroundColor Green }
function Info($t) { Write-Host "==> $t" -ForegroundColor Cyan }
function Die($t)  { Write-Host "[X] $t" -ForegroundColor Red; exit 1 }

$Root        = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$LogDir      = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$VenvUvicorn = Join-Path $BackendDir ".venv\Scripts\uvicorn.exe"
if (-not (Test-Path $VenvUvicorn))   { Die "No backend\.venv - run install.ps1 first." }
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) { Die "No node_modules - run install.ps1 first." }

# Build the production frontend bundle so 'npm run start' has something to serve.
Info "Building frontend for production..."
Push-Location $FrontendDir
try { npm run build } finally { Pop-Location }
Ok "frontend built"

# Find npm beside a real node (not Cursor / VS Code's bundled stub which
# ships node without npm). Same logic as install.ps1 / dev.ps1.
function Resolve-Npm {
    foreach ($c in @(Get-Command node -All -ErrorAction SilentlyContinue)) {
        $dir = Split-Path $c.Source -Parent
        $npm = Join-Path $dir "npm.cmd"
        if (Test-Path $npm) { return $npm }
    }
    $direct = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($direct) { return $direct.Source }
    return $null
}
$npmCmd = Resolve-Npm
if (-not $npmCmd) { Die "npm not found beside any node on PATH. Re-run .\scripts\windows\install.ps1 to diagnose." }

# Common settings for both tasks: at-logon trigger, restart on failure,
# hidden window, run in user context.
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -Hidden:$true -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Start-Process can't redirect stdout AND stderr to the same file on Windows,
# so we keep them as separate .out.log / .err.log files for each service.
# --- Backend task ---
$backendCmd = "Start-Process -FilePath '$VenvUvicorn' -ArgumentList 'app.main:app','--host','0.0.0.0','--port','8765' -WorkingDirectory '$BackendDir' -RedirectStandardOutput '$LogDir\backend.out.log' -RedirectStandardError '$LogDir\backend.err.log' -WindowStyle Hidden"
$backendAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"$backendCmd`""

# --- Frontend task ---
$frontendCmd = "Start-Process -FilePath '$npmCmd' -ArgumentList 'run','start' -WorkingDirectory '$FrontendDir' -RedirectStandardOutput '$LogDir\frontend.out.log' -RedirectStandardError '$LogDir\frontend.err.log' -WindowStyle Hidden"
$frontendAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"$frontendCmd`""

# Wipe any existing tasks before recreating - idempotent.
foreach ($name in @("BeachPleaseBackend", "BeachPleaseFrontend")) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
    }
}

Register-ScheduledTask -TaskName "BeachPleaseBackend"  -Action $backendAction  -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Ok "registered task BeachPleaseBackend"
Register-ScheduledTask -TaskName "BeachPleaseFrontend" -Action $frontendAction -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
Ok "registered task BeachPleaseFrontend"

# Start them right now.
Start-ScheduledTask -TaskName "BeachPleaseBackend"
Start-ScheduledTask -TaskName "BeachPleaseFrontend"
Ok "started both tasks"

Start-Sleep -Seconds 2

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
Ok "Beach, Please is now installed as Scheduled Tasks."
Write-Host @"

It will:
  - Auto-start when you log in.
  - Restart automatically on failure.
  - Log to $LogDir\{backend,frontend}.{out,err}.log.

Open from any device on your home Wi-Fi:
  Local:  http://localhost:5757
"@
if ($lanIP) {
    Write-Host "  LAN:    http://$lanIP`:5757"
}
Write-Host @"

Manage:
  Status:    Get-ScheduledTask -TaskName BeachPleaseBackend, BeachPleaseFrontend
  Stop:      Stop-ScheduledTask -TaskName BeachPleaseBackend
             Stop-ScheduledTask -TaskName BeachPleaseFrontend
  Restart:   Stop-ScheduledTask + Start-ScheduledTask
  Uninstall: .\scripts\windows\uninstall-task.ps1

If port 5757 or 8765 is in use, close the conflicting process or edit
this script before re-running.

Note: Tasks run in your user session, so they pause if you log out. To
keep them running headless, install with the SYSTEM-account variant:
re-run this script in an *elevated* PowerShell after editing -LogonType
to ServiceAccount and -UserId to "SYSTEM" - or use NSSM.
"@

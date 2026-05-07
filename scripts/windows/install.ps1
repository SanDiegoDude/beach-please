# Beach, Please - Windows installer (PowerShell).
#
# Idempotent. Safe to re-run.
#   - Verifies Python 3.11+ and Node 20+
#   - Creates backend\.venv and installs Python deps (uv if present, pip otherwise)
#   - Installs frontend node_modules
#   - Seeds backend\.env and frontend\.env.local from examples if missing
#
# Usage (from PowerShell, in repo root):
#   .\scripts\windows\install.ps1
#
# If you get an execution-policy error, run this once (per-user, no admin):
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

function Write-Color($Color, $Text) { Write-Host $Text -ForegroundColor $Color }
function Ok($t)   { Write-Color Green   "[OK] $t" }
function Info($t) { Write-Color Cyan    "==> $t" }
function Warn($t) { Write-Color Yellow  "[!]  $t" }
function Die($t)  { Write-Color Red     "[X]  $t"; exit 1 }

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

Info "Checking dependencies"

# --- Python ---
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pyCmd) {
    Die "python not found. Install Python 3.11+ from https://python.org and check 'Add to PATH'."
}
$pyVer = & $pyCmd.Source -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
$verParts = $pyVer.Split('.')
if ([int]$verParts[0] -lt 3 -or ([int]$verParts[0] -eq 3 -and [int]$verParts[1] -lt 11)) {
    Die "Python 3.11+ required, found $pyVer."
}
Ok "python $pyVer"

# --- Node + npm ---
# Cursor / VS Code / Electron apps put their own bundled `node.exe` on PATH,
# but ship it WITHOUT npm. So we can't trust the first `node` we find -- we
# need a node that has npm sitting beside it. Walk every node on PATH and
# pick the first one paired with npm; fall back to common install dirs.
function Find-NodeWithNpm {
    $candidates = @(Get-Command node -All -ErrorAction SilentlyContinue)
    foreach ($c in $candidates) {
        $dir = Split-Path $c.Source -Parent
        if ((Test-Path (Join-Path $dir "npm.cmd")) -or
            (Test-Path (Join-Path $dir "npm.exe")) -or
            (Test-Path (Join-Path $dir "npm"))) {
            return $c.Source
        }
    }
    # Fallback: PATH may not be refreshed yet (e.g. fresh winget install in
    # the same shell). Probe common Node.js install locations.
    $fallbacks = @(
        "$env:ProgramFiles\nodejs\node.exe",
        "${env:ProgramFiles(x86)}\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe",
        "$env:APPDATA\npm\node.exe"
    )
    foreach ($f in $fallbacks) {
        if ($f -and (Test-Path $f)) {
            $dir = Split-Path $f -Parent
            if (Test-Path (Join-Path $dir "npm.cmd")) { return $f }
        }
    }
    return $null
}

$nodeExe = Find-NodeWithNpm
if (-not $nodeExe) {
    $bareNode = Get-Command node -ErrorAction SilentlyContinue
    if ($bareNode -and ($bareNode.Source -like "*\cursor\*" -or $bareNode.Source -like "*\Microsoft VS Code\*")) {
        Die @"
Found 'node' at '$($bareNode.Source)' but no 'npm' beside it.
That's the editor's bundled Node helper, not a real Node.js installation.

Install Node.js 20+ with one of:
  winget install OpenJS.NodeJS.LTS
  choco install nodejs-lts
  or download from https://nodejs.org

Then OPEN A NEW PowerShell window so PATH picks up npm, and re-run this script.
"@
    } elseif ($bareNode) {
        Die "Found 'node' at '$($bareNode.Source)' but no 'npm' beside it. Reinstall Node.js from https://nodejs.org and reopen this terminal."
    } else {
        Die "node not found. Install Node 20+: 'winget install OpenJS.NodeJS.LTS' or download from https://nodejs.org"
    }
}

$nodeVer = (& $nodeExe -v).TrimStart('v')
if ([int]($nodeVer.Split('.')[0]) -lt 20) { Die "Node 20+ required, found $nodeVer (at $nodeExe)." }
Ok "node v$nodeVer ($nodeExe)"

# npm on Windows is npm.cmd. Resolve it as an absolute path so we don't
# depend on PATH lookup, which can be hijacked by editor stubs.
$nodeDir = Split-Path $nodeExe -Parent
$npmExe  = @("npm.cmd", "npm.exe", "npm") |
    ForEach-Object { Join-Path $nodeDir $_ } |
    Where-Object   { Test-Path $_ } |
    Select-Object  -First 1
if (-not $npmExe) { Die "npm not found beside node at '$nodeDir'. Reinstall Node.js." }
Ok "npm $(& $npmExe -v)"

# --- uv (optional) ---
$useUv = $false
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $useUv = $true
    Ok "uv $((uv --version).Split(' ')[1]) (will use for speed)"
} else {
    Warn "uv not installed - falling back to pip. For ~10x faster setup: 'pip install uv' or download from https://docs.astral.sh/uv/"
}

# --- Backend ---
Info "Backend"
Set-Location (Join-Path $Root "backend")

$VenvDir   = ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvDir)) {
    if ($useUv) { uv venv } else { & $pyCmd.Source -m venv $VenvDir }
    Ok "created $VenvDir"
} else {
    Ok "$VenvDir exists"
}

if ($useUv) {
    uv pip install -r requirements.txt
} else {
    & $VenvPip install --upgrade pip | Out-Null
    & $VenvPip install -r requirements.txt
}
Ok "Python deps installed"

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Warn "wrote backend\.env from .env.example - EDIT IT to point at your AI provider"
} else {
    Ok "backend\.env already exists"
}

# --- Frontend ---
Info "Frontend"
Set-Location (Join-Path $Root "frontend")

if (-not (Test-Path "node_modules")) {
    & $npmExe install
} else {
    Ok "node_modules exists (run 'npm install' in frontend\ if package.json changed)"
}
Ok "Node deps installed"

if ((-not (Test-Path .env.local)) -and (Test-Path .env.example)) {
    Copy-Item .env.example .env.local
    Ok "wrote frontend\.env.local from .env.example"
}

Set-Location $Root

Info "Done"
Write-Host ""
Ok "Installation complete."
Write-Host @"

Next steps:
  1. Edit backend\.env to point at your AI provider. The file has annotated
     profiles for OpenAI, LM Studio, and Ollama - copy the one you want.

  2. Run both servers:
       .\scripts\windows\dev.ps1
     or, individually in two terminals:
       cd backend
       .\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8765
       cd frontend
       npm run dev

  3. Open http://localhost:5757

  4. For phones / other devices on your home Wi-Fi:
       http://<this-machine-LAN-IP>:5757
     The frontend auto-detects the backend host - no per-device config.

  5. To install as an always-on service that auto-starts at login:
       .\scripts\windows\install-task.ps1

"@

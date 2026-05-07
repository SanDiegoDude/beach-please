#!/usr/bin/env bash
# Beach, Please — one-shot installer.
# Works on macOS and Linux. Windows users: use scripts\windows\install.ps1.
#
# Idempotent. Safe to re-run.
#   - Verifies Python 3.11+ and Node 20+
#   - Creates backend/.venv and installs Python deps (uv if present, pip otherwise)
#   - Installs frontend node_modules
#   - Seeds backend/.env and frontend/.env.local from examples if missing

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

color()  { printf "\033[1;36m%s\033[0m\n" "$*"; }
ok()     { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn()   { printf "\033[1;33m! %s\033[0m\n" "$*"; }
die()    { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

# OS-aware dependency-install hint, used in error messages.
case "$(uname -s)" in
  Darwin)  PKG_HINT="brew install python@3.12 node uv" ;;
  Linux)
    if   command -v apt-get >/dev/null 2>&1; then PKG_HINT="sudo apt install python3 python3-venv nodejs npm  (and: pip install uv)"
    elif command -v dnf     >/dev/null 2>&1; then PKG_HINT="sudo dnf install python3 nodejs npm  (and: pip install uv)"
    elif command -v pacman  >/dev/null 2>&1; then PKG_HINT="sudo pacman -S python python-pip nodejs npm  (and: pip install uv)"
    else PKG_HINT="install python3 + nodejs + npm with your distro's package manager"
    fi
    ;;
  *)       PKG_HINT="install Python 3.11+, Node 20+, and (optionally) uv" ;;
esac

# venv-relative paths differ between Unix and Windows. We're Unix here.
VENV_BIN=".venv/bin"
VENV_PY="$VENV_BIN/python"
VENV_PIP="$VENV_BIN/pip"

color "==> Checking dependencies"

if command -v python3 >/dev/null 2>&1; then
  PY_VER="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
  PY_MAJOR="$(echo "$PY_VER" | cut -d. -f1)"
  PY_MINOR="$(echo "$PY_VER" | cut -d. -f2)"
  if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    die "Python 3.11+ required, found $PY_VER. Hint: $PKG_HINT"
  fi
  ok "python3 $PY_VER"
else
  die "python3 not found. Install it first. Hint: $PKG_HINT"
fi

if command -v node >/dev/null 2>&1; then
  NODE_VER="$(node -v | sed 's/^v//')"
  NODE_MAJOR="$(echo "$NODE_VER" | cut -d. -f1)"
  if [ "$NODE_MAJOR" -lt 20 ]; then
    die "Node 20+ required, found $NODE_VER. Hint: $PKG_HINT"
  fi
  ok "node v$NODE_VER"
else
  die "node not found. Install it first. Hint: $PKG_HINT"
fi

if ! command -v npm >/dev/null 2>&1; then
  die "npm not found. It usually ships with node — try reinstalling node."
fi
ok "npm $(npm -v)"

# uv is optional; we use it if present, fall back to plain pip otherwise.
USE_UV=false
if command -v uv >/dev/null 2>&1; then
  USE_UV=true
  ok "uv $(uv --version | awk '{print $2}') (will use for speed)"
else
  warn "uv not installed — falling back to pip. Install uv for ~10x faster setup."
fi

color "==> Backend"
cd "$ROOT/backend"

if [ ! -d .venv ]; then
  if $USE_UV; then
    uv venv
  else
    python3 -m venv .venv
  fi
  ok "created .venv"
else
  ok ".venv exists"
fi

if $USE_UV; then
  uv pip install -r requirements.txt
else
  "$VENV_PIP" install --upgrade pip >/dev/null
  "$VENV_PIP" install -r requirements.txt
fi
ok "Python deps installed"

if [ ! -f .env ]; then
  cp .env.example .env
  warn "wrote backend/.env from .env.example — EDIT IT to point at your AI provider"
else
  ok "backend/.env already exists"
fi

color "==> Frontend"
cd "$ROOT/frontend"

if [ ! -d node_modules ]; then
  npm install
else
  ok "node_modules exists (run 'npm install' in frontend/ if package.json changed)"
fi
ok "Node deps installed"

if [ ! -f .env.local ] && [ -f .env.example ]; then
  cp .env.example .env.local
  ok "wrote frontend/.env.local from .env.example"
fi

color "==> Done"
cat <<EOF

  $(ok "Installation complete.")

  Next steps:
    1. Edit backend/.env to point at your AI provider (OpenAI key, LM Studio
       URL, or Ollama URL). The file has annotated profiles to copy from.
    2. Run both servers:
         ./scripts/dev.sh
       or, individually:
         (cd backend  && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8765)
         (cd frontend && npm run dev)
    3. Open http://localhost:5757
    4. To use from a phone on your home Wi-Fi, open
         http://<this-machine-LAN-IP>:5757
       (no extra config — the frontend auto-detects the backend host).

EOF

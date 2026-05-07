#!/usr/bin/env bash
# Beach, Please — start both backend and frontend in dev mode.
# Works on macOS and Linux. Windows users: use scripts\windows\dev.ps1.
#
# Backend binds 0.0.0.0:8765 (so phones on the LAN can reach it).
# Frontend binds whatever port package.json configures (default 5757).
# Logs go to logs/backend.log and logs/frontend.log; PIDs to logs/*.pid.
# Ctrl-C cleans both up.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

color() { printf "\033[1;36m%s\033[0m\n" "$*"; }
ok()    { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }

cleanup() {
  echo
  color "==> Stopping..."
  for f in "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid"; do
    if [ -f "$f" ]; then
      pid="$(cat "$f")"
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        ok "killed pid $pid"
      fi
      rm -f "$f"
    fi
  done
  exit 0
}
trap cleanup INT TERM

color "==> Backend (uvicorn on 0.0.0.0:8765)"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "No .venv — run ./scripts/install.sh first." >&2
  exit 1
fi
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8765 \
  > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$LOG_DIR/backend.pid"
ok "backend pid $(cat "$LOG_DIR/backend.pid"), logs at logs/backend.log"

color "==> Frontend (npm run dev)"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "No node_modules — run ./scripts/install.sh first." >&2
  exit 1
fi
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$LOG_DIR/frontend.pid"
ok "frontend pid $(cat "$LOG_DIR/frontend.pid"), logs at logs/frontend.log"

# Print LAN URL for phone access. Mac, Linux, and BSD have different ways
# to ask the OS for our primary LAN IP — try them in order.
LAN_IP=""
if [ "$(uname -s)" = "Darwin" ] && command -v ipconfig >/dev/null 2>&1; then
  # macOS first: en0 is usually Wi-Fi, en1 Ethernet.
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [ -z "$LAN_IP" ] && command -v hostname >/dev/null 2>&1; then
  # Linux: -I gives all non-loopback IPs, take the first.
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi
if [ -z "$LAN_IP" ] && command -v ip >/dev/null 2>&1; then
  # Modern Linux fallback.
  LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}' || true)"
fi

echo
ok "Beach, Please is running."
echo "  Local:   http://localhost:5757"
if [ -n "$LAN_IP" ]; then
  echo "  LAN:     http://$LAN_IP:5757   (open this on your phone)"
fi
echo "  Backend: http://localhost:8765/api/beaches"
echo
echo "Streaming logs below (Ctrl-C to stop everything):"
echo

# Tail both log files in the foreground. This both keeps the script alive
# (so the trap can clean up on Ctrl-C) and gives the operator live visibility
# without needing a second terminal. Avoids `wait -n` which isn't in bash 3.2
# (the default on macOS).
tail -F "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
cleanup

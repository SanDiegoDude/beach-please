#!/usr/bin/env bash
# Beach, Please — kill any backend/frontend processes started by dev.sh
# (or by hand). Best-effort.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"

ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }

killed_any=0

# Pidfiles from dev.sh
for f in "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid"; do
  if [ -f "$f" ]; then
    pid="$(cat "$f")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      ok "killed pid $pid (from $f)"
      killed_any=1
    fi
    rm -f "$f"
  fi
done

# Belt-and-suspenders pkill in case stale processes are around.
if pkill -f "uvicorn app.main" 2>/dev/null; then
  ok "pkilled uvicorn app.main"
  killed_any=1
fi
if pkill -f "next dev" 2>/dev/null; then
  ok "pkilled next dev"
  killed_any=1
fi

if [ "$killed_any" -eq 0 ]; then
  warn "Nothing to stop — Beach, Please wasn't running."
fi

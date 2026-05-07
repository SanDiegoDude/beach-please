#!/usr/bin/env bash
# Install Beach, Please as macOS launchd jobs so it auto-starts at login
# and restarts on crash. Designed for "always-on home server" use.
#
# Usage:
#   ./scripts/macos/install-launchd.sh
#
# Requires: macOS, npm, and a successful `make install` first.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
TMPL_DIR="$ROOT/scripts/macos"

ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }
die()  { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || die "launchd jobs are macOS-only. On Linux, use systemd (see README)."
command -v npm >/dev/null 2>&1 || die "npm not found in PATH"
[ -d "$ROOT/backend/.venv" ] || die "Backend not installed. Run 'make install' first."
[ -d "$ROOT/frontend/node_modules" ] || die "Frontend not installed. Run 'make install' first."

NPM_PATH="$(command -v npm)"
mkdir -p "$LAUNCH_DIR" "$ROOT/logs"

# Build the production frontend bundle so 'npm run start' has something to serve.
echo "==> Building frontend for production..."
(cd "$ROOT/frontend" && npm run build)
ok "frontend built"

# Render templates with this repo's absolute path.
for svc in backend frontend; do
  src="$TMPL_DIR/com.beachplease.${svc}.plist.tmpl"
  dst="$LAUNCH_DIR/com.beachplease.${svc}.plist"
  sed -e "s|__REPO__|$ROOT|g" -e "s|__NPM__|$NPM_PATH|g" "$src" > "$dst"
  ok "wrote $dst"
done

# Reload — bootout first in case they're already loaded.
for svc in backend frontend; do
  label="com.beachplease.${svc}"
  launchctl bootout "gui/$UID/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$UID" "$LAUNCH_DIR/${label}.plist"
  ok "loaded $label"
done

LAN_IP=""
if command -v ipconfig >/dev/null 2>&1; then
  LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
fi

cat <<EOF

  $(ok "Beach, Please is now installed as a launchd service.")

  It will:
    - Start automatically when you log in.
    - Restart automatically if it crashes.
    - Log to logs/backend.log and logs/frontend.log.

  Open it from any device on your home Wi-Fi:
    Local:  http://localhost:5757
EOF
if [ -n "$LAN_IP" ]; then
  cat <<EOF
    LAN:    http://$LAN_IP:5757
EOF
fi
cat <<EOF

  Manage:
    Status:    launchctl print gui/\$UID/com.beachplease.backend
    Stop:      launchctl bootout gui/\$UID/com.beachplease.backend
    Restart:   make uninstall-launchd && make install-launchd
    Uninstall: make uninstall-launchd

  If port 5757 or 8765 is in use, edit
  scripts/macos/com.beachplease.{backend,frontend}.plist.tmpl
  and re-run this script.

EOF

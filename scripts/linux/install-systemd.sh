#!/usr/bin/env bash
# Install Beach, Please as systemd user services for always-on home use.
# Designed for headless Linux servers — no sudo required.
#
# Why user services? They:
#   - Don't need root.
#   - Auto-start when the user logs in (or always, with `loginctl enable-linger`).
#   - Survive logout if linger is enabled.
#
# Usage:
#   ./scripts/linux/install-systemd.sh
#
# Headless / SSH servers should also run:
#   sudo loginctl enable-linger $USER
# so the services keep running after you disconnect.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMPL_DIR="$ROOT/scripts/linux"
USER_UNIT_DIR="$HOME/.config/systemd/user"

ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }
die()  { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || die "Linux only. Use install-launchd.sh on macOS or install-task.ps1 on Windows."
command -v systemctl >/dev/null 2>&1 || die "systemctl not found. Is this a systemd distro?"
command -v npm >/dev/null 2>&1 || die "npm not found in PATH."
[ -d "$ROOT/backend/.venv" ] || die "Backend not installed. Run ./scripts/install.sh first."
[ -d "$ROOT/frontend/node_modules" ] || die "Frontend not installed. Run ./scripts/install.sh first."

NPM_PATH="$(command -v npm)"
mkdir -p "$USER_UNIT_DIR" "$ROOT/logs"

echo "==> Building frontend for production..."
(cd "$ROOT/frontend" && npm run build)
ok "frontend built"

for svc in backend frontend; do
  src="$TMPL_DIR/beach-please-${svc}.service.tmpl"
  dst="$USER_UNIT_DIR/beach-please-${svc}.service"
  sed -e "s|__REPO__|$ROOT|g" -e "s|__NPM__|$NPM_PATH|g" "$src" > "$dst"
  ok "wrote $dst"
done

systemctl --user daemon-reload
ok "reloaded systemd user units"

for svc in backend frontend; do
  systemctl --user enable "beach-please-${svc}.service"
  systemctl --user restart "beach-please-${svc}.service"
  ok "enabled + started beach-please-${svc}"
done

LAN_IP=""
if command -v hostname >/dev/null 2>&1; then
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi
if [ -z "$LAN_IP" ] && command -v ip >/dev/null 2>&1; then
  LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}' || true)"
fi

cat <<EOF

  $(ok "Beach, Please is now installed as a systemd user service.")

  Status:    systemctl --user status beach-please-backend
             systemctl --user status beach-please-frontend
  Restart:   systemctl --user restart beach-please-{backend,frontend}
  Logs:      journalctl --user -u beach-please-backend -f
             tail -f $ROOT/logs/{backend,frontend}.log
  Stop all:  ./scripts/linux/uninstall-systemd.sh

  To survive logout (headless / SSH-only servers), run ONCE as root:
    sudo loginctl enable-linger $USER

  Open from any device on your LAN:
    Local:   http://localhost:5757
EOF
if [ -n "$LAN_IP" ]; then
  echo "    LAN:     http://$LAN_IP:5757"
fi
echo

#!/usr/bin/env bash
# Remove the Beach, Please systemd user services.

set -euo pipefail

USER_UNIT_DIR="$HOME/.config/systemd/user"
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }

[ "$(uname -s)" = "Linux" ] || { echo "Linux only." >&2; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "no systemctl" >&2; exit 1; }

for svc in backend frontend; do
  unit="beach-please-${svc}.service"
  if systemctl --user list-unit-files "$unit" 2>/dev/null | grep -q "$unit"; then
    systemctl --user stop "$unit" 2>/dev/null || true
    systemctl --user disable "$unit" 2>/dev/null || true
    ok "stopped + disabled $unit"
  fi
  if [ -f "$USER_UNIT_DIR/$unit" ]; then
    rm -f "$USER_UNIT_DIR/$unit"
    ok "removed $USER_UNIT_DIR/$unit"
  fi
done

systemctl --user daemon-reload
ok "Done. Beach, Please is no longer auto-starting."

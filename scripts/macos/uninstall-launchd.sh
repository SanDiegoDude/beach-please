#!/usr/bin/env bash
# Remove the Beach, Please launchd jobs.

set -euo pipefail

LAUNCH_DIR="$HOME/Library/LaunchAgents"
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }

[ "$(uname)" = "Darwin" ] || { echo "macOS only." >&2; exit 1; }

for svc in backend frontend; do
  label="com.beachplease.${svc}"
  if launchctl print "gui/$UID/$label" >/dev/null 2>&1; then
    launchctl bootout "gui/$UID/$label" 2>/dev/null || true
    ok "stopped $label"
  fi
  if [ -f "$LAUNCH_DIR/${label}.plist" ]; then
    rm -f "$LAUNCH_DIR/${label}.plist"
    ok "removed plist for $label"
  fi
done

ok "Done. Beach, Please is no longer auto-starting."

#!/usr/bin/env bash
# Render the launchd template and load the daily job.

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_config

PLIST="$HOME/Library/LaunchAgents/${LAUNCHD_LABEL}.plist"
mkdir -p "$(dirname "$PLIST")"

log "Rendering $PLIST"
sed -e "s|@@LABEL@@|${LAUNCHD_LABEL}|g" \
    -e "s|@@REPO_ROOT@@|${REPO_ROOT}|g" \
    -e "s|@@DIGEST_HOME@@|${DIGEST_HOME}|g" \
    -e "s|@@HOME@@|${HOME}|g" \
    -e "s|@@HOUR@@|${HORIZON_HOUR}|g" \
    -e "s|@@MINUTE@@|${HORIZON_MINUTE}|g" \
    "$REPO_ROOT/launchd/horizon.plist.template" > "$PLIST"

plutil -lint "$PLIST" >/dev/null || die "rendered plist is invalid"

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

ok "scheduled ${LAUNCHD_LABEL} daily at $(printf '%02d:%02d' "$HORIZON_HOUR" "$HORIZON_MINUTE")"
log "Uninstall with: make uninstall-schedule"

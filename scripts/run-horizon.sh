#!/usr/bin/env bash
# Run Horizon for today. This is what the launchd job invokes.
#
# Exits non-zero if Horizon aborts. That matters: Horizon refuses to emit a
# summary when AI analysis broadly fails, because an empty digest is
# indistinguishable from a genuinely quiet news day.

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_config

need uv

[ -d "$HORIZON_DIR" ] || die "Horizon not installed. Run: make install"

LOG="$DIGEST_HOME/horizon.log"
mkdir -p "$(dirname "$LOG")"

# Keep the log from growing without bound (it reached 440KB in practice).
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 5242880 ]; then
  mv "$LOG" "$LOG.1"
fi

log "Running Horizon → $(summary_path)"
# COLUMNS keeps rich from truncating file paths in the log to something
# misleading, which makes failures much harder to diagnose after the fact.
if COLUMNS=200 uv run --project "$HORIZON_DIR" horizon \
     --data-dir "$HORIZON_DIR/data" --log-level WARNING >>"$LOG" 2>&1; then
  ok "Horizon finished"
else
  status=$?
  warn "Horizon failed (exit $status). Last 20 log lines:"
  tail -20 "$LOG" >&2
  exit "$status"
fi

SUMMARY="$(summary_path)"
[ -f "$SUMMARY" ] || die "Horizon reported success but $SUMMARY is missing"
ok "summary: $SUMMARY ($(wc -c < "$SUMMARY") bytes)"

if [ "${PODCAST_ENABLED:-false}" = "true" ]; then
  log "Generating podcast"
  "$REPO_ROOT/scripts/generate-podcast.sh" || warn "podcast generation failed (digest is unaffected)"
fi

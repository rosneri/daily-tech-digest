#!/usr/bin/env bash
# One-shot installer. Safe to re-run: every step is idempotent.
#
#   ./install.sh              full install
#   ./install.sh --no-podcast skip podcastfy
#   ./install.sh --no-schedule skip the launchd job

set -euo pipefail
cd "$(dirname "$0")"

WITH_PODCAST=1
WITH_SCHEDULE=1
for arg in "$@"; do
  case "$arg" in
    --no-podcast)  WITH_PODCAST=0 ;;
    --no-schedule) WITH_SCHEDULE=0 ;;
    -h|--help)     sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

. scripts/lib.sh

# --- 1. config ---------------------------------------------------------------
if [ ! -f config.env ]; then
  cp config.env.example config.env
  ok "created config.env from the example"
  warn "SLACK_CHANNEL_ID is empty — set it in config.env before the digest can post"
fi
load_config

# --- 2. prerequisites --------------------------------------------------------
log "Checking prerequisites"
need git
need python3
command -v uv >/dev/null 2>&1 \
  || die "uv is required. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v claude >/dev/null 2>&1 \
  || warn "the 'claude' CLI is not on PATH — Horizon scoring and podcast scripting both need it"
ok "prerequisites present"

mkdir -p "$DIGEST_HOME"/{digests,podcasts}

# --- 3. horizon --------------------------------------------------------------
scripts/bootstrap-horizon.sh

# --- 4. preferences ----------------------------------------------------------
if [ -f "$DIGEST_HOME/preferences.json" ]; then
  ok "preferences.json exists — left untouched"
else
  cp config/preferences.json "$DIGEST_HOME/preferences.json"
  ok "installed preferences.json"
fi
[ -f "$DIGEST_HOME/favorites.json" ] || echo '{"favorites": []}' > "$DIGEST_HOME/favorites.json"

# --- 5. podcast --------------------------------------------------------------
if [ "$WITH_PODCAST" = 1 ] && [ "${PODCAST_ENABLED:-false}" = "true" ]; then
  scripts/install-podcast.sh
else
  log "Skipping podcast install"
fi

# --- 6. schedule -------------------------------------------------------------
if [ "$WITH_SCHEDULE" = 1 ]; then
  scripts/install-launchd.sh
else
  log "Skipping launchd install"
fi

# --- done --------------------------------------------------------------------
cat <<DONE

Installed.

  state          $DIGEST_HOME
  horizon        $HORIZON_DIR
  summaries      $SUMMARY_DIR
  podcasts       $PODCAST_DIR

Next:
  1. Set SLACK_CHANNEL_ID in config.env if you have not already.
  2. Register the Claude routine — see "The Claude routine" in README.md;
     the task definition is skill/SKILL.md.
  3. Try it:  make run-horizon
DONE

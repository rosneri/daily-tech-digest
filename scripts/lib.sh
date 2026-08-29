#!/usr/bin/env bash
# Shared helpers: config loading, logging, dependency checks.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { printf '\033[0;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m  !!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

load_config() {
  local cfg="$REPO_ROOT/config.env"
  [ -f "$cfg" ] || die "config.env not found. Run: cp config.env.example config.env && \$EDITOR config.env"
  # shellcheck disable=SC1090
  set -a; . "$cfg"; set +a

  : "${DIGEST_HOME:?DIGEST_HOME must be set in config.env}"
  HORIZON_DIR="$DIGEST_HOME/horizon"
  SUMMARY_DIR="$HORIZON_DIR/data/summaries"
  DIGEST_DIR="$DIGEST_HOME/digests"
  PODCAST_DIR="$DIGEST_HOME/podcasts"
  export HORIZON_DIR SUMMARY_DIR DIGEST_DIR PODCAST_DIR
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1${2:+ — $2}"
}

# Horizon writes horizon-YYYY-MM-DD-en.md; default to today.
summary_path() {
  local date="${1:-$(date +%F)}"
  echo "$SUMMARY_DIR/horizon-${date}-en.md"
}

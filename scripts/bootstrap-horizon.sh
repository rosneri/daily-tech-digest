#!/usr/bin/env bash
# Clone Horizon at the pinned commit and apply our local patch.
#
# Horizon (https://github.com/Thysrael/Horizon, MIT) is upstream software we do
# not vendor. patches/horizon-local.patch carries two things:
#   1. an AI client that shells out to the `claude` CLI, so no API key is needed
#   2. source/reliability fixes — see patches/README.md

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_config

need git
need uv "install from https://docs.astral.sh/uv/"

PATCH="$REPO_ROOT/patches/horizon-local.patch"

if [ -d "$HORIZON_DIR/.git" ]; then
  log "Horizon already present at $HORIZON_DIR"
  if git -C "$HORIZON_DIR" apply --reverse --check "$PATCH" >/dev/null 2>&1; then
    ok "patch already applied"
  else
    warn "existing checkout does not match our patch; leaving it alone"
    warn "to rebuild from scratch: rm -rf '$HORIZON_DIR' && make install"
  fi
else
  log "Cloning Horizon into $HORIZON_DIR"
  mkdir -p "$(dirname "$HORIZON_DIR")"
  git clone --quiet "$HORIZON_REPO" "$HORIZON_DIR"
  git -C "$HORIZON_DIR" checkout --quiet "$HORIZON_PIN"
  ok "checked out $HORIZON_PIN"

  log "Applying patches/horizon-local.patch"
  git -C "$HORIZON_DIR" apply --check "$PATCH" \
    || die "patch does not apply to $HORIZON_PIN — HORIZON_PIN and the patch are out of sync"
  git -C "$HORIZON_DIR" apply "$PATCH"
  ok "patch applied"
fi

log "Installing Horizon dependencies (uv sync)"
(cd "$HORIZON_DIR" && uv sync --quiet)
ok "dependencies installed"

log "Installing Horizon config"
mkdir -p "$HORIZON_DIR/data"
if [ -f "$HORIZON_DIR/data/config.json" ]; then
  ok "data/config.json exists — left untouched (delete it to re-seed)"
else
  python3 - "$REPO_ROOT/config/horizon.config.json" \
             "$HORIZON_DIR/data/config.json" "$HORIZON_THRESHOLD" <<'PY'
import json, sys
src, dst, threshold = sys.argv[1], sys.argv[2], float(sys.argv[3])
cfg = json.load(open(src))
cfg["processing"]["profile_settings"]["tech-news"]["threshold"] = threshold
json.dump(cfg, open(dst, "w"), indent=2, ensure_ascii=False)
PY
  ok "seeded data/config.json (threshold=$HORIZON_THRESHOLD)"
fi

# Horizon reads .env for the optional GitHub token; never commit this file.
if [ ! -f "$HORIZON_DIR/.env" ]; then
  cat > "$HORIZON_DIR/.env" <<'ENV'
# Optional. Without a token GitHub allows 60 requests/hour; a normal run uses
# ~16, so a single extra manual run can exhaust it. With a token: 5000/hour.
# GITHUB_TOKEN=
ENV
  ok "created .env stub"
fi

log "Done. Test with: make run-horizon"

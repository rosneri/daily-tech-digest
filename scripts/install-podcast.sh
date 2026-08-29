#!/usr/bin/env bash
# podcastfy needs Python >=3.11,<4 and pulls a large dependency tree, so it
# lives in its own venv rather than alongside Horizon's.

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_config

VENV="$DIGEST_HOME/.podcast-venv"

if command -v uv >/dev/null 2>&1; then
  log "Creating podcast venv with uv (Python 3.12)"
  uv venv --quiet --python 3.12 "$VENV"
  log "Installing podcastfy"
  # podcastfy 0.4.x imports playwright at module load without declaring it
  # as a dependency, so client.py fails to import unless we add it.
  VIRTUAL_ENV="$VENV" uv pip install --quiet podcastfy playwright
else
  need python3
  ver=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
  case "$ver" in
    3.11|3.12|3.13) ;;
    *) die "podcastfy needs Python 3.11-3.13, found $ver. Install uv for an isolated interpreter." ;;
  esac
  log "Creating podcast venv with python3 $ver"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  log "Installing podcastfy"
  # see note above re: playwright
  "$VENV/bin/pip" install --quiet podcastfy playwright
fi

# ffmpeg is what actually stitches the audio segments together.
if ! command -v ffmpeg >/dev/null 2>&1; then
  warn "ffmpeg not found — podcastfy needs it to assemble audio"
  warn "install with: brew install ffmpeg"
fi

ok "podcastfy $("$VENV/bin/python" -c 'import podcastfy;print(podcastfy.__version__)' 2>/dev/null || echo installed)"
ok "venv: $VENV"

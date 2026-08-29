#!/usr/bin/env bash
# Thin wrapper: read config.env, then drive scripts/generate_podcast.py.

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_config

# First positional is the date (optional); anything after is passed through to
# generate_podcast.py, e.g. --transcript-only.
DATE="$(date +%F)"
if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  DATE="$1"; shift
fi
SUMMARY="$(summary_path "$DATE")"

[ -f "$SUMMARY" ] || die "no Horizon summary for $DATE at $SUMMARY"

VENV="$DIGEST_HOME/.podcast-venv"
[ -x "$VENV/bin/python" ] || die "podcast venv missing. Run: make install-podcast"

mkdir -p "$PODCAST_DIR"

exec "$VENV/bin/python" "$REPO_ROOT/scripts/generate_podcast.py" \
  --summary "$SUMMARY" \
  --date "$DATE" \
  --out-dir "$PODCAST_DIR" \
  --max-stories "${PODCAST_MAX_STORIES:-8}" \
  --tts-model "${PODCAST_TTS_MODEL:-edge}" \
  --script-engine "${PODCAST_SCRIPT_ENGINE:-claude-cli}" \
  --llm-model "${PODCAST_LLM_MODEL:-claude-sonnet-5}" \
  --llm-api-key-label "${PODCAST_LLM_API_KEY_LABEL:-GEMINI_API_KEY}" \
  --name "${PODCAST_NAME:-Daily Tech Digest}" \
  --tagline "${PODCAST_TAGLINE:-Your morning briefing}" \
  --voice-1 "${PODCAST_VOICE_1:-en-US-AndrewNeural}" \
  --voice-2 "${PODCAST_VOICE_2:-en-US-EmmaNeural}" \
  "$@"

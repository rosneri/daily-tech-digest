#!/usr/bin/env bash
# Render skill/SKILL.md into a ready-to-paste task definition using config.env.
#
# The Claude routine's task definition lives inside the Claude Desktop app, not
# on disk, so this prints the rendered file for you to paste in (or writes it
# with -o).

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_config

OUT=""
[ "${1:-}" = "-o" ] && OUT="${2:?-o needs a path}"

[ -n "${SLACK_CHANNEL_ID:-}" ] || warn "SLACK_CHANNEL_ID is empty in config.env"

rendered=$(sed \
  -e "s|{{DIGEST_HOME}}|${DIGEST_HOME}|g" \
  -e "s|{{REPO_ROOT}}|${REPO_ROOT}|g" \
  -e "s|{{SLACK_CHANNEL_ID}}|${SLACK_CHANNEL_ID:-<SET SLACK_CHANNEL_ID>}|g" \
  -e "s|{{SLACK_MCP_PREFIX}}|${SLACK_MCP_PREFIX:-mcp__slack__}|g" \
  -e "s|{{AI_ENGINEER_FEED}}|${AI_ENGINEER_FEED:-}|g" \
  "$REPO_ROOT/skill/SKILL.md")

if [ -n "$OUT" ]; then
  printf '%s\n' "$rendered" > "$OUT"
  ok "wrote $OUT"
else
  printf '%s\n' "$rendered"
fi

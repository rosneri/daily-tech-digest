"""Render skill/SKILL.md into the Claude routine's task definition.

Replaces scripts/render-skill.sh.
"""

import re
from pathlib import Path

from .config import die, ok, warn

TEMPLATE = "skill/SKILL.md"

# Only a real placeholder, not the `}}` that ends a nested JSON object — the
# skill is full of Block Kit payloads.
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def render(cfg):
    source = cfg.repo_root / TEMPLATE
    if not source.exists():
        die(f"{source} not found")

    if not cfg.slack_user() and not cfg.slack_channel():
        warn("neither SLACK_USER_ID nor SLACK_CHANNEL_ID is set in config.env")

    substitutions = {
        "{{DIGEST_HOME}}": str(cfg.digest_home),
        "{{REPO_ROOT}}": str(cfg.repo_root),
        "{{SLACK_USER_ID}}": cfg.get("SLACK_USER_ID", "<SET SLACK_USER_ID>"),
        "{{SLACK_CHANNEL_ID}}": cfg.get("SLACK_CHANNEL_ID", "<SET SLACK_CHANNEL_ID>"),
        "{{AI_ENGINEER_FEED}}": cfg.get("AI_ENGINEER_FEED", ""),
    }
    text = source.read_text()
    for token, value in substitutions.items():
        text = text.replace(token, value)

    leftover = sorted(set(PLACEHOLDER.findall(text)))
    if leftover:
        warn(f"template still contains unsubstituted placeholders: {' '.join(leftover)}")
    return text


def write(cfg, out_path=None):
    text = render(cfg)
    if not out_path:
        print(text, end="" if text.endswith("\n") else "\n")
        return
    target = Path(out_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text if text.endswith("\n") else text + "\n")
    ok(f"wrote {target}")

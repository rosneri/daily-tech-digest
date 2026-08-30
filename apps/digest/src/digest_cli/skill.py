"""Render skill/SKILL.md into the Claude routine's task definition.

Replaces scripts/render-skill.sh.
"""

from pathlib import Path

from .config import die, ok, warn

TEMPLATE = "skill/SKILL.md"


def render(cfg):
    source = cfg.repo_root / TEMPLATE
    if not source.exists():
        die(f"{source} not found")

    if not cfg.slack_channel():
        warn("SLACK_CHANNEL_ID is empty in config.env")

    substitutions = {
        "{{DIGEST_HOME}}": str(cfg.digest_home),
        "{{REPO_ROOT}}": str(cfg.repo_root),
        "{{SLACK_CHANNEL_ID}}": cfg.get("SLACK_CHANNEL_ID", "<SET SLACK_CHANNEL_ID>"),
        "{{AI_ENGINEER_FEED}}": cfg.get("AI_ENGINEER_FEED", ""),
    }
    text = source.read_text()
    for token, value in substitutions.items():
        text = text.replace(token, value)

    leftover = [t for t in ("{{", "}}") if t in text]
    if leftover:
        warn("template still contains unsubstituted {{...}} placeholders")
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

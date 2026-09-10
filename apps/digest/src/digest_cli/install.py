"""One-shot installer. Safe to re-run: every step is idempotent.

Replaces install.sh.
"""

import json
import shutil

from . import commands
from .config import (CONFIG_FILE, EXAMPLE_FILE, load_config, log, need, ok,
                     warn)


def create_config():
    """Create config.env from the example. Returns True if it was created."""
    if CONFIG_FILE.exists():
        return False
    shutil.copy(EXAMPLE_FILE, CONFIG_FILE)
    ok("created config.env from the example")
    warn("SLACK_CHANNEL_ID is empty — set it in config.env before the digest can post")
    return True


def install(with_podcast=True, with_schedule=True):
    create_config()
    cfg = load_config()

    log("Checking prerequisites")
    need("git")
    need("python3")
    need("uv", "install: curl -LsSf https://astral.sh/uv/install.sh | sh")
    if shutil.which("claude") is None:
        warn("the 'claude' CLI is not on PATH — Horizon scoring and podcast "
             "scripting both need it")
    ok("prerequisites present")

    for directory in (cfg.digests_dir, cfg.podcast_dir):
        directory.mkdir(parents=True, exist_ok=True)

    commands.bootstrap(cfg)

    preferences = cfg.digest_home / "preferences.json"
    if preferences.exists():
        ok("preferences.json exists — left untouched")
    else:
        shutil.copy(cfg.repo_root / "config" / "preferences.json", preferences)
        ok("installed preferences.json")

    favorites = cfg.digest_home / "favorites.json"
    if not favorites.exists():
        favorites.write_text(json.dumps({"favorites": []}) + "\n")

    if with_podcast and cfg.flag("PODCAST_ENABLED", True):
        commands.install_podcast(cfg)
    else:
        log("Skipping podcast install")

    if with_schedule:
        commands.install_schedule(cfg)
    else:
        log("Skipping launchd install")

    slack_ready = cfg.has_slack_token()
    print(f"""
Installed.

  state          {cfg.digest_home}
  horizon        {cfg.horizon_dir}
  summaries      {cfg.summary_dir}
  podcasts       {cfg.podcast_dir}

Next:
  1. Set SLACK_USER_ID in config.env if you have not already.
  2. {'Slack app configured.' if slack_ready else 'Install the Slack app — see docs/slack-app.md, then: digest slack check'}
  3. Try it:  digest run
""")

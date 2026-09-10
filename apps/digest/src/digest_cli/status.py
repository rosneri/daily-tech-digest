"""Inspection and housekeeping commands.

Replaces the Makefile's status / logs / summary / check / clean targets.
"""

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import commands
from .config import CONFIG_FILE, REPO_ROOT, die, ok, resolve_date, warn

TOOLS = ("git", "python3", "uv", "proto", "moon", "claude", "ffmpeg")


def _line(label, value):
    print(f"{label:<12}{value}")


def status(cfg, day=None):
    day = resolve_date(day)
    _line("date", day)
    _line("state", str(cfg.digest_home))

    summary = cfg.summary_path(day)
    _line("summary", f"{summary.stat().st_size} bytes" if summary.exists() else "missing")

    digest_json = cfg.digest_json(day)
    if digest_json.exists():
        data = json.loads(digest_json.read_text())
        _line("digest", f"{data.get('story_count')} stories, source={data.get('source')}")
        thread_ts = data.get("slack_thread_ts")
        _line("thread", thread_ts or "not posted")
    else:
        _line("digest", "missing")

    mp3, size_mb, transcript = commands.locate_podcast(cfg, day)
    _line("podcast", f"{size_mb} MB  {mp3}" if mp3 else "missing")
    _line("transcript", str(transcript) if transcript else "missing")
    _line("schedule", f"{cfg.launchd_label} loaded" if commands.schedule_loaded(cfg)
                   else "not loaded")

    _line("slack", "configured" if cfg.has_slack_token()
                   else "no bot token (see docs/slack-app.md)")


def logs(cfg, lines=40):
    if not cfg.horizon_log.exists():
        print("no log yet")
        return
    tail = cfg.horizon_log.read_text(errors="replace").splitlines()[-lines:]
    print("\n".join(tail))


def summary(cfg, day=None):
    """Print the headline block at the top of a Horizon summary."""
    path = cfg.summary_path(resolve_date(day))
    if not path.exists():
        die(f"no summary for {resolve_date(day)}")
    for line in path.read_text().splitlines():
        print(line)
        if line.strip() == "---":
            break


def check(cfg):
    print("== python syntax")
    sources = sorted(REPO_ROOT.glob("libs/*/src/*/*.py")) + \
        sorted(REPO_ROOT.glob("libs/*/scripts/*.py")) + \
        sorted(REPO_ROOT.glob("libs/*/tests/*.py")) + \
        sorted(REPO_ROOT.glob("apps/*/src/*/*.py")) + [REPO_ROOT / "digest"]
    failures = 0
    for path in sources:
        try:
            ast.parse(path.read_text())
            print(f"  ok {path.relative_to(REPO_ROOT)}")
        except SyntaxError as exc:
            print(f"  -- {path.relative_to(REPO_ROOT)}: {exc}")
            failures += 1

    print("== json")
    for path in sorted((REPO_ROOT / "config").glob("*.json")):
        try:
            json.loads(path.read_text())
            print(f"  ok {path.relative_to(REPO_ROOT)}")
        except json.JSONDecodeError as exc:
            print(f"  -- {path.relative_to(REPO_ROOT)}: {exc}")
            failures += 1

    print("== tools")
    for tool in TOOLS:
        print(f"  ok {tool}" if shutil.which(tool) else f"  -- {tool} (missing)")

    print("== config")
    print(f"  ok {CONFIG_FILE.name}" if CONFIG_FILE.exists()
          else "  -- config.env (run: ./digest config)")
    if cfg:
        if cfg.get("SLACK_USER_ID"):
            print("  ok SLACK_USER_ID (digest is DM'd)")
        elif cfg.get("SLACK_CHANNEL_ID"):
            print("  ok SLACK_CHANNEL_ID (digest goes to the channel)")
        else:
            print("  -- SLACK_USER_ID (unset — see docs/slack-app.md)")
        print(f"  ok SLACK_BOT_TOKEN" if cfg.has_slack_token()
              else "  -- SLACK_BOT_TOKEN (unset — see docs/slack-app.md)")

    print("== workspace")
    for marker in ("pyproject.toml", ".prototools", ".moon/workspace.yml"):
        print(f"  ok {marker}" if (REPO_ROOT / marker).exists() else f"  -- {marker} (missing)")

    print("== analysis profile")
    template = REPO_ROOT / "config" / "profiles" / "tech-news" / "analysis.md"
    print(f"  ok {template.relative_to(REPO_ROOT)}" if template.exists()
          else "  -- config/profiles/tech-news/analysis.md (missing)")

    return 1 if failures else 0


def test():
    """Run the test suite under this interpreter."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(REPO_ROOT)],
        cwd=str(REPO_ROOT)).returncode


def clean(cfg, yes=False):
    """Remove generated podcast artefacts. Keeps digests and summaries."""
    targets = sorted(cfg.podcast_dir.glob("*.mp3"))
    transcripts = cfg.podcast_dir / "transcripts"
    if transcripts.is_dir():
        targets.append(transcripts)
    if not targets:
        print("nothing to clean")
        return
    for path in targets:
        print(f"  {path}")
    if not yes:
        warn("re-run with --yes to delete the paths listed above")
        return
    for path in targets:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    ok(f"removed {len(targets)} podcast artefact(s)")

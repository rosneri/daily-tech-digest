"""Configuration, logging and dependency checks for the CLI.

config.env keeps its shell-compatible KEY="value" format so existing installs
need no migration; parsing it is digest_shellenv's job.
"""

import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from digest_shellenv import parse_file, read_value

# src/digest_cli/config.py -> src/digest_cli -> src -> apps/digest -> apps -> repo
REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_FILE = REPO_ROOT / "config.env"
EXAMPLE_FILE = REPO_ROOT / "config.env.example"

_COLOR = sys.stderr.isatty() and os.environ.get("NO_COLOR") is None


def _paint(code, text):
    return f"\033[0;{code}m{text}\033[0m" if _COLOR else text


def log(msg):
    print(f"{_paint(34, '==>')} {msg}")


def ok(msg):
    print(f"{_paint(32, '  ok')} {msg}")


def warn(msg):
    print(f"{_paint(33, '  !!')} {msg}", file=sys.stderr)


def event(level, message):
    """Adapter for the libs' on_event callbacks, which stay presentation-free."""
    {"log": log, "ok": ok, "warn": warn}.get(level, log)(message)


class DigestError(Exception):
    """Fatal, expected error — reported without a traceback."""


def die(msg):
    raise DigestError(msg)


def need(tool, hint=None):
    """Fail unless `tool` is on PATH."""
    if shutil.which(tool) is None:
        die(f"missing dependency: {tool}" + (f" — {hint}" if hint else ""))
    return shutil.which(tool)


class Config:
    """Resolved settings plus the paths derived from DIGEST_HOME."""

    def __init__(self, values):
        self.values = values
        home = values.get("DIGEST_HOME", "").strip()
        if not home:
            die("DIGEST_HOME must be set in config.env")
        self.digest_home = Path(home).expanduser()
        self.repo_root = REPO_ROOT
        self.horizon_dir = self.digest_home / "horizon"
        self.summary_dir = self.horizon_dir / "data" / "summaries"
        self.digests_dir = self.digest_home / "digests"
        self.podcast_dir = self.digest_home / "podcasts"
        self.horizon_log = self.digest_home / "horizon.log"
        self.podcast_venv = self.digest_home / ".podcast-venv"
        self.generator = REPO_ROOT / "libs" / "podcast" / "scripts" / "generate_podcast.py"

    def get(self, key, default=""):
        value = self.values.get(key, "")
        return value if value != "" else default

    def flag(self, key, default=False):
        value = self.get(key, "true" if default else "false")
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def summary_path(self, day=None):
        return self.summary_dir / f"horizon-{day or today()}-en.md"

    def digest_json(self, day=None):
        return self.digests_dir / (day or today()) / "digest.json"

    @property
    def launchd_label(self):
        return self.get("LAUNCHD_LABEL", "com.dailytechdigest.horizon")

    @property
    def schedule_time(self):
        return int(self.get("HORIZON_HOUR", "6")), int(self.get("HORIZON_MINUTE", "45"))

    def podcast_options(self):
        """The resolved podcastfy settings, with this project's defaults applied."""
        return {
            "max_stories": self.get("PODCAST_MAX_STORIES", "8"),
            "tts_model": self.get("PODCAST_TTS_MODEL", "edge"),
            "script_engine": self.get("PODCAST_SCRIPT_ENGINE", "claude-cli"),
            "llm_model": self.get("PODCAST_LLM_MODEL", "claude-sonnet-5"),
            "llm_api_key_label": self.get("PODCAST_LLM_API_KEY_LABEL", "GEMINI_API_KEY"),
            "name": self.get("PODCAST_NAME", "Daily Tech Digest"),
            "tagline": self.get("PODCAST_TAGLINE", "Your morning briefing"),
            "voice_1": self.get("PODCAST_VOICE_1", "en-US-AndrewNeural"),
            "voice_2": self.get("PODCAST_VOICE_2", "en-US-EmmaNeural"),
        }

    def slack_token(self, override=None):
        """Resolve the bot token: flag, then environment, then config, then file.

        The token file is preferred in docs because config.env is otherwise safe
        to read aloud; both are supported so neither choice is a dead end.
        """
        token = (override or os.environ.get("SLACK_BOT_TOKEN")
                 or self.get("SLACK_BOT_TOKEN") or "").strip()
        if token:
            return token
        token_file = self.get("SLACK_TOKEN_FILE")
        if token_file:
            return read_value(Path(token_file).expanduser(), "SLACK_BOT_TOKEN").strip()
        return ""

    def has_slack_token(self):
        return bool(self.slack_token())

    def slack_channel(self, override=None):
        return (override or os.environ.get("SLACK_CHANNEL_ID")
                or self.get("SLACK_CHANNEL_ID") or "").strip()

    def env_for_subprocess(self):
        """config.env values exported for a child process (Horizon, podcastfy)."""
        return {**os.environ, **{k: str(v) for k, v in self.values.items()}}


def load_config(required=True):
    if not CONFIG_FILE.exists():
        if not required:
            return None
        die("config.env not found. Run: digest config")
    return Config(parse_file(CONFIG_FILE))


def today():
    return date.today().isoformat()


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def resolve_date(value):
    if not value:
        return today()
    if not DATE_RE.match(value):
        die(f"not a YYYY-MM-DD date: {value}")
    return value


def run(cmd, **kwargs):
    """subprocess.run with check=True and a readable failure message."""
    kwargs.setdefault("check", True)
    try:
        return subprocess.run([str(c) for c in cmd], **kwargs)
    except FileNotFoundError:
        die(f"command not found: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        die(f"{cmd[0]} failed (exit {exc.returncode})")

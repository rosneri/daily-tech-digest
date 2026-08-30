"""Managing a macOS launchd user agent.

Plists are built with ``plistlib`` rather than string templates, so quoting and
escaping are the stdlib's problem rather than ours. Knows nothing about digests.
"""

import plistlib
import subprocess
from pathlib import Path

__all__ = ["LaunchAgent", "LaunchdError", "default_path_env"]

AGENT_DIR = Path.home() / "Library" / "LaunchAgents"


class LaunchdError(Exception):
    """launchctl refused an operation, or a plist could not be written."""


def default_path_env():
    """A PATH that includes the usual homebrew/uv locations.

    launchd starts jobs with a minimal PATH that has neither ``uv`` nor
    ``ffmpeg`` on it, which is the single most common reason a job that works in
    a terminal fails at 06:45.
    """
    home = Path.home()
    return f"{home}/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"


class LaunchAgent:
    def __init__(self, label, agent_dir=None):
        self.label = label
        self.path = Path(agent_dir or AGENT_DIR) / f"{label}.plist"

    # -- definition ----------------------------------------------------------

    def definition(self, program_args, hour, minute, stdout=None, stderr=None, env=None):
        plist = {
            "Label": self.label,
            "ProgramArguments": [str(arg) for arg in program_args],
            "StartCalendarInterval": {"Hour": int(hour), "Minute": int(minute)},
            "EnvironmentVariables": {
                "HOME": str(Path.home()),
                "PATH": default_path_env(),
                **(env or {}),
            },
        }
        if stdout:
            plist["StandardOutPath"] = str(stdout)
        if stderr:
            plist["StandardErrorPath"] = str(stderr)
        return plist

    # -- lifecycle -----------------------------------------------------------

    def write(self, plist):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "wb") as handle:
            plistlib.dump(plist, handle)
        return self.path

    def load(self):
        # unload first so the call is idempotent: launchctl errors on a reload
        # of an already-loaded label.
        self.unload()
        result = subprocess.run(["launchctl", "load", str(self.path)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise LaunchdError(f"launchctl load failed: {result.stderr.strip()}")

    def unload(self):
        subprocess.run(["launchctl", "unload", str(self.path)], capture_output=True)

    def install(self, program_args, hour, minute, stdout=None, stderr=None, env=None):
        self.write(self.definition(program_args, hour, minute, stdout, stderr, env))
        self.load()
        return self.path

    def uninstall(self):
        self.unload()
        if self.path.exists():
            self.path.unlink()

    def is_loaded(self):
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        return self.label in result.stdout

    # -- maintenance ---------------------------------------------------------

    def read(self):
        if not self.path.exists():
            raise LaunchdError(f"{self.path} not found")
        with open(self.path, "rb") as handle:
            return plistlib.load(handle)

    def retarget(self, old, new):
        """Rewrite path references inside an installed plist.

        Used when the repo or the state directory moves. Writes a ``.bak`` and
        re-parses afterwards, so a substitution that produces invalid XML fails
        loudly instead of silently breaking the job.
        """
        if not self.path.exists():
            raise LaunchdError(f"{self.path} not found")
        raw = self.path.read_bytes()
        if old.encode() not in raw:
            return None

        backup = self.path.with_suffix(".plist.bak")
        backup.write_bytes(raw)
        self.path.write_bytes(raw.replace(old.encode(), new.encode()))
        try:
            self.read()
        except Exception as exc:
            self.path.write_bytes(raw)
            raise LaunchdError(f"substitution produced an invalid plist ({exc}) — reverted")
        return backup

"""Reading shell-style ``KEY=value`` files without a shell.

``config.env`` and the various ``.env`` files in this project are sourced by
humans in a terminal and by automation that has no shell available. This parser
covers the intersection: quoting, ``export`` prefixes, comments, and ``${VAR}``
references. It deliberately does *not* implement command substitution or
arithmetic — that is why ``config.env`` documents ``LAUNCHD_LABEL`` as needing a
literal value.
"""

import os
import re
from pathlib import Path

__all__ = ["parse", "parse_file", "load_into_environ", "read_value"]

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
_REF = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


def parse(text, base=None):
    """Parse env-file `text` into a dict.

    ``${VAR}`` resolves against `base` (defaulting to the process environment)
    and against keys defined earlier in the same text, matching how a shell
    would evaluate the file top to bottom. Unknown references become empty
    strings rather than raising, again matching the shell.
    """
    scope_base = os.environ if base is None else base
    values = {}
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE.match(raw)
        if not match:
            continue
        key, value = match.group(1), match.group(2)

        if len(value) >= 2 and value[0] == value[-1] == "'":
            values[key] = value[1:-1]  # single quotes: no expansion, by design
            continue
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()  # trailing bare comment

        scope = {**scope_base, **values}
        values[key] = _REF.sub(lambda m: scope.get(m.group(1), ""), value)
    return values


def parse_file(path, base=None, missing_ok=False):
    """Parse the env file at `path`. Returns {} for a missing file if allowed."""
    path = Path(path).expanduser()
    if not path.is_file():
        if missing_ok:
            return {}
        raise FileNotFoundError(path)
    return parse(path.read_text(), base=base)


def load_into_environ(path, override=True, missing_ok=True):
    """Merge an env file into ``os.environ``. Returns the keys that were set.

    With `override` false, existing environment variables win — the usual
    precedence for a file that only supplies defaults.
    """
    values = parse_file(path, missing_ok=missing_ok)
    applied = []
    for key, value in values.items():
        if override or key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    return applied


def read_value(path, key, default=""):
    """Read a single key out of an env file. Convenient for secrets files."""
    return parse_file(path, missing_ok=True).get(key, default)

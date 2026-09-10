"""Turn Horizon's structured items into the digest that gets posted.

This is the half of the job that used to live in a Claude routine's prose. It
can be code now because Horizon already emits everything the digest needs per
item: a score, a one-sentence summary, tags — and, via this project's own
analysis profile, a `cat:` tag naming the section the story belongs in. Nothing
here calls a model.

Knows nothing about Slack transport or the filesystem: items in, digest out,
and a Block Kit payload for each message.
"""

from .categories import CATEGORIES, CATEGORY_IDS, category_of
from .digest import compose
from .render import digest_messages

__all__ = [
    "CATEGORIES",
    "CATEGORY_IDS",
    "category_of",
    "compose",
    "digest_messages",
]

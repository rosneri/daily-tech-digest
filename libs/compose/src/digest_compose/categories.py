"""The digest's sections, and how a Horizon item is assigned to one.

The assignment itself happens upstream, in the analysis profile at
`config/profiles/tech-news/analysis.md`: the model is required to emit exactly
one `cat:<id>` tag from this closed list. Horizon's own `category` field is not
usable for this — it is set per *source*, so every Hacker News, Reddit and RSS
item arrives labelled `tech` no matter what it is about.

`other` is deliberately absent from `CATEGORIES`: it is a valid answer from the
model but not a section anyone wants to read, so those stories are dropped at
composition time rather than rendered under a shrug of a heading.
"""

# Order is the order the sections appear in the digest.
CATEGORIES = (
    ("js-ts", "⚡", "JS/TS ECOSYSTEM"),
    ("ai-ml", "🤖", "AI & ML"),
    ("python", "🐍", "PYTHON ECOSYSTEM"),
    ("sw-eng", "🛠️", "SOFTWARE ENGINEERING"),
    ("web", "🌐", "WEB DEVELOPMENT"),
    ("infra", "☁️", "PLATFORM & INFRA"),
    ("oss", "📦", "OPEN SOURCE"),
)

CATEGORY_IDS = tuple(cid for cid, _, _ in CATEGORIES)
CATEGORY_LABELS = {cid: f"{emoji}  {label}" for cid, emoji, label in CATEGORIES}

OTHER = "other"
TAG_PREFIX = "cat:"


def category_of(tags):
    """Return the `cat:` tag's id, or None when the model did not emit one.

    Tags are matched case-insensitively and with a leading `#` tolerated: the
    prompt asks for `cat:js-ts`, but models drift toward `#cat:js-ts` and the
    difference should not silently cost a story its section.
    """
    for tag in tags or []:
        cleaned = str(tag).strip().lstrip("#").lower()
        if not cleaned.startswith(TAG_PREFIX):
            continue
        category = cleaned[len(TAG_PREFIX):].strip()
        if category in CATEGORY_IDS or category == OTHER:
            return category
    return None

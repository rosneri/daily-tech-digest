"""Normalise a Horizon `ContentItem` dump into the flat story the digest uses.

Horizon's items are faithful to their source: a Hacker News item carries points
and a discussion URL, an RSS item carries its feed's name, a GitHub item carries
a repo. The digest wants one shape, so the per-source knowledge is confined to
`source_label` and `points` here rather than spread through rendering.
"""

from .categories import category_of

SOURCE_NAMES = {
    "hackernews": "Hacker News",
    "ossinsight": "OSS Insight",
    "google_news": "Google News",
    "twitter": "X",
}


def source_label(item):
    """A human name for where a story came from."""
    source_type = item.get("source_type", "")
    metadata = item.get("metadata") or {}
    if source_type == "rss":
        return metadata.get("feed_name") or "RSS"
    if source_type == "reddit":
        subreddit = metadata.get("subreddit")
        return f"r/{subreddit}" if subreddit else "Reddit"
    if source_type == "github":
        return metadata.get("repo") or "GitHub"
    return SOURCE_NAMES.get(source_type, source_type.replace("_", " ").title() or "Source")


def points(item):
    """Community score, where the source has one that means anything.

    Only Hacker News and Reddit rank by votes; an RSS `score` would be a feed
    quirk, not a signal, so it is ignored.
    """
    if item.get("source_type") not in ("hackernews", "reddit"):
        return None
    value = (item.get("metadata") or {}).get("score")
    return value if isinstance(value, int) and value > 0 else None


def to_story(item):
    """Flatten one analysed Horizon item. Returns None if it was never analysed.

    An unanalysed item has no score, no summary and no category, so it cannot be
    placed or ranked — that only happens if a stage was skipped, and dropping it
    is better than rendering a story with an empty body.
    """
    analysis = ((item.get("processing") or {}).get("analysis")) or {}
    summary = (analysis.get("summary") or "").strip()
    if not summary:
        return None

    tags = [str(t).strip().lstrip("#") for t in analysis.get("tags") or []]
    return {
        "id": item.get("id"),
        "title": (item.get("title") or "").strip(),
        "url": str(item.get("url") or ""),
        "summary": summary,
        "score": analysis.get("score"),
        "category": category_of(tags),
        "tags": [t for t in tags if not t.lower().startswith("cat:")],
        "source": source_label(item),
        "discussion_url": (item.get("metadata") or {}).get("discussion_url"),
        "points": points(item),
        "published_at": item.get("published_at"),
    }

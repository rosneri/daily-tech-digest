"""Compose today's digest and deliver it — the whole editorial step, in code.

This replaces the Claude routine that used to read Horizon's markdown, sort
stories into sections by hand, rewrite each one and drive the Slack CLI message
by message. Horizon now labels every item with a `cat:` tag and a one-sentence
summary, so nothing here needs a model.

Order matters and is not arbitrary: feedback for *yesterday* is collected before
today's thread is posted, because both read the same DM and the earlier the
lookup runs the less there is to page through.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import digest_compose
from digest_slack import SlackClient, SlackError

from .config import DigestError, die, event, log, ok, resolve_date, warn

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def date_label(day):
    parsed = date.fromisoformat(day)
    return f"{MONTHS[parsed.month - 1]} {parsed.day}, {parsed.year}"


def _read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        warn(f"{path} is not valid JSON ({exc}) — ignoring")
        return default


def _client(cfg):
    token = cfg.slack_token()
    if not token:
        die("no Slack bot token — see docs/slack-app.md")
    channel, user = cfg.slack_target()
    return SlackClient(token, channel or None, user or None)


def compose_digest(cfg, day):
    """Build the digest for `day` from that run's archived Horizon items."""
    items_file = Path(cfg.digests_dir) / day / "horizon-items.json"
    items = _read_json(items_file)
    if items is None:
        die(f"no Horizon items for {day} at {items_file} — run: digest run --date {day}")

    digest = digest_compose.compose(
        items,
        preferences=_read_json(cfg.digest_home / "preferences.json", {}),
        favorites=_read_json(cfg.digest_home / "favorites.json", {}),
        max_stories=cfg.max_stories,
        ai_share=cfg.ai_share,
    )
    if not digest["stories"]:
        die(f"composed 0 stories from {len(items)} items — refusing to post an empty digest")
    return digest


def post_digest(client, digest, day, podcast=None):
    """Send the thread. Returns the parent ts and each story's message ts."""
    messages = digest_compose.digest_messages(
        digest, date_label(day), has_podcast=bool(podcast))

    thread_ts = None
    story_ts = {}
    for message in messages:
        result = client.post(message["text"], blocks=message["blocks"],
                             thread_ts=thread_ts, unfurl=False)
        if thread_ts is None:
            thread_ts = result["ts"]
        if "story_number" in message:
            story_ts[message["story_number"]] = result["ts"]
    return thread_ts, story_ts


def upload_podcast(client, cfg, day, thread_ts):
    """Attach the episode to the thread. Never fatal — audio is a nice-to-have."""
    from . import commands

    mp3, size_mb, _ = commands.locate_podcast(cfg, day)
    if not mp3:
        return None
    try:
        result = client.upload_file(
            mp3, title=f"Daily Tech Digest — {date_label(day)}", thread_ts=thread_ts,
            comment="🎧 *Audio edition* — a ~5-8 min briefing of today's top stories.")
    except SlackError as exc:
        warn(f"podcast upload failed ({exc}) — the written digest is unaffected")
        return None
    return {"available": True, "path": str(mp3), "size_mb": result.get("size_mb", size_mb),
            "slack_permalink": result.get("permalink")}


def collect_feedback(client, cfg, day):
    """Fold yesterday's reactions and replies into favorites.json.

    Exact, not heuristic: yesterday's digest.json records the Slack `ts` of
    every story message, so a reaction maps back to its story by message id
    rather than by guessing from position in the thread.
    """
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    previous = _read_json(Path(cfg.digests_dir) / yesterday / "digest.json")
    if not previous or not previous.get("slack_thread_ts"):
        return 0

    by_ts = {s["slack_ts"]: s for s in previous.get("stories", []) if s.get("slack_ts")}
    if not by_ts:
        # Digests written before per-story ts existed cannot be matched safely.
        return 0

    try:
        messages = client.read_thread(previous["slack_thread_ts"])
    except SlackError as exc:
        warn(f"could not read yesterday's thread ({exc}) — skipping feedback")
        return 0

    # A human reply lands under the parent, not under the story it is about, so
    # attribute it to the story message immediately preceding it in the thread.
    liked = {}
    last_story_ts = None
    for message in messages:
        if message["ts"] in by_ts:
            last_story_ts = message["ts"]
            for reaction in message["reactions"]:
                liked.setdefault(message["ts"], {})["reaction"] = reaction["name"]
        elif not message["is_bot"] and message["text"].strip() and last_story_ts:
            liked.setdefault(last_story_ts, {})["comment"] = message["text"].strip()

    if not liked:
        return 0

    favorites_file = Path(cfg.digest_home) / "favorites.json"
    favorites = _read_json(favorites_file, {}) or {}
    entries = favorites.setdefault("favorites", [])
    for ts, signal in liked.items():
        story = by_ts[ts]
        entries.append({
            "date": yesterday,
            "title": story.get("title"),
            "url": story.get("url"),
            "category": story.get("category"),
            "tags": story.get("tags", []),
            "source": story.get("source"),
            "reaction": signal.get("reaction"),
            "comment": signal.get("comment"),
        })
    favorites_file.write_text(json.dumps(favorites, indent=2, ensure_ascii=False))
    return len(liked)


def save_digest(cfg, day, digest, thread_ts, story_ts, podcast):
    """Archive the digest. `slack_ts` per story is what tomorrow's run reads."""
    folder = Path(cfg.digests_dir) / day
    folder.mkdir(parents=True, exist_ok=True)

    stories = []
    for story in digest["stories"]:
        stories.append({**{k: v for k, v in story.items() if k != "rank"},
                        "slack_ts": story_ts.get(story["number"])})

    payload = {
        "date": day,
        "story_count": len(stories),
        "source": "horizon",
        "slack_thread_ts": thread_ts,
        "podcast": podcast or {"available": False},
        "categories": digest["counts"],
        "dropped": digest["dropped"],
        "stories": stories,
    }
    (folder / "digest.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    summary = cfg.summary_path(day)
    if summary.exists():
        (folder / summary.name).write_text(summary.read_text())

    preferences_file = Path(cfg.digest_home) / "preferences.json"
    preferences = _read_json(preferences_file)
    if preferences is not None:
        preferences["lastDigestDate"] = day
        preferences_file.write_text(json.dumps(preferences, indent=2, ensure_ascii=False))
    return folder / "digest.json"


def deliver(cfg, day=None, dry_run=False):
    day = resolve_date(day)
    digest = compose_digest(cfg, day)
    counts = ", ".join(f"{k}={v}" for k, v in digest["counts"].items())
    ok(f"composed {len(digest['stories'])} stories ({counts})")
    if digest["dropped"]["uncategorised"]:
        warn(f"{digest['dropped']['uncategorised']} items had no usable cat: tag")

    if dry_run:
        print(json.dumps(digest_compose.digest_messages(digest, date_label(day)),
                         indent=2, ensure_ascii=False))
        return 0

    client = _client(cfg)

    try:
        collected = collect_feedback(client, cfg, day)
        if collected:
            ok(f"recorded {collected} liked stories from yesterday")
    except (DigestError, OSError) as exc:
        # Feedback must never block the digest it precedes.
        warn(f"feedback step failed ({exc}) — continuing")

    from . import commands
    mp3, _, _ = commands.locate_podcast(cfg, day)

    thread_ts, story_ts = post_digest(client, digest, day, podcast=mp3)
    ok(f"posted {len(story_ts)} stories to thread {thread_ts}")

    podcast = upload_podcast(client, cfg, day, thread_ts) if mp3 else None
    path = save_digest(cfg, day, digest, thread_ts, story_ts, podcast)
    ok(f"saved {path}")
    return 0

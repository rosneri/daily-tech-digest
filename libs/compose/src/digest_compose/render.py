"""Render a composed digest as the sequence of Slack messages to send.

Each message is `{"text": ..., "blocks": [...]}`: `text` is the notification
fallback Slack shows in the push and the sidebar, `blocks` is what renders. One
story per message, because the feedback step reads reactions per message.

Emitting the whole sequence up front, rather than posting as it goes, keeps this
module free of transport and makes the digest testable as a value.
"""

from .categories import CATEGORY_LABELS

# Slack's own limits. A header over 150 characters or a section over 3000 is
# rejected outright with `invalid_blocks`, which would fail the whole digest
# over one verbose story — so text is trimmed to fit rather than sent as-is.
HEADER_LIMIT = 150
SECTION_LIMIT = 3000
TITLE_LIMIT = 200


def _trim(text, limit=HEADER_LIMIT):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _plain(text):
    return {"type": "plain_text", "text": _trim(text), "emoji": True}


def _mrkdwn(text):
    return {"type": "mrkdwn", "text": text}


def _context(text):
    return {"type": "context", "elements": [_mrkdwn(text)]}


def header_message(date_label, story_count, section_count, has_podcast):
    parts = [f"*{date_label}*", f"{story_count} stories", f"{section_count} sections"]
    if has_podcast:
        parts.append("🎧 Podcast")
    return {
        "text": f"🗞️ Daily Tech Digest — {date_label} · {story_count} stories",
        "blocks": [
            {"type": "header", "text": _plain("🗞️  Daily Tech Digest")},
            _context("  ·  ".join(parts)),
            {"type": "divider"},
        ],
    }


def section_message(category):
    label = CATEGORY_LABELS[category]
    return {"text": label, "blocks": [{"type": "header", "text": _plain(label)}]}


def story_message(story):
    """A story: headline and summary in one section, provenance in a context."""
    meta = []
    if story.get("points"):
        meta.append(f"🔶 {story['points']}")
    if story.get("url"):
        meta.append(f"<{story['url']}|{story['source']}>")
    else:
        meta.append(story["source"])
    if story.get("discussion_url") and story["discussion_url"] != story.get("url"):
        meta.append(f"<{story['discussion_url']}|Discussion>")

    title = _trim(story["title"], TITLE_LIMIT)
    body = f"*{story['number']}. {title}*\n{story['summary']}"
    blocks = [{"type": "section", "text": _mrkdwn(_trim(body, SECTION_LIMIT))}]
    if meta:
        blocks.append(_context("  ·  ".join(meta)))
    return {"text": _trim(f"{story['number']}. {story['title']}"), "blocks": blocks}


def footer_message(story_count, section_count, has_podcast):
    parts = [f"{story_count} stories from Horizon", f"{section_count} sections"]
    if has_podcast:
        parts.append("🎧 audio in this thread")
    parts.append("react to a story, or reply _more on [number]_")
    return {
        "text": f"{story_count} stories · react or reply to teach the digest",
        "blocks": [{"type": "divider"}, _context("  ·  ".join(parts))],
    }


def digest_messages(digest, date_label, has_podcast=False):
    """The full send sequence. The first message is the thread parent.

    Story messages carry `story_number` so the caller can record the Slack `ts`
    each one lands at, which is what makes the next day's feedback lookup exact
    instead of a guess at which reply was which story.
    """
    sections = digest["sections"]
    story_count = len(digest["stories"])
    messages = [header_message(date_label, story_count, len(sections), has_podcast)]
    for section in sections:
        messages.append(section_message(section["category"]))
        for story in section["stories"]:
            message = story_message(story)
            message["story_number"] = story["number"]
            messages.append(message)
    messages.append(footer_message(story_count, len(sections), has_podcast))
    return messages

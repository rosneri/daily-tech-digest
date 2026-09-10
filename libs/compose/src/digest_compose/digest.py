"""Rank, cap and order the stories — the editorial rules, as arithmetic.

Two rules from `preferences.json` survive the move out of a Claude routine
because they were always mechanical: tag preferences (`wantMore`, `wantLess`,
`focus`) shift a story's rank, and the AI/ML share cap bounds how much of the
digest one section can take. Both are applied here.

The rules that needed judgement — spot this week's conferences, watch named
developers' GitHub activity — are not here and cannot be. See docs/composing.md.
"""

import math
from collections import Counter

from .categories import CATEGORY_IDS, OTHER
from .items import to_story

# Rank adjustments, in score points on Horizon's 0-10 scale. Deliberately small:
# they break ties between comparable stories, they do not overturn the model's
# judgement of what matters.
WANT_MORE_BONUS = 0.4
FOCUS_BONUS = 0.3
WANT_LESS_PENALTY = 0.8
FAVOURITE_BONUS = 0.2
MAX_PREFERENCE_SHIFT = 1.5


def _normalise(values):
    return {str(v).strip().lower() for v in values or [] if str(v).strip()}


def favourite_affinity(favorites):
    """Tags the user has actually engaged with, weighted by how often.

    Reads the same `favorites.json` the feedback step appends to. A tag seen
    once is weak evidence, so the weight is capped rather than linear.
    """
    counter = Counter()
    for entry in (favorites or {}).get("favorites", []):
        for tag in _normalise(entry.get("tags")):
            counter[tag] += 1
    return counter


def rank(story, preferences, affinity):
    """The story's score after preferences, bounded so it stays a tie-breaker."""
    base = story.get("score")
    if base is None:
        return 0.0
    tags = _normalise(story.get("tags"))

    shift = 0.0
    if tags & _normalise(preferences.get("wantMore")):
        shift += WANT_MORE_BONUS
    if tags & _normalise(preferences.get("focus")):
        shift += FOCUS_BONUS
    if tags & _normalise(preferences.get("wantLess")):
        shift -= WANT_LESS_PENALTY
    if affinity and any(affinity.get(tag) for tag in tags):
        shift += FAVOURITE_BONUS

    shift = max(-MAX_PREFERENCE_SHIFT, min(MAX_PREFERENCE_SHIFT, shift))
    return float(base) + shift


def select(stories, max_stories, ai_share):
    """Take the best `max_stories`, with AI/ML held to `ai_share` of them.

    The cap is computed against the digest's final size, not the candidate pool,
    so a quiet day of mostly-AI news still yields a digest that is 40% AI rather
    than 40% of everything available.
    """
    ordered = sorted(stories, key=lambda s: s["rank"], reverse=True)
    if max_stories is not None:
        ordered_cap = min(max_stories, len(ordered))
    else:
        ordered_cap = len(ordered)

    ai_budget = math.floor(ordered_cap * ai_share) if ai_share is not None else None
    chosen, ai_taken, deferred = [], 0, []
    for story in ordered:
        if len(chosen) >= ordered_cap:
            break
        if story["category"] == "ai-ml" and ai_budget is not None:
            if ai_taken >= ai_budget:
                deferred.append(story)
                continue
            ai_taken += 1
        chosen.append(story)

    # A thin day can leave the digest short of its cap with AI stories to spare;
    # an under-filled digest is worse than an over-weighted one.
    for story in deferred:
        if len(chosen) >= ordered_cap:
            break
        chosen.append(story)
    return chosen


def order(stories):
    """Group into sections in CATEGORIES order, best story first, and number."""
    sections = []
    number = 1
    for category in CATEGORY_IDS:
        members = sorted((s for s in stories if s["category"] == category),
                         key=lambda s: s["rank"], reverse=True)
        if not members:
            continue
        for story in members:
            story["number"] = number
            number += 1
        sections.append({"category": category, "stories": members})
    return sections


def compose(items, preferences=None, favorites=None, max_stories=None, ai_share=0.4):
    """Items from Horizon in, a ready-to-render digest out."""
    preferences = preferences or {}
    affinity = favourite_affinity(favorites)

    stories, uncategorised = [], 0
    for item in items:
        story = to_story(item)
        if story is None:
            continue
        if story["category"] in (None, OTHER):
            uncategorised += 1
            continue
        story["rank"] = round(rank(story, preferences, affinity), 3)
        stories.append(story)

    sections = order(select(stories, max_stories, ai_share))
    return {
        "sections": sections,
        "stories": [s for section in sections for s in section["stories"]],
        "counts": {section["category"]: len(section["stories"]) for section in sections},
        "dropped": {"uncategorised": uncategorised,
                    "over_cap": len(stories) - sum(len(s["stories"]) for s in sections)},
    }

"""Composition rules: the editorial policy, now that it is arithmetic."""

import pytest

from digest_compose import CATEGORY_IDS, category_of, compose, digest_messages
from digest_compose.items import source_label, to_story


def item(title="A story", category="js-ts", score=6.0, tags=(), **overrides):
    analysis_tags = ([f"cat:{category}"] if category else []) + list(tags)
    payload = {
        "id": f"rss:{title}",
        "source_type": "rss",
        "title": title,
        "url": "https://example.com",
        "metadata": {"feed_name": "InfoQ"},
        "processing": {"analysis": {"score": score, "summary": f"{title} happened.",
                                    "tags": analysis_tags}},
    }
    payload.update(overrides)
    return payload


# -- categories --------------------------------------------------------------

def test_category_tag_is_read_however_the_model_writes_it():
    assert category_of(["cat:js-ts"]) == "js-ts"
    assert category_of(["#cat:AI-ML"]) == "ai-ml"
    assert category_of(["nodejs", "cat:python"]) == "python"


def test_an_unknown_or_missing_category_is_not_guessed():
    assert category_of(["cat:blockchain"]) is None
    assert category_of(["nodejs"]) is None
    assert category_of([]) is None


def test_uncategorised_and_other_items_are_dropped_and_counted():
    digest = compose([item(category=None), item(category="other"), item()])
    assert len(digest["stories"]) == 1
    assert digest["dropped"]["uncategorised"] == 2


# -- normalisation -----------------------------------------------------------

def test_source_label_per_source_type():
    assert source_label({"source_type": "rss", "metadata": {"feed_name": "InfoQ"}}) == "InfoQ"
    assert source_label({"source_type": "hackernews", "metadata": {}}) == "Hacker News"
    assert source_label({"source_type": "reddit", "metadata": {"subreddit": "rust"}}) == "r/rust"
    assert source_label({"source_type": "github", "metadata": {"repo": "nodejs/node"}}) == "nodejs/node"


def test_points_only_count_where_votes_mean_something():
    # An RSS `score` is a feed quirk, not a community signal.
    assert to_story(item(source_type="hackernews", metadata={"score": 412}))["points"] == 412
    assert to_story(item(metadata={"feed_name": "InfoQ", "score": 9}))["points"] is None


def test_an_unanalysed_item_is_not_a_story():
    assert to_story({"title": "x", "processing": {}}) is None


def test_the_category_tag_is_not_shown_as_a_topic_tag():
    story = to_story(item(tags=["nodejs"]))
    assert story["tags"] == ["nodejs"]


# -- ranking -----------------------------------------------------------------

def test_preferences_shift_rank_without_overturning_the_score():
    stories = compose([item("Wanted", score=6.0, tags=["nodejs"]),
                       item("Better", score=8.0)],
                      preferences={"wantMore": ["nodejs"]})["stories"]
    assert [s["title"] for s in stories] == ["Better", "Wanted"]
    assert stories[1]["rank"] == 6.4


def test_want_less_demotes():
    stories = compose([item("Boring", score=7.0, tags=["crypto"]), item("Fine", score=6.5)],
                      preferences={"wantLess": ["crypto"]})["stories"]
    assert [s["title"] for s in stories] == ["Fine", "Boring"]


def test_favourites_boost_tags_you_engaged_with():
    favorites = {"favorites": [{"tags": ["deno"]}]}
    stories = compose([item("Seen", score=6.0, tags=["deno"]), item("Unseen", score=6.0)],
                      favorites=favorites)["stories"]
    assert stories[0]["title"] == "Seen"


def test_preference_shift_is_bounded():
    story = compose([item(score=6.0, tags=["a", "b", "c"])],
                    preferences={"wantMore": ["a"], "focus": ["b"]},
                    favorites={"favorites": [{"tags": ["c"]}]})["stories"][0]
    assert story["rank"] <= 7.5


# -- selection ---------------------------------------------------------------

def test_ai_share_is_capped_against_the_final_length():
    items = [item(f"AI {i}", category="ai-ml", score=9.0) for i in range(8)]
    items += [item(f"JS {i}", category="js-ts", score=5.0) for i in range(8)]
    digest = compose(items, max_stories=10, ai_share=0.4)
    assert digest["counts"]["ai-ml"] == 4
    assert len(digest["stories"]) == 10


def test_a_thin_day_fills_the_digest_rather_than_holding_the_quota():
    # Only AI stories exist: an under-filled digest is worse than a skewed one.
    digest = compose([item(f"AI {i}", category="ai-ml") for i in range(5)],
                     max_stories=5, ai_share=0.4)
    assert len(digest["stories"]) == 5


def test_max_stories_caps_the_digest():
    assert len(compose([item(f"S{i}") for i in range(20)], max_stories=6)["stories"]) == 6


# -- ordering ----------------------------------------------------------------

def test_sections_follow_the_fixed_order_and_numbering_is_continuous():
    digest = compose([item("Infra", category="infra"), item("JS", category="js-ts"),
                      item("AI", category="ai-ml")])
    assert [s["category"] for s in digest["sections"]] == ["js-ts", "ai-ml", "infra"]
    assert [s["number"] for s in digest["stories"]] == [1, 2, 3]
    assert digest["stories"][0]["title"] == "JS"


def test_category_ids_match_the_prompt_vocabulary():
    prompt = (__file__.rsplit("/libs/", 1)[0] + "/config/profiles/tech-news/analysis.md")
    text = open(prompt).read()
    for category in CATEGORY_IDS:
        assert f"`cat:{category}`" in text, f"{category} is missing from the analysis prompt"


# -- rendering ---------------------------------------------------------------

def test_every_message_carries_blocks_and_a_fallback():
    digest = compose([item("JS", category="js-ts"), item("AI", category="ai-ml")])
    messages = digest_messages(digest, "September 9, 2026")
    assert len(messages) == 1 + 2 * 2 + 1  # header + (section + story) * 2 + footer
    for message in messages:
        assert message["text"].strip()
        assert message["blocks"]
        assert len(message["blocks"]) <= 50


def test_story_messages_are_tagged_with_their_number():
    digest = compose([item("JS")])
    numbers = [m["story_number"] for m in digest_messages(digest, "x") if "story_number" in m]
    assert numbers == [1]


def test_a_story_renders_its_provenance_in_a_context_block():
    digest = compose([item("JS", source_type="hackernews",
                           metadata={"score": 412, "discussion_url": "https://hn"})])
    story = [m for m in digest_messages(digest, "x") if "story_number" in m][0]
    context = story["blocks"][1]["elements"][0]["text"]
    assert "🔶 412" in context and "<https://hn|Discussion>" in context


def test_long_text_is_trimmed_to_slack_limits_not_rejected():
    # One verbose story must not fail the whole digest with `invalid_blocks`.
    digest = compose([item("x" * 400)])
    digest["stories"][0]["summary"] = "y" * 5000
    message = [m for m in digest_messages(digest, "x") if "story_number" in m][0]
    assert len(message["blocks"][0]["text"]["text"]) <= 3000
    assert len(message["text"]) <= 150

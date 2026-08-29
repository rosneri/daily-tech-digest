#!/usr/bin/env python3
"""Tests for transcript normalisation.

podcastfy validates that a transcript is strictly alternating
<Person1>/<Person2> pairs and raises otherwise, so a small formatting slip from
the model would otherwise fail the whole run. normalise_transcript() is the
thing standing between "the model was slightly sloppy" and "no podcast today",
so it needs to hold up against realistic malformed output.

Run with: make test
"""

import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gp", ROOT / "scripts" / "generate_podcast.py")
gp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gp)

PAIR_RE = re.compile(r"<Person1>.*?</Person1>\s*<Person2>.*?</Person2>", re.S)


def assert_valid(out: str, label: str) -> None:
    """Assert `out` satisfies every constraint podcastfy enforces."""
    seq = re.findall(r"<Person([12])>", out)
    assert seq, f"{label}: no turns produced"
    assert seq[0] == "1", f"{label}: must start with Person1, got {seq[0]}"
    assert len(seq) % 2 == 0, f"{label}: odd number of turns ({len(seq)})"
    assert all(seq[i] != seq[i + 1] for i in range(len(seq) - 1)), \
        f"{label}: turns not alternating ({''.join(seq)})"
    for n in (1, 2):
        assert out.count(f"<Person{n}>") == out.count(f"</Person{n}>"), \
            f"{label}: unbalanced Person{n} tags"
    assert len(PAIR_RE.findall(out)) == len(seq) // 2, \
        f"{label}: does not match podcastfy's pair regex"


CASES = {
    # The one that bit us in practice: a missing close tag makes the non-greedy
    # match swallow the inner tag into the captured text.
    "nested stray tag":
        "<Person1>a</Person1><Person2>b<Person2>c</Person2>"
        "<Person1>d</Person1><Person2>e</Person2>",
    "consecutive same speaker":
        "<Person1>a</Person1><Person1>b</Person1><Person2>c</Person2>",
    "starts with Person2":
        "<Person2>hi</Person2><Person1>a</Person1><Person2>b</Person2>",
    "trailing unpaired turn":
        "<Person1>a</Person1><Person2>b</Person2><Person1>c</Person1>",
    "wrapped in a code fence":
        "```\n<Person1>a</Person1><Person2>b</Person2>\n```",
    "newlines between turns":
        "<Person1>a</Person1>\n\n<Person2>b</Person2>\n",
    "empty turns dropped":
        "<Person1>a</Person1><Person2></Person2><Person2>b</Person2>",
}


def test_normalisation():
    for label, raw in CASES.items():
        assert_valid(gp.normalise_transcript(raw), label)
        print(f"  ok  {label}")


def test_rejects_untagged_output():
    for label, raw in {
        "prose with no tags": "Person 1: hello. Person 2: hi.",
        "empty string": "",
    }.items():
        try:
            gp.normalise_transcript(raw)
        except gp.GenerationError:
            print(f"  ok  rejects {label}")
        else:
            raise AssertionError(f"should have rejected {label}")


def test_parse_summary_rejects_empty_digest(tmp: pathlib.Path):
    """An empty Horizon summary must not silently yield a zero-story podcast."""
    p = tmp / "horizon-2026-01-01-en.md"
    p.write_text(
        "# Horizon Daily - 2026-01-01\n\n"
        "> Analyzed 102 items, but none met the importance threshold.\n"
    )
    try:
        gp.parse_summary(p, 8)
    except gp.GenerationError:
        print("  ok  rejects an empty summary")
    else:
        raise AssertionError("should have rejected an empty summary")


def test_parse_summary_extracts_stories(tmp: pathlib.Path):
    p = tmp / "horizon-2026-01-02-en.md"
    p.write_text(
        "# Horizon Daily\n\n"
        '<a id="item-tech-news-1"></a>\n'
        "### [Low score story](https://example.com/b) ⭐️ 6.0/10\n\n"
        "Body of the low one.\n\n"
        "tags\n\n"
        '<a id="item-tech-news-2"></a>\n'
        "### [High score story](https://example.com/a) ⭐️ 9.0/10\n\n"
        "Body of the high one.\n\n"
        "tags\n"
    )
    stories = gp.parse_summary(p, 8)
    assert len(stories) == 2, stories
    assert stories[0]["score"] == 9.0, "must be sorted by score descending"
    assert stories[0]["title"] == "High score story"
    assert stories[0]["url"] == "https://example.com/a"
    print("  ok  parses and ranks stories")

    capped = gp.parse_summary(p, 1)
    assert len(capped) == 1 and capped[0]["score"] == 9.0
    print("  ok  honours max_stories")


def main() -> int:
    import tempfile
    print("transcript normalisation")
    test_normalisation()
    test_rejects_untagged_output()
    print("summary parsing")
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        test_parse_summary_rejects_empty_digest(tmp)
        test_parse_summary_extracts_stories(tmp)
    print("\nall tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

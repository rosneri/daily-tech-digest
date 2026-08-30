#!/usr/bin/env python3
"""Turn a Horizon daily summary into a podcast episode via podcastfy.

podcastfy (https://github.com/souzatharsis/podcastfy, Apache-2.0) normally does
two jobs: write a two-host conversation with an LLM, then speak it with a TTS
engine. Its LLM step wants an API key.

This project already authenticates to Claude through the logged-in `claude` CLI
(that is how Horizon scores stories), so by default we write the script with
that CLI and hand podcastfy a finished transcript. Combined with Edge TTS, the
whole podcast path needs no API key at all. Set PODCAST_SCRIPT_ENGINE=podcastfy
to use podcastfy's own LLM instead.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

# podcastfy validates that the transcript is strictly alternating
# <Person1>…</Person1><Person2>…</Person2> pairs, so we must match that exactly.
TURN_RE = re.compile(r"<Person([12])>(.*?)</Person\1>", re.S)
STRAY_TAG_RE = re.compile(r"</?Person[12]>")
WHITESPACE_RE = re.compile(r"\s+")


class GenerationError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Parsing Horizon's summary
# --------------------------------------------------------------------------

def _unescape(text: str) -> str:
    """Horizon escapes markdown for rendering; undo it for speech."""
    return html.unescape(re.sub(r"\\(.)", r"\1", text)).strip()


def parse_summary(path: Path, max_stories: int) -> list[dict]:
    """Extract the top stories from a Horizon summary markdown file."""
    md = path.read_text(encoding="utf-8")

    if "none met the importance threshold" in md:
        raise GenerationError(
            f"{path.name} contains no stories. Horizon found nothing above the "
            "score threshold, so there is nothing to narrate."
        )

    stories: list[dict] = []
    for block in re.split(r'\n<a id="item-', md)[1:]:
        head = re.search(r"###\s*\[(.+?)\]\((.+?)\)\s*⭐️\s*([\d.]+)/10", block, re.S)
        if not head:
            continue
        body = re.search(r"⭐️\s*[\d.]+/10\n\n(.+?)\n\n", block, re.S)
        stories.append(
            {
                "title": _unescape(head.group(1)),
                "url": head.group(2),
                "score": float(head.group(3)),
                "summary": _unescape(body.group(1)) if body else "",
            }
        )

    if not stories:
        raise GenerationError(f"could not parse any stories out of {path}")

    stories.sort(key=lambda s: -s["score"])
    return stories[:max_stories]


# --------------------------------------------------------------------------
# Writing the script
# --------------------------------------------------------------------------

def build_prompt(stories: list[dict], day: str, cfg: dict) -> str:
    briefing = "\n\n".join(
        f"{i}. {s['title']} (score {s['score']:.1f}/10)\n{s['summary']}"
        for i, s in enumerate(stories, 1)
    )
    return f"""Write a two-host podcast script for {cfg['name']} covering {day}.

Host 1 introduces each story and explains it. Host 2 asks the questions a working
software engineer would actually ask, and draws out why a story matters.

Rules:
- Output ONLY the script. No preamble, no commentary, no markdown fences.
- Wrap every turn in <Person1></Person1> or <Person2></Person2> tags.
- Turns MUST alternate, starting with Person1 and ending with Person2. Never put
  two turns by the same person in a row.
- Open by naming the show ("{cfg['name']}") and the date. Close with a sign-off.
- Cover all {len(stories)} stories below, in order, roughly a minute each.
- This is spoken audio: no URLs, no bullet points, no version numbers read
  digit by digit. Expand abbreviations the first time you use them.
- Keep it warm and concrete. Do not invent facts beyond what is given.

Today's stories:

{briefing}"""


def script_via_claude_cli(prompt: str, model: str) -> str:
    """Generate the script with the locally authenticated `claude` CLI."""
    exe = shutil.which("claude") or next(
        (
            p
            for p in (
                "/usr/local/bin/claude",
                os.path.expanduser("~/.claude/local/claude"),
                "/opt/homebrew/bin/claude",
            )
            if os.path.isfile(p) and os.access(p, os.X_OK)
        ),
        None,
    )
    if not exe:
        raise GenerationError(
            "`claude` CLI not found. Install Claude Code, or set "
            "PODCAST_SCRIPT_ENGINE=podcastfy to use podcastfy's own LLM."
        )

    result = subprocess.run(
        [exe, "-p", prompt, "--model", model],
        capture_output=True,
        text=True,
        timeout=600,
        # The CLI otherwise stalls 3s per call waiting on stdin it never gets,
        # and can block outright on an inherited tty under launchd.
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        # The CLI reports usage limits and auth failures on stdout, not stderr.
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise GenerationError(f"claude CLI exited {result.returncode}: {detail[:400]}")
    return result.stdout.strip()


def normalise_transcript(raw: str) -> str:
    """Coerce the model's output into the strict alternation podcastfy requires.

    Merges consecutive same-speaker turns and drops a trailing unpaired turn, so
    a small formatting slip does not fail the whole run.
    """
    raw = re.sub(r"^```[a-z]*\n|```$", "", raw.strip(), flags=re.M)

    # A malformed turn like "<Person2>a<Person2>b</Person2>" makes the non-greedy
    # match swallow the inner tag into the captured text, which would then be
    # re-emitted and break the alternation we are trying to guarantee. Strip any
    # stray speaker tags out of the content.
    turns = [
        (m.group(1), STRAY_TAG_RE.sub(" ", m.group(2)).strip())
        for m in TURN_RE.finditer(raw)
    ]
    if not turns:
        raise GenerationError(
            "model output contained no <Person1>/<Person2> tags; cannot build a transcript"
        )

    merged: list[list[str]] = []
    for speaker, text in turns:
        if not text:
            continue
        if merged and merged[-1][0] == speaker:
            merged[-1][1] += " " + text
        else:
            merged.append([speaker, text])

    if merged and merged[0][0] != "1":
        merged.insert(0, ["1", "Welcome in."])
    if len(merged) % 2:
        merged.pop()
    if not merged:
        raise GenerationError("transcript was empty after normalisation")

    # Collapse the whitespace any stripped tag left behind. Done before the join
    # so the f-string stays backslash-free (Python <3.12 rejects that).
    cleaned = [(s, WHITESPACE_RE.sub(" ", t).strip()) for s, t in merged]
    return "".join(f"<Person{s}>{t}</Person{s}>" for s, t in cleaned)


# --------------------------------------------------------------------------
# Driving podcastfy
# --------------------------------------------------------------------------

def conversation_config(cfg: dict) -> dict:
    return {
        "podcast_name": cfg["name"],
        "podcast_tagline": cfg["tagline"],
        "output_language": "English",
        "creativity": 0.7,
        "conversation_style": ["informative", "conversational", "concise"],
        "roles_person1": "host who introduces and explains each story",
        "roles_person2": "co-host who asks practical engineering questions",
        "text_to_speech": {
            "default_tts_model": cfg["tts_model"],
            "output_directories": {
                "transcripts": str(cfg["out_dir"] / "transcripts"),
                "audio": str(cfg["out_dir"]),
            },
            "edge": {
                "default_voices": {
                    "question": cfg["voice_1"],
                    "answer": cfg["voice_2"],
                }
            },
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", type=Path, help="Horizon summary markdown")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-stories", type=int, default=8)
    ap.add_argument("--tts-model", default="edge")
    ap.add_argument("--script-engine", default="claude-cli",
                    choices=["claude-cli", "podcastfy"])
    ap.add_argument("--llm-model", default="claude-sonnet-5")
    ap.add_argument("--llm-api-key-label", default="GEMINI_API_KEY")
    ap.add_argument("--name", default="Daily Tech Digest")
    ap.add_argument("--tagline", default="Your morning briefing")
    ap.add_argument("--voice-1", default="en-US-AndrewNeural")
    ap.add_argument("--voice-2", default="en-US-EmmaNeural")
    ap.add_argument("--transcript-only", action="store_true")
    args = ap.parse_args()

    summary = args.summary or Path(f"horizon-{args.date}-en.md")
    if not summary.is_file():
        print(f"error: summary not found: {summary}", file=sys.stderr)
        return 1

    out_dir: Path = args.out_dir
    (out_dir / "transcripts").mkdir(parents=True, exist_ok=True)

    cfg = {
        "name": args.name,
        "tagline": args.tagline,
        "tts_model": args.tts_model,
        "voice_1": args.voice_1,
        "voice_2": args.voice_2,
        "out_dir": out_dir,
    }

    try:
        from podcastfy.client import generate_podcast
    except ImportError:
        print("error: podcastfy is not installed. Run: make install-podcast",
              file=sys.stderr)
        return 1

    try:
        stories = parse_summary(summary, args.max_stories)
        print(f"==> {len(stories)} stories from {summary.name}")

        if args.script_engine == "claude-cli":
            print("==> writing script with the claude CLI")
            raw = script_via_claude_cli(
                build_prompt(stories, args.date, cfg), args.llm_model
            )
            transcript = normalise_transcript(raw)

            tpath = out_dir / "transcripts" / f"transcript-{args.date}.txt"
            tpath.write_text(transcript, encoding="utf-8")
            turns = transcript.count("<Person1>") + transcript.count("<Person2>")
            print(f"==> transcript: {tpath} ({turns} turns)")

            if args.transcript_only:
                return 0

            print(f"==> synthesising audio via podcastfy (tts={args.tts_model})")
            audio = generate_podcast(
                transcript_file=str(tpath),
                tts_model=args.tts_model,
                conversation_config=conversation_config(cfg),
            )
        else:
            # Let podcastfy do both halves with its own LLM.
            text = "\n\n".join(
                f"{s['title']}\n{s['summary']}" for s in stories
            )
            audio = generate_podcast(
                text=text,
                tts_model=args.tts_model,
                llm_model_name=args.llm_model,
                api_key_label=args.llm_api_key_label,
                conversation_config=conversation_config(cfg),
                transcript_only=args.transcript_only,
            )

        if not audio:
            print("error: podcastfy returned no audio file", file=sys.stderr)
            return 1

        final = out_dir / f"digest-{args.date}.mp3"
        if Path(audio).resolve() != final.resolve():
            shutil.move(audio, final)
        size_mb = final.stat().st_size / 1_048_576
        print(f"==> episode: {final} ({size_mb:.1f} MB)")
        return 0

    except GenerationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

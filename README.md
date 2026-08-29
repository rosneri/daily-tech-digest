# Daily Tech Digest

An automated morning tech briefing. Every day it gathers news from ~50 sources,
scores and deduplicates it with an LLM, posts a curated digest to Slack as a
threaded message, and optionally produces a two-host podcast episode of the same
material.

```
06:45  launchd ──> Horizon ──> horizon-YYYY-MM-DD-en.md   (~170 items in, ~20-25 out)
                      │
                      └──────> digest-YYYY-MM-DD.mp3      (podcastfy, optional)

08:00  Claude routine ──> reads the summary
                     ├──> categorises, applies editorial rules
                     ├──> posts a Slack thread
                     └──> writes digests/YYYY-MM-DD/digest.json
```

Two halves, deliberately decoupled: a **scheduled job** does the deterministic
work (fetch, score, summarise, narrate), and a **Claude routine** does the
editorial work (categorise, write, deliver). Either can be run on its own.

## What it needs

| | | |
|---|---|---|
| macOS | for `launchd` scheduling | the scripts themselves are portable |
| [`uv`](https://docs.astral.sh/uv/) | Python environments | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Claude Code CLI | LLM calls | authenticates via your existing login — **no API key** |
| `ffmpeg` | podcast audio only | `brew install ffmpeg` |
| A Slack MCP server | digest delivery | configured in Claude |

The default configuration needs **no API keys at all**. Story scoring and podcast
scripting both go through the logged-in `claude` CLI, and the default TTS engine
(Edge) is free. Keys only become necessary if you switch to OpenAI/ElevenLabs
voices or to podcastfy's own LLM.

## Install

```sh
git clone <this-repo> daily-tech-digest
cd daily-tech-digest
cp config.env.example config.env
$EDITOR config.env          # set SLACK_CHANNEL_ID
./install.sh
```

`install.sh` is idempotent — re-run it freely. It will:

1. clone [Horizon](https://github.com/Thysrael/Horizon) at a pinned commit and apply `patches/horizon-local.patch`
2. install Horizon's dependencies and seed `data/config.json`
3. create an isolated venv for [podcastfy](https://github.com/souzatharsis/podcastfy)
4. render and load the launchd job

Skip pieces with `./install.sh --no-podcast --no-schedule`.

Then register the Claude routine (see below) and verify:

```sh
make check      # dependencies, syntax, config
make status     # what exists for today
```

## Usage

```sh
make run-horizon              # fetch + score + summarise (~12 min)
make summary                  # today's headlines
make podcast                  # audio episode for today
make transcript               # script only, no audio
make podcast DATE=2026-08-28  # any past day with a summary
make status                   # summary / digest / podcast / schedule
make logs                     # tail the Horizon log
```

`make help` lists everything.

## The Claude routine

The editorial half runs as a scheduled Claude task. Its definition lives in
`skill/SKILL.md` with placeholders for your paths and channel:

```sh
make skill                        # print it with your config filled in
scripts/render-skill.sh -o /tmp/SKILL.md   # or write to a file
```

Create a scheduled task in Claude, attach the rendered file, and set it to run
comfortably after the Horizon job — Horizon takes about 12 minutes, so a 06:45
job and an 08:00 routine leaves plenty of room.

The routine loads your preferences, reads the morning's summary, maps stories
into categories, posts the Slack thread, tracks which stories you reacted to
yesterday, and saves `digest.json`.

## Configuration

Everything lives in `config.env` (gitignored). The settings you are most likely
to touch:

| Key | Default | Notes |
|---|---|---|
| `SLACK_CHANNEL_ID` | — | **Required.** Where the digest is posted. |
| `DIGEST_HOME` | `~/Automation/daily-tech-digest` | All runtime state. |
| `HORIZON_THRESHOLD` | `5.5` | Score cutoff 0-10. Lower = more stories. |
| `HORIZON_HOUR/MINUTE` | `6` / `45` | Must finish before the routine runs. |
| `PODCAST_ENABLED` | `true` | |
| `PODCAST_TTS_MODEL` | `edge` | `edge` is free; `openai`/`elevenlabs`/`gemini` need keys. |
| `PODCAST_SCRIPT_ENGINE` | `claude-cli` | `claude-cli` needs no key; `podcastfy` uses its own LLM. |
| `PODCAST_MAX_STORIES` | `8` | Roughly a minute of audio each. |

Editorial preferences — feeds, focus topics, `wantMore`/`wantLess`, and the
rules the routine follows — live in `config/preferences.json` and are installed
to `$DIGEST_HOME/preferences.json`.

Source selection, category limits and scoring live in `config/horizon.config.json`.

### Tuning what you get

- **Too few stories?** Lower `HORIZON_THRESHOLD`. At 6.5 the rubric only admits
  its "high value" band and you get a handful a day; 5.5 admits "interesting"
  and yields 20-30.
- **Wrong mix?** `digest.category_groups` in `config/horizon.config.json` caps
  each group. Note that most items arrive tagged `tech`, so that group's limit
  dominates the total.
- **Wrong emphasis?** `profiles/tech-news/analysis.md` inside the Horizon
  checkout carries a "Reader profile" section that biases scoring within each
  rubric band. Edit it there, then refresh the patch (see `patches/README.md`).

## How the pieces fit

```
config.env ──> scripts/lib.sh ──> every script
                                    │
   bootstrap-horizon.sh ── clone Horizon @ pin + apply patch + seed config
   run-horizon.sh ─────── run Horizon, then optionally the podcast
   generate-podcast.sh ── wrapper: config.env -> generate_podcast.py
   generate_podcast.py ── parse summary -> write script -> podcastfy TTS
   install-launchd.sh ─── render launchd/horizon.plist.template, load it
   render-skill.sh ────── fill placeholders in skill/SKILL.md
```

### The podcast path

`generate_podcast.py` parses the Horizon summary, takes the top
`PODCAST_MAX_STORIES`, and asks the `claude` CLI for a two-host script. podcastfy
requires strictly alternating `<Person1>`/`<Person2>` turns, so the output is
normalised — consecutive same-speaker turns are merged and a trailing unpaired
turn is dropped — rather than failing the run over a formatting slip. The
finished transcript goes to podcastfy for TTS only, which is why no LLM key is
needed.

Set `PODCAST_SCRIPT_ENGINE=podcastfy` to hand both halves to podcastfy instead.

## Troubleshooting

**Digest says "none met the importance threshold".** Either a genuinely quiet
day or `HORIZON_THRESHOLD` is too high. It is *not* a masked AI failure —
Horizon now aborts non-zero rather than emitting an empty digest when analysis
is broadly failing, so a summary that says this really did score its inputs.

**`make run-horizon` exits non-zero with "AI analysis failed for N/M items".**
Working as intended. Usually a Claude usage limit or an expired login — check
with `claude -p "hello"`. Any existing summary is left untouched.

**GitHub 403 rate limit.** Unauthenticated GitHub allows 60 requests/hour and a
run uses ~16, so a couple of manual runs exhausts it. Add `GITHUB_TOKEN` to
`$DIGEST_HOME/horizon/.env` for 5000/hour.

**Podcast fails with an ffmpeg error.** `brew install ffmpeg`.

**`git apply` fails during install.** `HORIZON_PIN` and
`patches/horizon-local.patch` have drifted apart. See `patches/README.md`.

## Credits

- [Horizon](https://github.com/Thysrael/Horizon) by Thysrael — news aggregation, scoring and summarisation (MIT)
- [podcastfy](https://github.com/souzatharsis/podcastfy) by Tharsis Souza — text-to-podcast (Apache-2.0)

Horizon is not vendored here; it is cloned at install time and patched. See
`patches/README.md` for what we change and why.

## License

MIT — see [LICENSE](LICENSE).

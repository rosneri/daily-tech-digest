# Daily Tech Digest

An automated morning tech briefing. Every day it gathers news from ~50 sources,
scores and deduplicates it with an LLM, DMs you a curated Block Kit digest from
its own Slack app, and optionally produces a two-host podcast episode of the same
material.

```
06:45  launchd ──> Horizon ──> horizon-YYYY-MM-DD-en.md   (~170 items in, ~20-25 out)
                      │
                      └──────> digest-YYYY-MM-DD.mp3      (podcastfy, optional)

08:00  Claude routine ──> reads the summary
                     ├──> categorises, applies editorial rules
                     ├──> DMs a Slack thread
                     └──> writes digests/YYYY-MM-DD/digest.json
```

Two halves, deliberately decoupled: a **scheduled job** does the deterministic
work (fetch, score, summarise, narrate), and a **Claude routine** does the
editorial work (categorise, write, deliver). Either can be run on its own.

## What it needs

| | | |
|---|---|---|
| [`proto`](https://moonrepo.dev/proto) | pins every tool version | `curl -fsSL https://moonrepo.dev/install/proto.sh \| bash`, then `proto use` |
| [`moon`](https://moonrepo.dev/moon) | runs tasks across the workspace | installed by `proto use` |
| macOS | for `launchd` scheduling | the CLI itself is portable |
| [`uv`](https://docs.astral.sh/uv/) | the Python workspace, Horizon, podcastfy | installed by `proto use` |
| Claude Code CLI | LLM calls | authenticates via your existing login — **no API key** |
| `ffmpeg` | podcast audio only | `brew install ffmpeg` |
| A Slack app | digest delivery | created from `slack/manifest.yaml` — [docs/slack-app.md](docs/slack-app.md) |

The default configuration needs **no API keys at all**. Story scoring and podcast
scripting both go through the logged-in `claude` CLI, and the default TTS engine
(Edge) is free. Keys only become necessary if you switch to OpenAI/ElevenLabs
voices or to podcastfy's own LLM.

## Install

```sh
git clone <this-repo> daily-tech-digest
cd daily-tech-digest
proto use                   # installs python, uv and moon at the pinned versions
./digest config
$EDITOR config.env          # set SLACK_USER_ID
./digest install
```

`./digest install` is idempotent — re-run it freely. It will:

1. clone [Horizon](https://github.com/Thysrael/Horizon) at a pinned commit and apply `patches/horizon-local.patch`
2. install Horizon's dependencies and seed `data/config.json`
3. create an isolated venv for [podcastfy](https://github.com/souzatharsis/podcastfy)
4. write and load the launchd job

Skip pieces with `./digest install --no-podcast --no-schedule`.

Then set up Slack delivery ([docs/slack-app.md](docs/slack-app.md)), register the
Claude routine (see below), and verify:

```sh
./digest check          # dependencies, syntax, config
./digest slack check    # token, scopes, DM destination
./digest status         # what exists for today
moon check --all        # compile + test every project
```

## Usage

```sh
./digest run                        # fetch + score + summarise (~12 min)
./digest summary                    # today's headlines
./digest podcast                    # audio episode for today
./digest podcast --transcript-only  # script only, no audio
./digest podcast --date 2026-08-28  # any past day with a summary
./digest status                     # summary / digest / podcast / schedule
./digest logs                       # tail the Horizon log
```

`./digest --help` lists everything. Every dated command takes `--date YYYY-MM-DD`.

There is no `make` and no shell script: the pipeline is the `digest` CLI over
the workspace libraries. `moon` runs the checks and tests:

```sh
moon check --all            # every project
moon run slack:test         # one project's tests
moon run digest:check       # one project's syntax gate
```

## The Claude routine

The editorial half runs as a scheduled Claude task. Its definition lives in
`skill/SKILL.md` with placeholders for your paths and Slack destination:

```sh
./digest skill                    # print it with your config filled in
./digest skill -o /tmp/SKILL.md   # or write it to a file
```

Re-render after changing `config.env` — the rendered copy is a build artefact,
so edit `skill/SKILL.md` rather than the output.

Create a scheduled task in Claude, attach the rendered file, and set it to run
comfortably after the Horizon job — Horizon takes about 12 minutes, so a 06:45
job and an 08:00 routine leaves plenty of room.

The routine loads your preferences, reads the morning's summary, maps stories
into categories, DMs the Slack thread as Block Kit, uploads the podcast MP3 into
it, tracks which stories you reacted to yesterday, and saves `digest.json`.

It reaches Slack through `./digest slack` rather than an MCP server. That is
what makes the audio work: MCP can post messages but cannot upload files, so the
episode could previously only be named, not played. It is also what makes the
digest a DM built from blocks rather than plain text in a channel.

## Configuration

Everything lives in `config.env` (gitignored). The settings you are most likely
to touch:

| Key | Default | Notes |
|---|---|---|
| `SLACK_USER_ID` | — | **Required.** Your member ID; the digest is DM'd to you. |
| `SLACK_CHANNEL_ID` | — | Optional. Post to a channel instead of the DM. |
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
apps/digest ─── the only client. Owns config.env, presentation, orchestration.
  │
  ├─ libs/shellenv ── parse shell-style KEY=value files without a shell
  ├─ libs/slack ───── Slack Web API: post, upload files, read threads/reactions
  ├─ libs/launchd ─── build, load and retarget macOS launchd agents
  ├─ libs/horizon ─── clone @ pin + patch + seed; run the daily aggregation
  └─ libs/podcast ─── build the podcastfy venv; drive the generator; find episodes
```

The split is the point: a lib takes explicit arguments and raises its own error
type, so none of them can reach for `config.env` or decide how something prints.
That is what makes a second client — a daemon, an MCP server, a different
scheduler — a new entry in `.moon/workspace.yml` and nothing else.

Every lib is stdlib-only on purpose: the CLI has to run from a bare launchd job
at 06:45, so `./digest` works straight from a checkout without `uv sync` having
run. The one exception is `libs/podcast/scripts/generate_podcast.py`, which
executes inside the podcastfy venv rather than the workspace one — which is
exactly why it is a subprocess and not an import.

### Workspace

`proto` pins the toolchain in `.prototools`; `moon` maps the projects in
`.moon/workspace.yml`; `uv` links them as a workspace from the root
`pyproject.toml`. Tasks run through `uv run`, so they behave the same whether or
not the toolchain has been materialised.

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

**`./digest run` exits non-zero with "AI analysis failed for N/M items".**
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

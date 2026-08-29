# Horizon patches

[Horizon](https://github.com/Thysrael/Horizon) (MIT, © Thysrael) does the news
gathering, scoring and summarising. We do not vendor it — `scripts/bootstrap-horizon.sh`
clones it at the commit pinned by `HORIZON_PIN` and applies `horizon-local.patch`.

## What the patch changes

**`src/ai/client.py` — authenticate through the Claude Code CLI.**
`AnthropicClient` shells out to `claude -p` instead of using the Anthropic SDK,
so the pipeline needs no `ANTHROPIC_API_KEY`. Two fixes on top:

- The CLI reports usage limits and auth failures on **stdout**, not stderr. The
  original handler only read stderr, so every failure logged `stderr:` followed
  by nothing — 381 blank error lines in one observed run.
- `stdin=subprocess.DEVNULL`. The CLI otherwise waits 3 seconds for stdin on
  every call (~100s per run at 130 items) and can block on an inherited tty
  under launchd.

**`src/ai/analyzer.py` + `src/orchestrator.py` — do not ship a silently empty digest.**
An item whose analysis fails gets `score=None` and can never clear the
threshold. When the AI backend failed wholesale, Horizon still exited 0 and
wrote *"none met the importance threshold — this might indicate a quiet day in
your tracked sources"* — indistinguishable from a real quiet day, and
downstream consumers silently fell back to other sources. The analyzer now
counts failures and the orchestrator aborts non-zero above
`ANALYSIS_FAILURE_ABORT_RATIO` (0.5), leaving any existing summary intact.

**`src/orchestrator.py` — browser User-Agent on the shared HTTP client.**
Some publishers reject the bare `python-httpx` agent with a 403.

**`src/models.py` + `src/scrapers/github.py` — `search_repos` source type.**
Trending repositories via the GitHub search API (recently created, ranked by
stars). Replaces OSS Insight, whose `past_24_hours` star counts top out around
8 — against the default `min_stars: 20` it silently returned zero rows daily.

**`profiles/tech-news/analysis.md` — reader profile.**
Biases scoring toward software engineering within each rubric band, so consumer
hardware, space and finance stories stop crowding out the engineering content.
A tiebreaker, not a filter.

## Working on the patch

```sh
# after editing files in the Horizon checkout
cd "$DIGEST_HOME/horizon" && git diff > /path/to/repo/patches/horizon-local.patch

# verify it still applies to the pinned commit
git clone https://github.com/Thysrael/Horizon.git /tmp/hz && cd /tmp/hz
git checkout "$HORIZON_PIN" && git apply --check /path/to/repo/patches/horizon-local.patch
```

Bumping `HORIZON_PIN` without refreshing the patch will fail the install with a
clear error rather than half-applying.

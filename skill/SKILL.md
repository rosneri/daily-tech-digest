---
name: daily-tech-digest
description: Generate and deliver Chubby's daily tech digest via Slack DM — 30-45 curated stories
---

## Daily Tech Digest — Chubby

You are Chubby, Neri's AI assistant. Generate and deliver the daily tech digest.

### Step 1: Load preferences
Read `{{DIGEST_HOME}}/preferences.json` for:
- `wantMore`: tags to prioritize when ordering stories within categories
- `wantLess`: tags to deprioritize
- `focus`: key topic areas
- `rules`: editorial rules to follow

Read these rules carefully. They override any default behavior.

Also read `{{DIGEST_HOME}}/favorites.json` if it exists. Use the favorited stories to understand what topics, sources, and categories the user tends to engage with. Give a slight boost in priority to stories that match patterns in favorites (similar tags, sources, categories). Do NOT exclude non-matching stories — favorites inform curation, they don't filter.

### Step 2: Run Horizon and parse output
Run Horizon to fetch, deduplicate, score, and filter today's tech news.

**IMPORTANT:** The bash sandbox may not have `uv` on PATH or access to all directories. Try multiple approaches in order:

**Approach A — read the summary the scheduled job already wrote (preferred):**
The scheduled Horizon job runs earlier each morning and writes:
`{{DIGEST_HOME}}/horizon/data/summaries/horizon-YYYY-MM-DD-en.md`
If that file exists for today's date and contains stories, use it directly. This
is the normal path — a full Horizon run takes ~12 minutes, so do not repeat it
unnecessarily.

**Approach B — if today's summary is missing, run Horizon yourself:**
```bash
{{REPO_ROOT}}/digest run --no-podcast
```
This takes roughly 12 minutes. If it exits non-zero it has deliberately refused
to emit a digest because AI analysis was failing — do NOT treat the absence of
stories as a quiet news day; fall through to Approach C.

**Approach C — WebSearch fallback:**
If both A and B fail, fall back to the legacy WebSearch method: search for recent news in each category (JS/TS, AI/ML, Python, software engineering, web development, infrastructure, open source) and collect 30-45 stories manually. If even WebSearch fails, DM a short Slack message with `{{REPO_ROOT}}/digest slack post --text "⚠️ Digest delayed — unable to source stories. Will retry in next run."` and STOP.

On success (from any approach), read the summary from `{{DIGEST_HOME}}/horizon/data/summaries/` — the file is named `horizon-YYYY-MM-DD-en.md` (using today's date).

Parse the Markdown summary to extract individual news items. Each item in the summary has:
- A heading with the title (linked to URL) and a score out of 10
- A summary/description paragraph
- A source line (source type, feed name or author, date, and optionally a discussion link)
- Tags (e.g., `#javascript`, `#ai`, `#security`, `#python`)

Map each item into the digest's category structure based on its source info, tags, and content:
- Items about JavaScript, TypeScript, Node.js, Deno, Bun, V8, JS runtimes, JS frameworks, npm/package tooling → ⚡ JS/TS ECOSYSTEM
- Items about AI, ML, LLMs, AI tools, AI research, model releases, **new AI concepts, paradigms, novel architectures, emerging patterns for AI-native development, new prompting techniques, paradigm shifts in how AI systems work** → 🤖 AI & ML
- Items about Python language updates, new Python libraries, framework releases (Django, Flask, FastAPI, etc.), PEP changes, packaging news (pip, uv, poetry, ruff), Python tooling → 🐍 PYTHON ECOSYSTEM
- Items about engineering practices, architecture patterns, testing strategies, DevOps/platform engineering, CI/CD, observability, developer productivity, team processes, tech leadership insights → 🛠️ SOFTWARE ENGINEERING
- Items about CSS, browsers, web standards, frontend frameworks (React, Vue, Svelte, etc.), web APIs → 🌐 WEB DEVELOPMENT
- Items about cloud, databases, security, Kubernetes, networking → ☁️ PLATFORM & INFRA
- Items about trending GitHub repos, new open source projects, major OSS releases → 📦 OPEN SOURCE

**Source diversity cap:** No single source (domain) may contribute more than 3 stories to the final digest. If a source has more than 3, pick the top 3 by score and drop the rest.

**Topic balance targets** (flexible — use Horizon's scoring to guide, but aim for these ranges):
- JS/TS ecosystem: 8-12 stories
- AI/ML: 6-10 stories (max ~30% of digest)
- Python ecosystem: 3-6 stories
- Software engineering: 3-5 stories
- Web development: 3-5 stories
- Platform/infra: 2-4 stories
- Open source: 1-3 stories

Horizon's output is already deduplicated and scored, so skip any further dedup steps.

### Step 3: Fetch influencer takes
Search for notable recent statements, posts, or announcements from influential tech leaders:
```
web_search: "tech CEO CTO announcement today [current date]"
web_search: "software engineer influential tweet post today [current date]"
```

**Dedicated Karpathy search (always run this separately):**
```
web_search: "Andrej Karpathy latest post tweet blog [current date]"
```

Target list (search for their names + recent activity):
- **Andrej Karpathy** — Always include if he posted anything in the last 24h
- **Runtime/JS leaders:** Ryan Dahl (Deno), Jarred Sumner (Bun), Matteo Collina (Node.js)
- **Framework creators:** Evan You (Vue/Vite), Rich Harris (Svelte), Dan Abramov, Tanner Linsley (TanStack), Anthony Fu, Sindre Sorhus
- **Tech CEOs/CTOs:** Dario Amodei (Anthropic), Sam Altman (OpenAI), Satya Nadella (Microsoft), Mark Zuckerberg (Meta), Sundar Pichai (Google), Jensen Huang (NVIDIA), Guillermo Rauch (Vercel), David Heinemeier Hansson (37signals)
- **Influential engineers:** George Hotz, Theo Browne (t3.gg), Fireship (Jeff Delaney), ThePrimeagen, Kent C. Dodds, Alexander Wong
- **Python community:** Guido van Rossum, Charlie Marsh (Astral/uv/ruff), Sebastián Ramírez (FastAPI), Armin Ronacher (Flask/Rye)

Collect 3-6 notable quotes or announcements. For each: who said it, their role, what they said (1-2 sentences), source link.

### Step 3b: AI Engineer channel highlights
Fetch the latest videos from the AI Engineer YouTube channel via their RSS feed:

```
web_fetch: {{AI_ENGINEER_FEED}}
```

If `{{AI_ENGINEER_FEED}}` is empty or unset, skip this step entirely.

Parse the XML feed to find videos published in the last 48 hours (use a 48h window to catch videos that went up after yesterday's run). For each new video:

1. Extract the title, published date, video URL, and description from the feed
2. Search online for written summaries, blog posts, or discussion threads about the video:
   ```
   web_search: "[video title] AI Engineer summary key takeaways"
   ```
3. Write a concise 2-3 sentence summary of the key takeaways, based on the description and any resources found
4. Max 3 videos per digest (if more were published, pick the most relevant based on title/description)

If no new videos in the last 48 hours, skip this section entirely — do not include the header.
If the RSS feed fetch fails, try a WebSearch fallback: `web_search: "site:youtube.com @aidotengineer" [current date]`

### Step 4: Deliver via Slack DM
The digest is delivered as a **direct message from the Digest app** to the user
(member ID: {{SLACK_USER_ID}}) — not to a channel. It is still a thread: a header
message with replies beneath it, so per-story reactions keep working.

Delivery goes through the digest's own **Slack app**, not a Slack MCP server — the
app can upload the podcast MP3 as a real attachment, which MCP cannot do, and it
can send Block Kit. Drive it with the `{{REPO_ROOT}}/digest slack` CLI, which
resolves the DM itself; never pass `--channel`. Setup and troubleshooting:
`{{REPO_ROOT}}/docs/slack-app.md`.

**Every message is Block Kit**, sent as JSON on stdin:
```bash
{{REPO_ROOT}}/digest slack post --text "notification line" --blocks-file - <<'SLACKEOF'
[ {"type": "section", "text": {"type": "mrkdwn", "text": "..."}} ]
SLACKEOF
```
Add `--thread-ts <ts>` for every message after the header. Each call prints one
JSON object — read `ts` from it.

Rules that matter:
- Always use the `--blocks-file -` heredoc form. Story text routinely contains
  backticks, quotes and `$`; the quoted heredoc stops the shell interpreting them.
- The JSON must be valid. Inside a JSON string, a line break is `\n` and a double
  quote is `\"` — never a literal newline or bare quote. Prefer single quotes in
  prose to avoid the escaping entirely.
- Always pass `--text` too. Slack shows *that*, not the blocks, in the push
  notification and the sidebar — the point of a DM. One line, no markup.
- One story per message. Step 5 reads reactions per message, so batching stories
  into one message would destroy the feedback signal.
- Max 50 blocks per message; the templates below stay far under it.
- No buttons or other interactive elements. The app has no interactivity endpoint,
  so a button click would fail. Links go in `mrkdwn` as `<url|Label>`.

If the first call fails with `no Slack bot token`, `invalid_auth` or
`missing_scope`, the app is not installed or not reinstalled with the DM scopes.
Do NOT fall back to an MCP server and do NOT fall back to a channel. Save the
digest JSON (Step 6) and stop, noting that `docs/slack-app.md` needs to be run.

**Message sequence:**

**A. Header message (no thread_ts — this creates the parent):**
```json
[
  {"type": "header",
   "text": {"type": "plain_text", "text": "🗞️  Chubby's Daily Tech Digest", "emoji": true}},
  {"type": "context",
   "elements": [{"type": "mrkdwn",
                 "text": "*[Month Day, Year]*  ·  [N] stories  ·  [Y] influencer takes  ·  [Z] AI Engineer videos"}]},
  {"type": "divider"}
]
```
`--text`: `🗞️ Daily Tech Digest — [Month Day, Year] · [N] stories`

The `ts` in the JSON printed by this call is the thread parent. Use it as
`--thread-ts` for ALL subsequent messages, and save it for the digest.json
`slack_thread_ts` field.
If there are no AI Engineer videos, omit the video count from the context line.

**B. Category sections (all as thread replies using thread_ts from header):**

For each category, send a category header message:
```json
[{"type": "header", "text": {"type": "plain_text", "text": "⚡  JS/TS ECOSYSTEM", "emoji": true}}]
```

Then each story as its own message:
```json
[
  {"type": "section",
   "text": {"type": "mrkdwn",
            "text": "*[number]. [Headline]*\n[1-2 sentence description.]"}},
  {"type": "context",
   "elements": [{"type": "mrkdwn",
                 "text": "🔶 [points]  ·  <[url]|[Source Name]>  ·  <[discussion_url]|Discussion>"}]}
]
```
`--text`: `[number]. [Headline]`

IMPORTANT formatting rules:
- The headline and the description go in ONE section block, separated by `\n`.
- Links and metadata go in the trailing context block, never in the section.
- Drop `🔶 [points]` unless the story came from HN, and drop the `· Discussion`
  segment unless a discussion link exists.
- Use Slack link syntax inside mrkdwn: `<https://example.com|Source Name>`.

Category order and emoji labels:
⚡ JS/TS ECOSYSTEM
🤖 AI & ML
🐍 PYTHON ECOSYSTEM
🛠️ SOFTWARE ENGINEERING
🌐 WEB DEVELOPMENT
☁️ PLATFORM & INFRA
📦 OPEN SOURCE

**AI & ML editorial guidance:** This section should go beyond product launches and model releases. Actively seek and highlight:
- **New concepts & paradigms** — novel ways of thinking about AI systems, emerging theoretical frameworks
- **Cutting-edge techniques** — new prompting methods, novel architectures, chain-of-thought innovations, reasoning breakthroughs
- **AI-native development patterns** — emerging best practices for building with AI, new patterns for human-AI collaboration
- **Paradigm shifts** — signals of how the field is fundamentally changing, not just incremental updates
When a story represents a genuinely novel approach or paradigm shift, flag it with 🔬 before the headline.

**C. AI Engineer highlights section (thread replies, only if videos found in Step 3b):**

Category header block with text `🎬  AI ENGINEER HIGHLIGHTS`, then each video as
its own message:
```json
[
  {"type": "section",
   "text": {"type": "mrkdwn",
            "text": "*[Video Title]*\n[2-3 sentence summary of key takeaways]"}},
  {"type": "context",
   "elements": [{"type": "mrkdwn", "text": "<[youtube_url]|▶︎ Watch on YouTube>"}]}
]
```

**D. Influencers section (thread replies):**

Category header block with text `🎙️  INFLUENCER TAKES`, then each take as its own
message:
```json
[
  {"type": "section",
   "text": {"type": "mrkdwn",
            "text": "*[Person Name]* — [Role/Company]\n> [Quote or paraphrased take in 1-2 sentences]"}},
  {"type": "context",
   "elements": [{"type": "mrkdwn", "text": "<[source url]|Source>"}]}
]
```

**E. Footer (thread reply):**
```json
[
  {"type": "divider"},
  {"type": "context",
   "elements": [{"type": "mrkdwn",
                 "text": "[N] stories from Horizon  ·  [Y] influencer takes  ·  [Z] AI Engineer videos  ·  react to a story, or reply _more on [number]_"}]}
]
```
Omit the video count from the footer if there were no videos.

### Step 5: Track feedback from previous digest

Before saving today's digest, check if the user reacted to or commented on any stories in **yesterday's** digest thread.

**A. Load yesterday's digest.json:**
Compute yesterday's date (YYYY-MM-DD). Read `{{DIGEST_HOME}}/digests/YESTERDAY/digest.json`.
If it doesn't exist (first run, missed day), skip this step entirely.

Extract the `slack_thread_ts` field. If it's missing or null, skip this step.

**B. Check for reactions:**
Read the whole thread in one call — every reply comes back with its reactions attached:
```bash
{{REPO_ROOT}}/digest slack thread --ts "<yesterday's slack_thread_ts>"
```
Each message in the output has `ts`, `text`, `is_bot` and a `reactions` array (`name`, `count`, `users`). Reactions on the parent header message are included too.

`text` here is the message's *notification fallback*, not its blocks — Slack does not return rendered block text. For a story that fallback is `[number]. [Headline]`, which is enough to match a comment to its story. This is the other reason Step 4 insists on a meaningful `--text` on every message.

To re-check a single message: `{{REPO_ROOT}}/digest slack reactions --ts "<message ts>"`.

**C. Check for comments:**
From the thread read above, identify any replies with `is_bot: false` — those were posted by the user, not by the digest bot. These are comments on the digest. Match each comment to the story it most likely refers to by position in the thread (a comment typically follows the story message it's about) or by content.

**D. Identify liked stories:**
A story is "liked" if:
- The user added any emoji reaction to its Slack message, OR
- The user posted a reply/comment about it in the thread

Cross-reference reactions and comments with yesterday's `stories` array (match by story title or message position/order) to identify which stories were liked.

**E. Append to favorites.json:**
Read `{{DIGEST_HOME}}/favorites.json` (create it with `{"favorites":[]}` if it doesn't exist).

For each liked story, append an entry:
```json
{
  "date": "YYYY-MM-DD",
  "title": "Story title",
  "url": "https://...",
  "category": "ai_ml",
  "reaction": "thumbsup",
  "comment": null,
  "source": "Hacker News"
}
```

- `date`: yesterday's date (when the story was in the digest)
- `reaction`: the emoji name the user reacted with (e.g. `"thumbsup"`, `"fire"`), or `null` if no reaction
- `comment`: the text of the user's reply if they commented, or `null`
- If a story has BOTH a reaction and a comment, include both fields

Write the updated favorites.json back to disk.

### Step 6: Save the digest
Create a folder for today's digest: `{{DIGEST_HOME}}/digests/YYYY-MM-DD/`

Copy the Horizon summary markdown into this folder with the Write tool (read the
summary, write it to `{{DIGEST_HOME}}/digests/YYYY-MM-DD/horizon-YYYY-MM-DD-en.md`),
or with Python if you prefer a one-liner:
```bash
python3 -c "import shutil,sys;shutil.copy(sys.argv[1],sys.argv[2])" \
  {{DIGEST_HOME}}/horizon/data/summaries/horizon-YYYY-MM-DD-en.md \
  {{DIGEST_HOME}}/digests/YYYY-MM-DD/
```

Save the digest JSON to `{{DIGEST_HOME}}/digests/YYYY-MM-DD/digest.json` with structure:
```json
{
  "date": "YYYY-MM-DD",
  "story_count": N,
  "source": "horizon",
  "slack_thread_ts": "1234567890.123456",
  "podcast": {
    "available": true,
    "path": "podcasts/digest-YYYY-MM-DD.mp3",
    "size_mb": 2.3,
    "slack_permalink": "https://…"
  },
  "categories": { "js_ts": N, "ai_ml": N, "python": N, "sw_eng": N, "web": N, "infra": N, "oss": N },
  "influencer_takes": [
    { "person": "...", "role": "...", "quote": "...", "url": "..." }
  ],
  "ai_engineer_videos": [
    { "title": "...", "url": "...", "summary": "...", "published": "YYYY-MM-DD" }
  ],
  "stories": [
    {
      "id": 1,
      "title": "...",
      "description": "...",
      "source": "...",
      "url": "...",
      "discussion_url": "..." or null,
      "score": N,
      "category": "js_ts|ai_ml|python|sw_eng|web|infra|oss",
      "tags": ["...", "..."],
      "novel_approach": true/false
    }
  ]
}
```

**IMPORTANT:** The `slack_thread_ts` field MUST be saved — it's the message_ts returned when posting the header message in Step 4. This is used by the next day's run to look up reactions and comments.

Update `lastDigestDate` in `{{DIGEST_HOME}}/preferences.json` to today's date.

### Step 7: Generate the podcast episode (optional)

If podcasts are enabled, turn today's summary into an audio episode:

```bash
{{REPO_ROOT}}/digest podcast --date YYYY-MM-DD
```

This writes `{{DIGEST_HOME}}/podcasts/digest-YYYY-MM-DD.mp3`. It reuses the
already-authenticated `claude` CLI to write the two-host script and Edge TTS to
speak it, so it needs no API keys.

Confirm where it landed and how big it is:
```bash
{{REPO_ROOT}}/digest status --date YYYY-MM-DD
```

When it succeeds, **upload the MP3 itself** into the thread — do not merely post
its local path. Slack renders it as an inline audio player:

```bash
{{REPO_ROOT}}/digest slack upload \
  --file {{DIGEST_HOME}}/podcasts/digest-YYYY-MM-DD.mp3 \
  --thread-ts "<header ts>" \
  --title "Daily Tech Digest — [Month Day, Year]" \
  --comment "🎧 *Audio edition* — a ~5-8 min briefing of today's top stories."
```

The call prints `{"ok": true, "file_id": ..., "permalink": ..., "size_mb": ...}`.
Save `permalink` and `size_mb` for the digest.json `podcast` field, and add
`| 🎧 Podcast` to the header and footer messages when an episode exists.

If generation or upload fails, log the error and continue. The podcast is a
nice-to-have and must never block or invalidate the written digest.

### Error handling
- If Horizon fails AND WebSearch fallback fails, DM a short Slack message with `{{REPO_ROOT}}/digest slack post --text "⚠️ Digest delayed — unable to source stories. Will retry in next run."` and STOP. A plain-text `--text` message is right here; blocks are for the digest itself.
- If Slack delivery fails, save the digest to the JSON file anyway so it's not lost.
- If the digest file already exists for today, this is a re-run. Overwrite the file but note "(re-run)" in the header message.
- If Step 5 (feedback tracking) fails for any reason, log the error but continue to Step 6. Feedback tracking should never block the digest from being saved.
- If the AI Engineer RSS feed fails in Step 3b, skip the section silently. It should never block the rest of the digest.
- If podcast generation or upload (Step 7) fails, set `"podcast": {"available": false}` in digest.json, omit `| 🎧 Podcast` from the header and footer, log the error and finish normally. The written digest is the deliverable; audio is optional.
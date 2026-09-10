# Composing the digest without a model

The editorial half of the digest used to be a scheduled Claude task: it read
Horizon's markdown summary, sorted stories into sections, rewrote each one,
applied the rules in `preferences.json` and drove the Slack CLI message by
message. It is code now — `digest deliver`.

## Why it can be code

Horizon already did the judgement; the routine was mostly re-deriving it from
prose. Per item, Horizon's analysis produces a score, a one-sentence summary and
a set of tags. Only the section was missing, and Horizon's own `category` field
could not supply it: category is configured **per source**, so every Hacker
News, Reddit and RSS item arrives labelled `tech` regardless of subject. That is
why a digest built on it was one flat list.

So the section is asked for in the analysis prompt instead. This repo ships its
own copy of the `tech-news` profile at `config/profiles/tech-news/`, and
`processing.profiles_dir` in Horizon's config points at it as an absolute path —
`digest run` re-points it on every run, so it survives a config that was seeded
before this existed. The profile requires exactly one `cat:<id>` tag per item
from a closed list. Nothing in Horizon's source is modified; the profile
directory and the pipeline entry point are both supported extension points.

Items whose category comes back `cat:other`, or with no `cat:` tag at all, are
dropped rather than shown under a vague heading. `digest deliver` reports the
count; a persistently high number means the prompt's list needs a new section.

## What the rules became

| Rule in `preferences.json` | Now |
|---|---|
| Prioritise `wantMore` / `focus` tags | rank bonus, `libs/compose/.../digest.py` |
| Demote `wantLess` tags | rank penalty |
| Favour what you engaged with before | rank bonus from `favorites.json` tags |
| "at most 40% of stories should be AI/ML" | `DIGEST_AI_SHARE`, applied as a quota |
| Prioritise JS/TS ecosystem news | the `js-ts` section renders first |

The rank adjustments are deliberately small — under 1.5 points on Horizon's
0-10 scale — so preferences break ties between comparable stories rather than
overturning the model's read of what matters.

## What was lost

Two rules needed judgement or a live search, and no longer happen:

- **"Check for major tech conferences this week (GTC, GDC, KubeCon, WWDC…) and
  give those stories priority placement."** Nothing searches for what is on this
  week. Conference news still appears when Horizon's sources carry it; it just
  gets no special placement.
- **"Monitor GitHub activity for influential developers (Ryan Dahl, Evan You,
  Rich Harris, …) — new repos, notable stars."** Partly covered already:
  `sources.github` in `config/horizon.config.json` watches 16 repositories for
  releases. Personal activity feeds are not among them. Adding the repos you
  care about there is the deterministic replacement.

Both are worth deleting from `preferences.json` rather than leaving as prose no
step reads. They are listed here so the loss is on the record rather than
discovered as a silent regression.

## Feedback is exact now

`digest.json` records the Slack `ts` of every story message. Yesterday's
reactions therefore map back to stories by message id. The old routine matched
"by story title or message position/order", which was a guess whenever the user
reacted to something in the middle of a long thread.

Replies are still positional — a human reply lands under the thread parent, not
under the story it is about, so it is attributed to the story message directly
above it.

# Evaluation goal

Evaluate the importance of timely technology news for readers interested in software engineering, artificial intelligence, machine learning, computer systems, hardware, open source, and the technology industry.

# Scoring rubric

- **9-10: Groundbreaking.** Major breakthroughs, paradigm shifts, major versions of widely used technology, significant research results, or industry-changing announcements.
- **7-8: High value.** Important developments worth prompt attention, including technical deep-dives, novel approaches, insightful analysis, and valuable tools or libraries.
- **5-6: Interesting.** Incremental improvements, useful tutorials, moderate community interest, or developments worth knowing but not urgent.
- **3-4: Low priority.** Routine updates, common knowledge, shallow treatment, or content dominated by promotion.
- **0-2: Noise.** Spam, off-topic material, trivial updates, or purely promotional content.

# Evaluation guidance

Consider technical depth, novelty, likely impact, source quality, relevance to software engineering and AI systems, and concrete supporting details. Treat substantive community debate as additional evidence of value, but do not equate popularity with technical importance. Do not reward exaggerated headlines.

Use three to five specific topic tags.

# Category tag

Exactly one tag must be a category, written as `cat:<id>`, and it must be the
first tag. Pick the single best fit from this closed list — never invent one:

- `cat:js-ts` — JavaScript, TypeScript, Node, Deno, Bun, V8, ECMAScript, npm and
  the JS/TS build and test toolchain.
- `cat:ai-ml` — models, training, inference, agents, prompting, AI research, and
  the tools and companies whose product is AI.
- `cat:python` — the Python language, runtime, packaging and its libraries.
- `cat:web` — browsers, the web platform, CSS, HTML, accessibility, and
  front-end frameworks that are not primarily a JS/TS toolchain story.
- `cat:infra` — cloud, deployment, databases, networking, observability and
  security operations.
- `cat:oss` — the practice and politics of open source: licensing, governance,
  funding, maintainer burnout, notable new projects.
- `cat:sw-eng` — how software gets built: architecture, testing, code review,
  developer experience, engineering culture and career.
- `cat:other` — genuinely none of the above.

Judge by what the item is *about*, not where it was published: a Hacker News
post about a Node release is `cat:js-ts`. When two fit, prefer the more specific
one — a story about running a model in the browser is `cat:ai-ml`, not
`cat:web`. Reserve `cat:other` for items no reader would file under the rest;
it is a last resort, not a tie-breaker.

# Reader profile

The reader is a working software engineer whose day-to-day is JavaScript/TypeScript, Node, React and the web platform, Python, and building with AI.

Apply the rubric above as written, then use relevance to this reader to settle borderline calls. Items that change how they write, ship, or operate software — language, runtime, framework and tooling releases; security advisories in widely used packages; developer-facing AI; architecture, testing and platform-engineering practice; notable open-source projects — sit at the upper end of the band the rubric assigns them.

Consumer hardware launches, space, biotech, transport, funding rounds, and business or policy coverage sit at the lower end of their band unless they carry a concrete consequence for people who build software. This adjusts placement within a band; it is not a separate penalty, and genuinely major news in these areas still scores on its own merits.

# Token Wisdom — Social Distribution (× Zernio)

> The off-site half of corpus-as-product. One canonical content object, fanned out
> to every platform LLMs crawl. Engine: [Zernio](https://zernio.com) · 14+ platforms ·
> one API. Implementation: [`zernio.py`](zernio.py).

This adapts the pattern proven for BLANK AF (vault/038 — a single social API driving
streetwear drops) to Token Wisdom's reality: a weekly tech-futures publication and a
living encyclopedia of the AI era.

---

## 1. Why this, why now

Token Wisdom's single biggest growth blocker is **discovery**. The live `tokenwisdom.ghost.io`
site is gated behind an access code, which 302s every public URL to `/private/` and
kills SEO. The real public face is the **ungated static GitHub Pages corpus** built by
`generate_site.py`. That corpus is the lead magnet — but a lead magnet nobody finds
isn't one.

Zernio is the distribution answer, and Token Wisdom is an unusually good fit for the
thesis behind it:

- **The content *is* the thing LLMs cite.** TW writes the AI-era encyclopedia. Its
  1,941 hand-defined Lexicon terms are exactly the definitional, evergreen material
  large language models quote. We are not chasing AI citation as a tactic bolted onto a
  clothing brand — we *are* a reference work for the domain.
- **The 30-day recency window maps to weekly cadence.** Every edition is a fresh
  citation surface. Every Lexicon term is a permanent one. Staying inside the window is
  what TW already does editorially; distribution just makes the crawlers aware of it.
- **The structured content object already exists.** `data/all_posts.json` and
  `data/lexicon.json` are generated every build. We don't author social content — we
  *project* existing corpus data onto platforms.

This is the complement to the on-site **Constellation** graph (`lexicon.py`).
Constellation deepens engagement for readers already on the site; Zernio pushes
term + edition surfaces *out* to where new readers and crawlers live. Same corpus,
two directions.

> **Naming note.** "Zernio" was used loosely in an earlier session to mean the
> on-site social-graph (the Constellation). Zernio is in fact a third-party
> multi-platform **publishing API**. They're complementary, not the same thing — and
> the Lexicon/Constellation data is what *feeds* the Zernio content engine.

---

## 2. What's built

[`zernio.py`](zernio.py) generates content **today** against real `data/`, and the
two automation hooks are **wired**. Only the final network call is mocked until the
SDK + key land — everything else (detection, formatting, scheduling, state) runs now.

```bash
python3 zernio.py term           # Term of the Week, formatted per platform
python3 zernio.py evolution      # "How a term changed meaning" (TW's headline feature)
python3 zernio.py constellation  # A term + the ideas it travels with → the live graph
python3 zernio.py edition        # A weekly edition as a 3-post release arc
python3 zernio.py totw           # CRON entry point — publish/dry-run the Term of the Week
python3 zernio.py sync           # Distribute posts not seen before (build trigger)
python3 zernio.py status         # enabled? public base? accounts? state size?
```

**Wired automation:**

- **Build trigger.** `generate_site.py` calls `zernio.sync_new_publications(posts)` at
  the end of every build. It compares post slugs against `data/.zernio_state.json`
  (git-tracked, so state persists across builds/CI). The **first run seeds silently** —
  it records the 267-post backlog as already-distributed so nothing blasts retroactively;
  only genuinely new slugs on later builds fire. Editions get the 3-post arc, essays a
  single cross-post. It is wrapped so it can **never fail the build**, and **dry-runs**
  until a key + accounts exist.
- **Cron.** `python3 zernio.py totw` is the Term-of-the-Week entry point — schedule it
  daily/weekly. Deterministic rotation = idempotent (same day → same term).

It reads `data/lexicon.json` (terms, definition history, "travels with", recurrence)
and `data/all_posts.json` (editions + essays), builds a canonical `ContentItem`, and
runs it through per-platform formatters carrying **Token Wisdom voice** — authoritative
but human, a literary streak, dry wit, the mystical wink (🔮) used sparingly. Not
all-caps, not marketing-speak.

---

## 3. Content types (mapped from BLANK AF)

| BLANK AF | Token Wisdom | Source | Builder in `zernio.py` |
|---|---|---|---|
| `drop_announcement` | **`edition`** — the weekly Pearls of Wisdom | `all_posts.json` | `content_item_from_post`, `build_edition_sequence` |
| (n/a) | **`essay`** — A Closer Look / OP-ED / Dear ___ Letter | `all_posts.json` | `content_item_from_post` |
| `feeling_forecast` (daily) | **`term`** — Term of the Week | `lexicon.json` | `term_of_the_week` |
| (n/a) | **`definition_evolution`** — how a term was re-defined over time | `lexicon.json` | `content_item_definition_evolution` |
| `community_spotlight` | **`constellation`** — a term + its co-occurrence cluster | `lexicon.json` `related` | `content_item_constellation_spotlight` |
| (n/a) | **`podcast`** — "The Essay, Aloud" A/B audio companion | podcast feed | inside `build_edition_sequence` |
| (n/a) | **`zeitgeist`** — tag-frequency trend (pillar 4, when built) | `relationships/` | _future_ |

**The Term of the Week is the engine.** ~1,941 evergreen, definitional, citable posts
the corpus already wrote. Definitional content is precisely what LLMs quote, and
recurring terms (62 appear in ≥3 editions) are the highest-value picks. `term_of_the_week`
rotates deterministically (same day → same term, so scheduling is idempotent).

---

## 4. Platform priority (by AI-citation value AND fit)

TW is thought-leadership, not visual streetwear — so the order diverges from BLANK AF.
Text + audio + long-form first; visual networks are phase 2.

| # | Platform | Why |
|---|----------|-----|
| 1 | **LinkedIn** | #2 most-cited domain across ChatGPT/Perplexity/Google AI Mode; long-form is TW's native register |
| 2 | **YouTube** | 16% of LLM answers cite it; TW already has NotebookLM audio + A/B podcast pairs — transcripts = crawlable expertise |
| 3 | **X / Twitter** | Real-time pulse; TW's aphoristic coinages (*Constitutional Forcing*, *Substrate Failure*) are built for it. X API billed at cost — set a cap |
| 4 | **Bluesky** | Early-mover AI-indexing advantage; tech-futures crowd is here |
| 5 | **Mastodon** | Federated, fully crawlable; fediverse overlaps the researcher/builder audience |
| 6 | **Reddit** | r/Futurology, r/artificial, r/technology — authentic long-form, high citation weight |
| 7 | **Threads** | Meta-ecosystem cross-posting |
| 8–9 | Instagram / Pinterest | **Phase 2** — only with a cover/diagram asset (edition covers + Lexicon term cards can carry it) |

Dropped vs. BLANK AF: TikTok, Discord, Telegram, Snapchat — wrong register for a journal
of record. Revisit only if a specific audience justifies it.

---

## 5. Triggers (TW is static + Ghost)

Where posts fire from. TW has no live app server like BLANK AF's `server.ts`, so triggers
hang off the **build pipeline** and (when un-gated) **Ghost webhooks**.

| Trigger | Mechanism | Status |
|---|---|---|
| New edition / essay published | `generate_site.py` → `sync_new_publications(posts)`, diffed against `data/.zernio_state.json` | **WIRED** (editions → 3-post arc; essays → single cross-post) |
| Daily/weekly cron | scheduled job → `python3 zernio.py totw` | **WIRED** (Term of the Week) |
| Term hits recurrence milestone | during `lexicon.build()`, a term crossing 3 / 5 / 10 editions → `content_item_definition_evolution` | _future_ |
| Ghost `post.published` webhook | when Ghost is renewed/un-gated, webhook → `content_item_from_post` | _blocked (Ghost gated)_ |
| Manual / MCP | natural-language publishing in Claude (§7) | available once keyed |

---

## 6. Wire-up checklist

1. `pip install zernio-sdk`
2. Sign up at zernio.com (free, 2 accounts) → create a **Token Wisdom** profile
3. Connect **LinkedIn + X** first (free tier), then YouTube / Bluesky / Mastodon
4. Generate API key → `ZERNIO_API_KEY=sk_…` in the environment
5. Set `TW_PUBLIC_BASE` to the **ungated static site** (never `tokenwisdom.ghost.io`)
6. Populate `ZERNIO_ACC_<PLATFORM>` env vars (see `account_map_from_env()`)
7. In `zernio.py`: uncomment the `from zernio import Zernio` import and the
   `zernio.posts.create_post(...)` call inside `publish_everywhere()`
8. Test: `python3 zernio.py status` (should show `enabled=True`), then `python3 zernio.py term`
9. Schedule the cron: `python3 zernio.py totw` (daily or weekly)

The build-pipeline trigger and the cron entry point are **already wired** (§2) — once
the key + accounts are present they flip from dry-run to live automatically. No code
change beyond step 7.

```bash
# Environment
ZERNIO_API_KEY=sk_your_key_here
TW_PUBLIC_BASE=https://iamkhayyam.github.io/tokenwisdom   # the UNGATED corpus
TW_TIMEZONE=America/Edmonton
ZERNIO_ACC_LINKEDIN=acc_xxx
ZERNIO_ACC_TWITTER=acc_xxx
ZERNIO_ACC_YOUTUBE=acc_xxx
ZERNIO_ACC_BLUESKY=acc_xxx
ZERNIO_ACC_MASTODON=acc_xxx
```

---

## 7. MCP — natural-language publishing

Zernio's MCP server auto-generates 280+ tools from its OpenAPI spec. Add to the Claude
Code / Desktop config and publish by talking:

```json
{
  "mcpServers": {
    "zernio": {
      "url": "https://mcp.zernio.com/mcp",
      "headers": { "Authorization": "Bearer sk_YOUR_API_KEY" }
    }
  }
}
```

- "Post this week's edition to LinkedIn and X with the cover image."
- "Schedule the Term of the Week across all connected platforms for 8am."
- "Spotlight the constellation around *Substrate Failure*."
- "Show me which platforms drove the most reach on the last 5 editions."

---

## 8. Pricing

| Setup | Accounts | Monthly |
|---|---|---|
| Launch (LinkedIn + X) | 2 | **$0** |
| Growth (+ YouTube, Bluesky, Mastodon) | 5 | **$18** |
| Full text stack (+ Reddit, Threads) | 7–8 | **~$30** |

X/Twitter API calls pass through at cost with no markup — set a monthly cap in the
dashboard.

---

## 9. Roadmap

- **Week 1 — Foundation.** Sign up, connect LinkedIn + X, key in env, wire & test one
  real cross-post from `zernio.py`.
- **Week 2 — The evergreen engine.** Stand up the Term of the Week cron. This alone
  produces a steady stream of citable, on-brand surfaces with zero new authoring.
- **Week 3 — Edition arc + triggers.** Hook `build_edition_sequence` into the build
  pipeline; add YouTube/Bluesky/Mastodon; start the constellation + definition-drift
  spotlights.
- **Week 4+ — Optimize.** Analytics on best posting times per platform; A/B long-vs-short;
  feed Zeitgeist (pillar 4) trends in as a content type once built.

---

*Voice reminder for all generated content: authoritative but human. The idea is the
hero; the human curator is the differentiator ("100% Authentic Humanly Chosen"). Dense
ideas, dry wit, the occasional 🔮 — never greeting-card energy, never all-caps hype.
Moving toward technical-journal-of-record while keeping the warmth that makes it
personal. See [PRODUCT.md](PRODUCT.md).*

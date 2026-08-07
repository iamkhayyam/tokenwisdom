"""
Token Wisdom — Search Index
===========================

Our own search. No Algolia, no API key, no monthly bill, no third party holding
the corpus. The whole searchable site is 4.1 MB of essay text and 1,922 Lexicon
terms; compressed it costs less to ship than one feature image, so the index is
just static JSON on Cloudflare Pages next to everything else.

Two artifacts, both built from the same JSON the rest of the build reads:

  docs/search/meta.json      posts (title, excerpt, tags, date) + every Lexicon
                             term (name, definition, category, edition_count).
                             ~120 KB gzipped. Loaded the moment search opens;
                             on its own it already answers title / term / tag /
                             definition queries.

  docs/search/postings.json  inverted index, token -> [post ids], built over
                             post *bodies*. ~330 KB gzipped. Fetched in the
                             background right after meta; when it lands, the
                             same queries start matching full essay text too.

That split is the whole performance story: search is usable after 120 KB and
becomes full-text a moment later, so there is never a spinner in front of the
reader. Both files are content-addressed by the build (search.js reads the
`generated` stamp) and cached hard by the CDN.

Gating mirrors the rest of the build exactly — a post reaches the index only if
it is `visibility: public` AND not in generate_site.HIDDEN_POST_SLUGS. Members
and paid editions are never tokenized, so no gated sentence can be reconstructed
out of the index by anyone who reads the JSON.

Run standalone (`python search_index.py`) or let generate_site.py call build().
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

LEXICON_FILE = DATA / "lexicon.json"
POSTS_FILE = DATA / "all_posts.json"
OUT_DIR = DOCS / "search"

# Words carrying no discriminating power across a corpus that is *entirely*
# about technology — indexing "technology" or "the" costs bytes and returns
# everything. Deliberately short: aggressive stoplists break phrase intent
# ("what is the singularity"), and our postings budget is generous.
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "is", "it", "its",
    "for", "on", "with", "as", "at", "by", "from", "that", "this", "these",
    "those", "be", "are", "was", "were", "been", "being", "will", "would",
    "can", "could", "should", "not", "no", "you", "your", "we", "our", "us",
    "they", "their", "them", "he", "she", "his", "her", "i", "me", "my",
    "have", "has", "had", "do", "does", "did", "so", "if", "then", "than",
    "there", "here", "what", "when", "where", "who", "how", "why", "all",
    "any", "both", "each", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "very", "just", "about", "into", "over", "after",
    "before", "up", "out", "off", "down", "again", "also", "one", "two",
}

# Tokens must start alphanumeric, may carry internal apostrophes/hyphens.
# Keeps "o'reilly", "state-of-the-art", "gpt-4" intact rather than shredding
# them into noise.
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")

MIN_TOKEN_LEN = 3
EXCERPT_CHARS = 200
DEFINITION_CHARS = 220

# Occurrences within one post before it counts as a "strong" body match — the
# piece is about the term, not just brushing past it. Four is where the curve
# separates on this corpus: a passing mention is 1–2, a subject is 5+.
STRONG_TF = 4


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords and 1–2 char noise dropped.

    Mirrored exactly by `tokenize()` in assets/search.js — if you change the
    rules here, change them there or queries stop matching the index.
    """
    return [
        t for t in TOKEN_RE.findall((text or "").lower())
        if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS
    ]


def _clamp(text: str, n: int) -> str:
    """Trim to n chars on a word boundary, with an ellipsis if we cut."""
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut + "…"


def _is_public(post: dict, hidden_slugs: set) -> bool:
    """The single gate. `visibility` covers members/paid; hidden_slugs covers
    posts that render but are deliberately unlisted (see generate_site)."""
    if (post.get("visibility") or "public") != "public":
        return False
    return (post.get("slug") or "") not in hidden_slugs


def _hidden_slugs() -> set:
    """Borrow the canonical hidden set from generate_site so the two can never
    drift. Falls back to empty (index nothing extra) if imported standalone in
    an environment where generate_site won't import."""
    try:
        import generate_site
        return set(generate_site.HIDDEN_POST_SLUGS)
    except Exception:  # noqa: BLE001 — standalone runs still produce a valid index
        return set()


def build(posts=None, terms=None, out_dir: Path = OUT_DIR, quiet: bool = False):
    """Write meta.json + postings.json. Returns a small stats dict.

    `posts` / `terms` may be passed in by generate_site (which already has them
    in memory); otherwise they're loaded from data/.
    """
    if posts is None:
        posts = json.loads(POSTS_FILE.read_text())
    if terms is None:
        terms = json.loads(LEXICON_FILE.read_text())["terms"]

    hidden = _hidden_slugs()
    public = [p for p in posts if _is_public(p, hidden)]
    # Newest first — the client uses array order as its recency tiebreaker, so
    # sorting here means it never has to parse or compare dates at query time.
    public.sort(key=lambda p: (p.get("published_at") or ""), reverse=True)

    # ── meta.json ───────────────────────────────────────────────────────────
    # Positional arrays, not objects. At 2,175 records the key names would be
    # roughly a third of the payload; search.js unpacks by index.
    post_meta = []
    for p in public:
        tags = [
            t.get("name", "") for t in (p.get("tags") or [])
            if not (t.get("name") or "").startswith("#")
        ]
        post_meta.append([
            p.get("title") or "",                        # 0 title
            p.get("slug") or "",                         # 1 slug
            _clamp(p.get("excerpt") or "", EXCERPT_CHARS),  # 2 excerpt
            (p.get("published_at") or "")[:10],          # 3 date
            tags,                                        # 4 tags
            p.get("reading_time") or 0,                  # 5 minutes
        ])

    term_meta = []
    for t in terms:
        term_meta.append([
            t.get("name") or "",                              # 0 name
            t.get("slug") or "",                              # 1 slug
            _clamp(t.get("definition") or "", DEFINITION_CHARS),  # 2 definition
            t.get("category") or "",                          # 3 category
            t.get("edition_count") or 0,                      # 4 appearances
        ])
    # Most-defined terms first, so equal-scoring matches surface the term the
    # newsletter has actually returned to most often.
    term_meta.sort(key=lambda r: -r[4])

    meta = {
        "generated": date.today().isoformat(),
        "posts": post_meta,
        "terms": term_meta,
    }

    # ── postings.json ───────────────────────────────────────────────────────
    # token -> sorted list of post indices (indices into meta["posts"]).
    # Title and excerpt are deliberately *excluded* here: search.js scans those
    # directly out of meta.json, which is already loaded and lets it do prefix
    # matching that a token index can't.
    #
    # Two maps, not one. `t` is every post containing the token; `s` is the
    # subset where it occurs STRONG_TF+ times — the difference between an essay
    # that mentions quantum computing and an essay that is *about* it. Without
    # this, every body-only match scores identically and the ranking collapses
    # to date order. Storing one extra list is far cheaper than storing a term
    # frequency for all 205k postings.
    postings: dict[str, set] = {}
    strong: dict[str, set] = {}
    for i, p in enumerate(public):
        counts: dict[str, int] = {}
        for tok in tokenize(p.get("plaintext") or ""):
            counts[tok] = counts.get(tok, 0) + 1
        for tok, c in counts.items():
            postings.setdefault(tok, set()).add(i)
            if c >= STRONG_TF:
                strong.setdefault(tok, set()).add(i)

    # Delta-encode to base36. Postings are ascending ints over a 253-doc space,
    # so gaps are small and nearly all become one character: ~45% smaller than
    # a JSON array of ints, and search.js decodes it in a single pass.
    def _encode(m):
        out = {}
        for tok, ids in m.items():
            parts, prev = [], 0
            for i in sorted(ids):
                parts.append(_b36(i - prev))
                prev = i
            out[tok] = ".".join(parts)
        return out

    encoded = _encode(postings)
    encoded_strong = _encode(strong)

    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.json"
    post_path = out_dir / "postings.json"
    meta_path.write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False))
    post_path.write_text(json.dumps(
        {"generated": meta["generated"], "docs": len(public),
         "t": encoded, "s": encoded_strong},
        separators=(",", ":"), ensure_ascii=False))

    stats = {
        "posts": len(public),
        "skipped": len(posts) - len(public),
        "terms": len(term_meta),
        "tokens": len(encoded),
        "postings": sum(len(v) for v in postings.values()),
        "strong": sum(len(v) for v in strong.values()),
        "meta_kb": meta_path.stat().st_size / 1000,
        "postings_kb": post_path.stat().st_size / 1000,
    }
    if not quiet:
        print(f"  {stats['posts']} posts indexed ({stats['skipped']} gated/hidden skipped), "
              f"{stats['terms']} terms")
        print(f"  {stats['tokens']:,} tokens / {stats['postings']:,} postings "
              f"({stats['strong']:,} strong)  ·  "
              f"meta {stats['meta_kb']:.0f} KB + postings {stats['postings_kb']:.0f} KB")
    return stats


_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _b36(n: int) -> str:
    if n == 0:
        return "0"
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = _B36[r] + s
    return s


if __name__ == "__main__":
    print("Building search index…")
    build()

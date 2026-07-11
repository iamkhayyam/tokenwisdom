#!/usr/bin/env python3
"""Cross-reference the Lexicon against 'A Closer Look' essays and attach essay
appearances to each term.

The Lexicon's `editions` list is newsletter-only (terms *defined* in the hand-
authored "The Less You Know" glossary). Essays never define terms, but they
*discuss* them. This module finds, per term, which essays mention it — strictly —
and records them under a NEW `essays` field (leaving `editions`/`edition_count`/
`first`/`latest` untouched, so "defined in" semantics stay honest). It also adds
`essay_count` and `first_seen` (earliest of newsletter first-def vs earliest essay).

Strict matching (avoids the LED->"led" / BASIC->"basic" / Technology noise):
  · whole-word, CASE-SENSITIVE against the term's canonical capitalization
  · eligible terms = multi-word, OR acronym/all-caps, OR a capitalized single
    word NOT in GENERIC_BLOCKLIST
Scope: only posts tagged `a-closer-look`.

Usage
-----
  python3 essay_xref.py --dry-run     # impact report, no write
  python3 essay_xref.py               # writes data/lexicon.json (backs up first)

Also exposes attach_essay_appearances(terms, posts) for the lexicon.py pipeline.
"""
from __future__ import annotations
import argparse, json, re, shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import enrich_margins as em  # strip_tags, reused text extraction

ROOT = Path(__file__).resolve().parent
LEXICON_FILE = ROOT / "data" / "lexicon.json"
POSTS_FILE = ROOT / "data" / "all_posts.json"
ESSAY_TAG = "a-closer-look"

# Generic single words that are Lexicon entries but too common to trust as an
# essay "mention" (they'd match sentence-initial capitals everywhere).
GENERIC_BLOCKLIST = {
    "technology", "silicon", "basic", "consciousness", "optimization",
    "manufacturing", "innovation", "automation", "infrastructure", "computing",
    "hardware", "software", "internet", "digital", "algorithm", "network",
    "platform", "cloud", "security", "privacy", "energy", "climate",
    "intelligence", "learning", "productivity", "efficiency", "sustainability",
    "creativity", "experience", "engineering", "development", "science",
    "research", "design", "data", "led", "optimization",
}


def _quarter_of(date_str: str) -> str:
    """'2024-08-22' -> '2024-Q3' (matches lexicon.py's timeline period keys)."""
    y, m = date_str[:4], int(date_str[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def _is_acronym(name: str) -> bool:
    letters = [c for c in name if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(name) <= 6


def build_strict_patterns(terms: list[dict]):
    """One case-sensitive whole-word pattern per eligible term."""
    pats = []
    for t in terms:
        name = t["name"]
        if len(name) < 3 or not (t.get("definition") or "").strip():
            continue
        multi = " " in name
        acro = _is_acronym(name)
        if not (multi or acro):
            # single-word, non-acronym: must be Capitalized and not generic
            if name[:1].islower() or name.lower() in GENERIC_BLOCKLIST:
                continue
        pats.append((t, re.compile(r"\b" + re.escape(name) + r"\b")))  # case-sensitive
    return pats


def _essays(posts: list[dict]) -> list[dict]:
    out = []
    for p in posts:
        if not p.get("html"):
            continue
        slugs = {tg.get("slug") for tg in (p.get("tags") or []) if tg.get("slug")}
        if ESSAY_TAG in slugs:
            out.append(p)
    return out


def attach_essay_appearances(terms: list[dict], posts: list[dict]) -> dict:
    """Mutate terms in place: add `essays`, `essay_count`, `first_seen`.
    Returns an impact summary dict."""
    essays = _essays(posts)
    pats = build_strict_patterns(terms)
    by_slug = {t["slug"]: t for t in terms}

    term_hits: dict[str, list[dict]] = defaultdict(list)
    for p in essays:
        text = em.strip_tags(p.get("html") or "")
        meta = {"slug": p.get("slug"), "title": p.get("title"),
                "date": (p.get("published_at") or "")[:10], "source": "essay"}
        for t, pat in pats:
            if pat.search(text):
                term_hits[t["slug"]].append(meta)

    earlier = 0
    for t in terms:
        hits = sorted(term_hits.get(t["slug"], []), key=lambda m: m["date"] or "9999")
        t["essays"] = hits
        t["essay_count"] = len(hits)
        nl_first = (t.get("first") or {}).get("date") or "9999"
        e_first = hits[0]["date"] if hits else None
        if e_first and e_first < nl_first:
            earlier += 1

        # ── merged, chronological appearances (defined = newsletter glossary,
        #    discussed = essay). One source of truth for the combined metrics. ──
        appearances = []
        for ed in t.get("editions", []):
            appearances.append({
                "date": ed.get("date", ""), "kind": "defined",
                "slug": ed.get("slug"), "title": ed.get("title"),
                "edition": ed.get("edition"), "week": ed.get("week"),
                "source": ed.get("source"),
            })
        for h in hits:
            appearances.append({
                "date": h["date"], "kind": "discussed",
                "slug": h["slug"], "title": h["title"],
                "edition": None, "week": None, "source": "essay",
            })
        appearances.sort(key=lambda a: a["date"] or "9999")
        t["appearances"] = appearances
        t["appearance_count"] = len(appearances)
        dates = [a["date"] for a in appearances if a["date"]]
        t["first_seen"] = min(dates) if dates else (nl_first if nl_first != "9999" else None)
        t["latest_seen"] = max(dates) if dates else None

        # rebuild the per-quarter timeline to count ALL appearances (so the
        # "arc" chart reflects essays too), over the existing global periods.
        periods = [p["period"] for p in t.get("timeline", [])]
        counts = {p: 0 for p in periods}
        for a in appearances:
            q = _quarter_of(a["date"]) if a["date"] else None
            if q in counts:
                counts[q] += 1
        if periods:
            t["timeline"] = [{"period": p, "count": counts[p]} for p in periods]

    return {
        "essays_scanned": len(essays),
        "eligible_terms": len(pats),
        "terms_with_essays": sum(1 for t in terms if t["essay_count"]),
        "total_terms": len(terms),
        "pairs": sum(t["essay_count"] for t in terms),
        "terms_essay_earlier_than_first_def": earlier,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lex = json.load(open(LEXICON_FILE))
    posts = json.load(open(POSTS_FILE))
    posts = posts if isinstance(posts, list) else posts.get("posts", posts)
    terms = lex["terms"]

    summary = attach_essay_appearances(terms, posts)

    print("=" * 60)
    print("ESSAY CROSS-REFERENCE  (A Closer Look, strict)")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:38s}: {v}")
    print()
    ranked = sorted((t for t in terms if t["essay_count"]),
                    key=lambda t: -t["essay_count"])
    print("── Top 25 terms by essay coverage (strict) ──")
    for t in ranked[:25]:
        print(f"  {t['essay_count']:3d}  {t['name'][:32]:32s} (nl eds:{t['edition_count']}, cat:{t['category']})")

    if args.dry_run:
        print("\nDRY RUN — no file written.")
        return

    backup = LEXICON_FILE.with_suffix(".json.bak")
    shutil.copy(LEXICON_FILE, backup)
    lex["essay_xref_generated"] = datetime.now().strftime("%Y-%m-%d")
    json.dump(lex, open(LEXICON_FILE, "w"), indent=2, ensure_ascii=False)
    print(f"\nBacked up → {backup.name}; wrote essay appearances into {LEXICON_FILE.name}")


if __name__ == "__main__":
    main()

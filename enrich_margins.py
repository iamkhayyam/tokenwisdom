#!/usr/bin/env python3
"""Auto-generate right-gutter margin notes for essays.

Scans each essay's HTML and produces a JSON annotation file
(data/margin_notes.json) mapping slug → list of notes. Note kinds:

  term        — first occurrence of a Lexicon entry, prefer capitalized
                / multi-word matches; renders as .tw-note--term with a
                definition and "In the Lexicon →" link.
  acronym     — first occurrence of a Lexicon Acronyms entry (BMI, LLM,
                RAG, …); expansion sourced from the entry's `definition`.
  quote       — pulled from an existing <blockquote> in the prose; drops
                a right-gutter tw-note--quote next to it.
  stat        — sentences containing punchy figures (~12%, $50M, 3.2×,
                140 mph); rendered as .tw-note--stat with the number
                lifted out.

The generator is idempotent: reruns produce the same JSON so the file
is safe to diff-review before deploying. generate_site.py picks up
data/margin_notes.json and injects notes into the essay body at build
time via essay_template.apply_margin_notes.

Cap per post: MAX_NOTES_PER_POST (default 4). Cap prevents gutter
crowding on shorter essays; ranks: quote > stat > term > acronym.

Usage
-----
  python3 enrich_margins.py                # writes data/margin_notes.json
  python3 enrich_margins.py --dry-run      # prints a summary; no write
  python3 enrich_margins.py --slug foo     # process a single post
"""

from __future__ import annotations

import argparse
import html as html_stdlib
import json
import re
from pathlib import Path
from typing import Iterable

BACKUP_DIR = Path(__file__).resolve().parent
POSTS_FILE = BACKUP_DIR / "data" / "all_posts.json"
LEXICON_FILE = BACKUP_DIR / "data" / "lexicon.json"
OUT_FILE = BACKUP_DIR / "data" / "margin_notes.json"

MAX_NOTES_PER_POST = 4

# Posts that ship hand-authored notes; skip auto-enrichment for them.
SKIP_SLUGS = {
    "the-sky-has-been-warning-us-since-1859",
}

# Section-tag slugs — used to detect essays vs newsletters. Same set as
# generate_site.py. Kept in sync manually; if that set drifts, this
# script only over- or under-covers a few posts, no data corruption.
NEWSLETTER_TAG_SLUGS = {"worthafortune", "pearls-of-wisdom"}


# ── HTML helpers ────────────────────────────────────────────────────

_PARA_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCKQUOTE_RE = re.compile(r"<blockquote\b[^>]*>(.*?)</blockquote>", re.DOTALL | re.IGNORECASE)


def strip_tags(html_str: str) -> str:
    return html_stdlib.unescape(_TAG_RE.sub("", html_str)).strip()


def paragraph_snippets(html_str: str) -> list[tuple[str, str]]:
    """Return [(inner_html, plain_text)] for each <p> in reading order."""
    out = []
    for m in _PARA_RE.finditer(html_str):
        inner = m.group(1)
        text = strip_tags(inner)
        if text:
            out.append((inner, text))
    return out


def sentence_containing(text: str, needle: str) -> str:
    """Return the sentence around `needle` in `text` (rough split)."""
    idx = text.lower().find(needle.lower())
    if idx == -1:
        return text[:180]
    start = max(0, text.rfind(".", 0, idx))
    if start > 0:
        start += 1
    end = text.find(".", idx + len(needle))
    if end == -1:
        end = len(text)
    return text[start:end].strip()


# ── Note builders ───────────────────────────────────────────────────

def _term_note(name: str, definition: str) -> str:
    return (
        '<span class="tw-note tw-note--term">'
        f'<span class="twn-term">{html_stdlib.escape(name)}</span>'
        f'<span class="twn-def">{html_stdlib.escape(definition)}</span>'
        '<a class="twn-link" href="/lexicon/">In the Lexicon &rarr;</a>'
        '</span>'
    )


def _acronym_note(acronym: str, expansion: str) -> str:
    return (
        '<span class="tw-note tw-note--term">'
        f'<span class="twn-term">{html_stdlib.escape(acronym)}</span>'
        f'<span class="twn-def">{html_stdlib.escape(expansion)}</span>'
        '<a class="twn-link" href="/lexicon/">In the Lexicon &rarr;</a>'
        '</span>'
    )


def _quote_note(text: str) -> str:
    # Trim quote to a single sentence-worth for the gutter
    trimmed = text.strip().rstrip(".").strip()
    if len(trimmed) > 180:
        trimmed = trimmed[:177].rsplit(" ", 1)[0] + "…"
    return f'<span class="tw-note tw-note--quote">&ldquo;{html_stdlib.escape(trimmed)}&rdquo;</span>'


def _stat_note(number: str, caption: str) -> str:
    return (
        '<span class="tw-note tw-note--stat">'
        f'<span class="twn-num">{html_stdlib.escape(number)}</span>'
        f'<span class="twn-cap">{html_stdlib.escape(caption)}</span>'
        '</span>'
    )


# ── Detectors ───────────────────────────────────────────────────────

def find_term_matches(text: str, term_index: list[dict]) -> list[dict]:
    """First occurrence of each lexicon term with a real definition.

    Longer names win over shorter substrings (LLM vs LLM Ops), so terms
    are searched longest-first. Case-sensitive for multi-word matches,
    case-insensitive for single-word so 'quantum computing' catches
    'Quantum computing'.
    """
    matches = []
    for term in term_index:
        name = term["name"]
        if len(name) < 3:
            continue
        # Skip if we've already found a match for this exact position range
        if " " in name:
            pat = re.compile(r"\b" + re.escape(name) + r"\b")
        else:
            pat = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        m = pat.search(text)
        if not m:
            continue
        matches.append({
            "kind": "term",
            "trigger": name,
            "position": m.start(),
            "note_html": _term_note(term["name"], term["definition"]),
            "score": 100 + len(name.split()) * 5,   # multi-word terms rank higher
        })
    return matches


ACRONYM_PAT = re.compile(r"\b([A-Z]{2,5})\b")


def find_acronym_matches(text: str, acronym_map: dict[str, str]) -> list[dict]:
    """Match uppercase 2-5 letter tokens against the acronym dict."""
    matches = []
    seen = set()
    for m in ACRONYM_PAT.finditer(text):
        ac = m.group(1)
        if ac in seen:
            continue
        seen.add(ac)
        if ac in acronym_map:
            matches.append({
                "kind": "acronym",
                "trigger": ac,
                "position": m.start(),
                "note_html": _acronym_note(ac, acronym_map[ac]),
                "score": 60,
            })
    return matches


def find_quote_matches(post_html: str) -> list[dict]:
    """Pull each <blockquote>'s text as a gutter quote note."""
    matches = []
    for m in _BLOCKQUOTE_RE.finditer(post_html):
        text = strip_tags(m.group(1))
        if not text or len(text) < 20:
            continue
        first_words = text.split()[:6]
        trigger = " ".join(first_words)
        matches.append({
            "kind": "quote",
            "trigger": trigger,
            "position": m.start(),
            "note_html": _quote_note(text),
            "score": 200,
        })
    return matches


STAT_PAT = re.compile(
    r"(~?\$?[0-9]+(?:[.,][0-9]+)?\s*(?:%|×|x|k|M|B|bn|mn|mph|ms|GW|MW|kW|Hz|MHz|GHz|nm|mm|km|mi))",
    re.IGNORECASE,
)


def find_stat_matches(text: str) -> list[dict]:
    matches = []
    seen = set()
    for m in STAT_PAT.finditer(text):
        num = m.group(1).strip()
        key = num.lower()
        if key in seen:
            continue
        seen.add(key)
        caption = sentence_containing(text, num)
        # Trim caption; keep it terse for the gutter
        if len(caption) > 140:
            caption = caption[:137].rsplit(" ", 1)[0] + "…"
        matches.append({
            "kind": "stat",
            "trigger": num,
            "position": m.start(),
            "note_html": _stat_note(num, caption),
            "score": 150,
        })
    return matches


# ── Anchor resolution ──────────────────────────────────────────────

def paragraph_prefix(post_html: str, needle_position: int) -> str | None:
    """Return the first ~40 chars of the paragraph containing `needle_position`
    (in the plain-text sense). Used by apply_margin_notes to find the anchor
    <p>. Returns None if we can't locate a paragraph.
    """
    for m in _PARA_RE.finditer(post_html):
        inner = m.group(1)
        text = strip_tags(inner)
        if not text:
            continue
        # We can't map plain-text positions back to HTML positions perfectly,
        # so we use a substring check: does this paragraph contain the trigger?
        if 0 <= needle_position < m.start():
            continue
        if needle_position <= m.end():
            words = text.split()
            return " ".join(words[:6])
    return None


def anchor_for_match(post_html: str, match: dict, plain_text: str) -> str | None:
    """Given a match against the concatenated plain-text of a post, return
    the paragraph prefix (~6 words) that we'll use to re-anchor at build
    time. Since we scan paragraph-by-paragraph, we know which one the
    match came from — we just need to remember it.
    """
    return match.get("_anchor_prefix")


# ── Main pipeline ──────────────────────────────────────────────────

def is_essay(post: dict) -> bool:
    if not post.get("html"):
        return False
    slugs = {t.get("slug") for t in (post.get("tags") or []) if t.get("slug")}
    return not (slugs & NEWSLETTER_TAG_SLUGS)


def enrich_post(post: dict, term_index: list[dict], acronym_map: dict[str, str]) -> list[dict]:
    """Produce a de-duplicated, capped list of note dicts for one essay."""
    slug = post.get("slug", "")
    html_body = post.get("html") or ""

    # Quote notes are anchored to the paragraph immediately before the
    # blockquote in the original HTML. Simpler: attach to the first
    # paragraph *after* the blockquote for post-context.
    all_notes: list[dict] = []
    for q in find_quote_matches(html_body):
        # Anchor: first 6 words of the first paragraph following the quote
        after = html_body[q["position"]:]
        para_m = _PARA_RE.search(after[after.find("</blockquote>"):])
        if para_m:
            anchor = " ".join(strip_tags(para_m.group(1)).split()[:6])
            q["_anchor_prefix"] = anchor
            all_notes.append(q)

    # For text-based matches (term, acronym, stat), we scan per paragraph
    # so we already know the anchor.
    used_triggers: set[str] = set()
    for inner, text in paragraph_snippets(html_body):
        anchor = " ".join(text.split()[:6])
        para_matches: list[dict] = []
        para_matches.extend(find_term_matches(text, term_index))
        para_matches.extend(find_acronym_matches(text, acronym_map))
        para_matches.extend(find_stat_matches(text))
        for match in para_matches:
            trig = match["trigger"].lower()
            if trig in used_triggers:
                continue
            used_triggers.add(trig)
            match["_anchor_prefix"] = anchor
            all_notes.append(match)

    # Rank + cap.
    all_notes.sort(key=lambda m: m["score"], reverse=True)
    kept: list[dict] = []
    used_anchors: set[str] = set()
    for note in all_notes:
        # Don't stack two notes on the same paragraph
        if note["_anchor_prefix"] in used_anchors:
            continue
        used_anchors.add(note["_anchor_prefix"])
        kept.append({
            "kind": note["kind"],
            "trigger": note["trigger"],
            "anchor": note["_anchor_prefix"],
            "note_html": note["note_html"],
        })
        if len(kept) >= MAX_NOTES_PER_POST:
            break
    return kept


def build_acronym_map(lex_terms: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in lex_terms:
        if t.get("category") != "Acronyms":
            continue
        name = (t.get("name") or "").strip()
        defn = (t.get("definition") or "").strip()
        # Only include short all-uppercase acronyms with real definitions
        if 2 <= len(name) <= 5 and name.isupper() and defn and defn.lower() != name.lower():
            out[name] = defn
    return out


def build_term_index(lex_terms: list[dict]) -> list[dict]:
    """Longer names first so multi-word terms match before single-word substrings."""
    filtered = [
        t for t in lex_terms
        if t.get("category") in ("Technologies", "Concepts", "Technical Terms")
        and (t.get("definition") or "").strip()
        and len((t.get("name") or "")) >= 3
    ]
    filtered.sort(key=lambda t: -len(t.get("name") or ""))
    return filtered


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-generate margin notes for essays.")
    ap.add_argument("--dry-run", action="store_true", help="Print stats, don't write.")
    ap.add_argument("--slug", help="Process only a single post by slug.")
    args = ap.parse_args()

    posts = json.load(POSTS_FILE.open())
    lex = json.load(LEXICON_FILE.open())
    lex_terms = lex["terms"]

    term_index = build_term_index(lex_terms)
    acronym_map = build_acronym_map(lex_terms)
    print(f"Lexicon: {len(term_index)} term candidates, {len(acronym_map)} acronyms")

    essays = [p for p in posts if is_essay(p) and p.get("slug") not in SKIP_SLUGS]
    if args.slug:
        essays = [p for p in essays if p.get("slug") == args.slug]
        if not essays:
            print(f"No essay found for slug: {args.slug}")
            return
    print(f"Essays to enrich: {len(essays)}")

    output: dict[str, list[dict]] = {}
    kind_totals = {"term": 0, "acronym": 0, "quote": 0, "stat": 0}
    for post in essays:
        notes = enrich_post(post, term_index, acronym_map)
        if not notes:
            continue
        output[post["slug"]] = notes
        for n in notes:
            kind_totals[n["kind"]] += 1

    print(f"\nEnriched: {len(output)} posts")
    print("Note kinds:")
    for k, n in kind_totals.items():
        print(f"  {n:4}  {k}")

    if args.dry_run:
        print("\n(dry-run: not writing)")
        return

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote: {OUT_FILE}")


if __name__ == "__main__":
    main()

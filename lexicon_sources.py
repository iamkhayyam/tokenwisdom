#!/usr/bin/env python3
"""
Harvest the hand-authored "The Less You Know" glossary from every edition.

Two sources, one normalized output:
  · corpus HTML  — editions backed up in data/all_posts.json (<= ed 153)
  · newsletter PDFs — editions newer than the backup (155-159), parsed from
    the PDFs the author exports each week

Each edition's glossary uses 4-5 category buckets whose labels have drifted over
time ("Latest Technologies & Innovations" -> "Technologies Referenced", etc.);
we normalize them to one canonical taxonomy. The output is a list of edition
records that lexicon.py turns into the Lexicon.

A normalized edition:
  {
    "edition": 153, "week": 13, "date": "2026-03-31",
    "title": "...", "slug": "...", "source": "corpus" | "pdf",
    "entries": [ {"term": "...", "definition": "...", "category": "Concepts"}, ... ],
  }
"""

import json
import re
import html as ihtml
import subprocess
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path(__file__).parent
DATA_DIR = BACKUP_DIR / "data"

# Canonical taxonomy — collapses the drifting per-edition bucket labels.
CANON = {
    "latest technologies & innovations": "Technologies",
    "latest technologies and innovations": "Technologies",
    "technologies referenced": "Technologies",
    "technology referenced": "Technologies",
    "most important topics": "Concepts",
    "core concepts": "Concepts",
    "key concepts": "Concepts",
    "topics referenced": "Concepts",
    "technical terms": "Technical Terms",
    "technical references": "Technical Terms",
    "acronyms": "Acronyms",
    "acronyms & abbreviations": "Acronyms",
    "people and works cited": "People & Works",
    "people and works cited this edition": "People & Works",
    "people & works cited": "People & Works",
    "people, works & references": "People & Works",
}
CATEGORY_ORDER = ["Technologies", "Concepts", "Technical Terms", "Acronyms", "People & Works"]
SECTION_TITLE_RX = re.compile(r"the less you know", re.IGNORECASE)


def canon_category(label):
    key = re.sub(r"\s+", " ", (label or "").strip().lower()).strip(" :")
    return CANON.get(key, label.strip() if label else "Concepts")


def _clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = ihtml.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _clean_term(t):
    return _clean(t).strip(" :—–-")


def _clean_def(d):
    d = _clean(d).strip()
    d = re.sub(r"^[:—–-]\s*", "", d)            # leading separator
    d = re.sub(r"^\((.*)\)$", r"\1", d.strip())  # acronym form "(Expansion)" -> "Expansion"
    d = re.sub(r"\s+\d{1,2}$", "", d)            # trailing footnote marker ("… non-compressible 3")
    return d.strip()


EDITION_RX = re.compile(r"(\d+)(?:st|nd|rd|th)\s+edition", re.IGNORECASE)
WEEK_RX = re.compile(r"week\s*[-_/\\\s]*0?(\d{1,2})", re.IGNORECASE)


# ============================================================
# CORPUS (HTML) SOURCE
# ============================================================

_FOOTER_MARKERS = ["until next time", "this newsletter was curated"]


def _html_section(htmlc):
    """Return the HTML from the last 'The Less You Know' heading to the footer/end.

    Category headers drift between <h2> and <h3> across editions, so we do NOT cut
    at the next heading — we run to a footer marker (or the end of the post).
    """
    matches = [m for m in re.finditer(r"(?is)<h2[^>]*>(.*?)</h2>", htmlc)
               if SECTION_TITLE_RX.search(_clean(m.group(1)))]
    if not matches:
        return ""
    sec = htmlc[matches[-1].end():]
    low = sec.lower()
    cut = min([low.find(mk) for mk in _FOOTER_MARKERS if low.find(mk) > 0] or [len(sec)])
    return sec[:cut]


def _parse_html_entries(section):
    """Yield (term, definition, canonical_category) from a Less You Know section.

    Handles category headers at any heading level (h2/h3/h4); entries are <li>
    (with the term in <strong>). Stops collecting when a non-glossary heading
    appears (the footer)."""
    parts = re.split(r"(?is)(<h[234][^>]*>.*?</h[234]>)", section)
    cur = None
    for chunk in parts:
        c = chunk.strip()
        if re.match(r"(?is)^<h[234]", c):
            txt = _clean(c)
            low = re.sub(r"\s+", " ", txt.lower()).strip(" :")
            if SECTION_TITLE_RX.search(txt) or low == "the more you learn" or not low:
                continue
            cur = CANON.get(low)          # None for non-glossary headings -> skip entries
            continue
        if cur is None:
            continue
        items = re.findall(r"(?is)<li>(.*?)</li>", chunk)
        if not items:                     # fallback: <p><strong>Term:</strong> def</p>
            items = [m.group(0) for m in re.finditer(r"(?is)<p>\s*<strong>.*?</p>", chunk)]
        for inner in items:
            mb = re.match(r"(?is)\s*(?:<p>)?\s*<strong>(.*?)</strong>(.*)", inner)
            if mb:
                term, rest = mb.group(1), mb.group(2)
            else:
                m2 = re.match(r"(?s)\s*([^:—–-]{2,80})[:—–-]\s*(.*)", _clean(inner))
                if not m2:
                    continue
                term, rest = m2.group(1), m2.group(2)
            term = _clean_term(term)
            definition = _clean_def(rest)
            if term and 1 < len(term) <= 80:
                yield term, definition, cur


def from_corpus(posts):
    editions = []
    for p in posts:
        section = _html_section(p.get("html") or "")
        if not section:
            continue
        entries = [{"term": t, "definition": d, "category": c}
                   for t, d, c in _parse_html_entries(section)]
        if not entries:
            continue
        title = p.get("title") or ""
        em = EDITION_RX.search(title)
        wm = WEEK_RX.search(title) or WEEK_RX.search(p.get("slug") or "")
        editions.append({
            "edition": int(em.group(1)) if em else None,
            "week": int(wm.group(1)) if wm else None,
            "date": (p.get("published_at") or "")[:10],
            "title": title,
            "slug": p.get("slug") or "",
            "source": "corpus",
            "entries": entries,
        })
    return editions


# ============================================================
# PDF SOURCE
# ============================================================

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}


def _pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                          capture_output=True, text=True).stdout


_DATE_RX = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+(\d{1,2})(?:st|nd|rd|th)?[^\n]{0,40}?(20\d{2})",
    re.IGNORECASE)


def _pdf_date(txt):
    """Find a 'Month D[…]YEAR' date — tolerant of ordinals, ranges, emoji, and
    cross-month spans ('March 29–April 4th, 2026', 'July 20th 🧿 July 26th, 2025').
    Prefer the footer (last lines), fall back to the full document."""
    for region in (txt[-1600:], txt):
        m = _DATE_RX.search(region)
        if m:
            mo, day, yr = MONTHS[m.group(1).lower()], int(m.group(2)), int(m.group(3))
            try:
                return datetime(yr, mo, day).strftime("%Y-%m-%d")
            except ValueError:
                return f"{yr}-{mo:02d}-01"
    return ""


def _parse_pdf_entries(txt):
    """Parse the Less You Know section from layout text into (term, def, category)."""
    matches = list(SECTION_TITLE_RX.finditer(txt))
    if not matches:
        return []
    sec = txt[matches[-1].end():]
    # Stop at common footer markers.
    for stop in ["Until next time", "This newsletter was curated", "🔮 Token Wisdom ·",
                 "Token Wisdom ·"]:
        i = sec.find(stop)
        if i > 200:
            sec = sec[:i]
            break

    lines = [ln.rstrip() for ln in sec.splitlines()]
    cat_lookup = {k: v for k, v in CANON.items()}
    entries = []
    cur_cat = "Concepts"
    cur_term = None
    cur_def = []

    def flush():
        nonlocal cur_term, cur_def
        if cur_term:
            d = _clean_def(" ".join(cur_def))
            if len(cur_term) <= 80:
                entries.append({"term": _clean_term(cur_term),
                                "definition": d, "category": cur_cat})
        cur_term, cur_def = None, []

    for raw in lines:
        line = re.sub(r"^[•·▪‣*]\s*", "", raw.strip())   # drop leading bullet glyph
        if not line:
            continue
        low = re.sub(r"\s+", " ", line.lower()).strip(" :")
        if low in cat_lookup:                       # category header line (any case)
            flush()
            cur_cat = cat_lookup[low]
            continue
        if low.startswith("a glossary of") or low.startswith("the more you learn"):
            continue
        # A new term starts the line, in one of three forms:
        #   "Term: definition"  ·  "Term — definition"  ·  "ACR (Expansion)"
        mterm = re.match(r"^([A-Z][A-Za-z0-9 ,&/().+'\"%-]{1,70}?)\s*[:—–]\s+(.*)$", line)
        macr = re.match(r"^([A-Z0-9][A-Za-z0-9/.\-]{0,11})\s+\((.+)\)\s*$", line)
        if mterm:
            flush()
            cur_term, cur_def = mterm.group(1), [mterm.group(2)]
        elif macr:
            flush()
            cur_term, cur_def = macr.group(1), [macr.group(2)]
        elif cur_term:                              # continuation of definition
            cur_def.append(line)
    flush()
    return entries


_FNAME_ED_RX = re.compile(r"^(\d{2,3})(?:st|nd|rd|th)\b", re.IGNORECASE)


def discover_pdfs(pdf_dir, exclude_editions=()):
    """Find one canonical newsletter PDF per edition under pdf_dir.

    Newsletters are named like '154th-edition--token-wisdom--week-14.pdf' or
    '90th Edition ... Pearls of Wisdom.pdf' (leading edition number). We skip
    'A Closer Look' essay exports ('acl…') and dedupe '(1)/(2)' variants,
    returning only editions NOT already in exclude_editions (e.g. the corpus).
    """
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        return []
    exclude = set(exclude_editions)
    by_ed = {}
    for p in pdf_dir.rglob("*.pdf"):
        m = _FNAME_ED_RX.match(p.name)
        if not m:
            continue
        ed = int(m.group(1))
        if ed in exclude:
            continue
        cur = by_ed.get(ed)
        # Prefer files without a "(1)" dup suffix, then the shortest name.
        score = (("(" in p.name), len(p.name))
        if cur is None or score < cur[0]:
            by_ed[ed] = (score, p)
    return [v[1] for _, v in sorted(by_ed.items())]


def from_pdfs(pdf_paths):
    editions = []
    for path in pdf_paths:
        path = Path(path)
        if not path.exists():
            continue
        txt = _pdf_text(path)
        entries = _parse_pdf_entries(txt)
        if not entries:
            continue
        head = txt[:1500]
        em = EDITION_RX.search(head) or EDITION_RX.search(path.name)
        wm = WEEK_RX.search(head) or WEEK_RX.search(path.name)
        editions.append({
            "edition": int(em.group(1)) if em else None,
            "week": int(wm.group(1)) if wm else None,
            "date": _pdf_date(txt),
            "title": re.sub(r"\s+", " ", head.splitlines()[0]).strip() if head.strip() else path.stem,
            "slug": path.stem,
            "source": "pdf",
            "entries": entries,
        })
    return editions


# ============================================================
# COMBINE
# ============================================================

def harvest(posts, pdf_paths=()):
    """Return normalized editions from corpus + PDFs, de-duplicated by edition no."""
    eds = from_corpus(posts)
    seen = {e["edition"] for e in eds if e["edition"]}
    for e in from_pdfs(pdf_paths):
        if e["edition"] and e["edition"] in seen:
            continue                      # corpus wins when both exist
        eds.append(e)
        if e["edition"]:
            seen.add(e["edition"])
    eds.sort(key=lambda e: e["date"] or "")
    return eds


if __name__ == "__main__":
    from collections import Counter, defaultdict
    posts = json.load(open(DATA_DIR / "all_posts.json"))
    tokn = Path("/Volumes/SSD/✨ TOKN")
    pdfs = sorted(tokn.glob("*token-wisdom*week*.pdf")) if tokn.exists() else []
    eds = harvest(posts, pdfs)
    total = sum(len(e["entries"]) for e in eds)
    print(f"editions harvested: {len(eds)}  (corpus {sum(e['source']=='corpus' for e in eds)}, "
          f"pdf {sum(e['source']=='pdf' for e in eds)})")
    print(f"total glossary entries: {total}  (avg {total/len(eds):.1f}/edition)")
    cats = Counter(en["category"] for e in eds for en in e["entries"])
    print("by category:", dict(cats))
    # distinct terms + recurrence
    term_eds = defaultdict(set)
    for e in eds:
        for en in e["entries"]:
            term_eds[en["term"].lower()].add(e["edition"] or e["date"])
    print(f"distinct terms (case-insensitive): {len(term_eds)}")
    recur = sorted(((len(v), t) for t, v in term_eds.items()), reverse=True)
    print(f"recurring (>=3 editions): {sum(1 for n,_ in recur if n>=3)}")
    for n, t in recur[:20]:
        print(f"  {n:3d}×  {t}")
    print("\nsample edition (latest):")
    e = eds[-1]
    print(f"  ed{e['edition']} W{e['week']} {e['date']} [{e['source']}] — {len(e['entries'])} entries")
    for en in e["entries"][:6]:
        print(f"    · ({en['category']}) {en['term']}: {en['definition'][:90]}")

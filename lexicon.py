#!/usr/bin/env python3
"""
Token Wisdom — The Lexicon.

A living glossary built from the hand-authored "The Less You Know" section that
closes each edition (see lexicon_sources.py for the harvester). Every term, its
definition, and its category come straight from the newsletter — this is the
author's own evolving vocabulary, not machine-inferred.

For each distinct term we compute, across every edition that glossed it:
  · the canonical definition (most recent) + the full definition history
  · how many editions defined it, when it first appeared, when last
  · a per-quarter sparkline of when it was part of the working vocabulary
  · "travels with" — terms repeatedly glossed in the same editions (co-occurrence)

Output:
  · docs/lexicon/index.html   — filterable index + a "core vocabulary" hero
  · docs/lexicon/<slug>.html  — one page per term (SEO long-tail)
  · data/lexicon.json         — reusable data layer (feeds Constellation / Zeitgeist)

Reuses the editorial design system from generate_site.py. Run generate_site.py
(which wipes & rebuilds docs/ and calls build() here), or run this standalone to
refresh just the lexicon against an existing docs/.
"""

import json
import re
import html as ihtml
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import lexicon_sources as src
import tw_theme as theme

BACKUP_DIR = Path(__file__).parent
DATA_DIR = BACKUP_DIR / "data"
DOCS_DIR = BACKUP_DIR / "docs"

# Default place to look for edition PDFs that fill gaps the corpus backup lacks
# (editions newer than the last backup, plus a few the backup never glossed).
PDF_DIR = Path("/Volumes/SSD/✨ TOKN")

CAT_COLOR = {
    "Technologies": "teal",
    "Concepts": "accent",
    "Technical Terms": "gold",
    "Acronyms": "teal",
    "People & Works": "accent",
}
COLOR_VAR = {"accent": "var(--accent)", "teal": "var(--teal)", "gold": "var(--gold)"}


def esc(s):
    return ihtml.escape(str(s or ""))


def slugify(name):
    s = name.lower()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "term"


def norm_key(name):
    return re.sub(r"\s+", " ", name.strip().lower())


def quarter_of(date_str):
    y, m = int(date_str[:4]), int(date_str[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def quarter_keys(start, end):
    sy, sq = int(start[:4]), (int(start[5:7]) - 1) // 3 + 1
    ey, eq = int(end[:4]), (int(end[5:7]) - 1) // 3 + 1
    keys, y, q = [], sy, sq
    while (y, q) <= (ey, eq):
        keys.append(f"{y}-Q{q}")
        q += 1
        if q > 4:
            q, y = 1, y + 1
    return keys


# ============================================================
# AGGREGATE
# ============================================================

def aggregate(editions):
    """Collapse per-edition glossary entries into one record per distinct term."""
    editions = [e for e in editions if e.get("date")]
    editions.sort(key=lambda e: e["date"])

    # quarter window across all glossary editions
    dates = [e["date"] for e in editions]
    qkeys = quarter_keys(dates[0], dates[-1]) if dates else []

    terms = {}  # norm_key -> record
    edition_terms = []  # list of (edition, set(norm_keys)) for co-occurrence

    for e in editions:
        ed_label = (f"{e['edition']}th" if e.get("edition") else e["date"])
        keys_here = set()
        for en in e["entries"]:
            term, definition, cat = en["term"], en["definition"], en["category"]
            k = norm_key(term)
            if not k:
                continue
            keys_here.add(k)
            t = terms.get(k)
            if t is None:
                t = terms[k] = {
                    "key": k,
                    "surface": Counter(),
                    "categories": Counter(),
                    "defs": [],           # [{text, edition, date, slug, title, source}]
                    "editions": [],       # [{edition, week, date, slug, title, source}]
                    "_qcount": Counter(),
                }
            t["surface"][term] += 1
            if cat:
                t["categories"][cat] += 1
            if definition:
                t["defs"].append({
                    "text": definition, "edition": e.get("edition"), "date": e["date"],
                    "slug": e["slug"], "title": e["title"], "source": e["source"],
                })
            t["editions"].append({
                "edition": e.get("edition"), "week": e.get("week"), "date": e["date"],
                "slug": e["slug"], "title": e["title"], "source": e["source"],
            })
            t["_qcount"][quarter_of(e["date"])] += 1
        edition_terms.append((e, keys_here))

    # co-occurrence: how often two terms share an edition's glossary
    cooc = defaultdict(Counter)
    for _, keys in edition_terms:
        ks = list(keys)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                cooc[ks[i]][ks[j]] += 1
                cooc[ks[j]][ks[i]] += 1

    # finalize
    used_slugs = {}
    out = []
    for k, t in terms.items():
        name = t["surface"].most_common(1)[0][0]
        category = t["categories"].most_common(1)[0][0] if t["categories"] else "Concepts"
        slug = slugify(name)
        if slug in used_slugs:
            used_slugs[slug] += 1
            slug = f"{slug}-{used_slugs[slug]}"
        else:
            used_slugs[slug] = 1

        defs_sorted = sorted(t["defs"], key=lambda d: d["date"])
        # distinct definition history (drop consecutive identical / near-identical)
        history = []
        for d in defs_sorted:
            norm = re.sub(r"\s+", " ", d["text"].lower()).strip()
            if not history or re.sub(r"\s+", " ", history[-1]["text"].lower()).strip() != norm:
                history.append(d)
        canonical = history[-1]["text"] if history else ""

        eds_sorted = sorted(t["editions"], key=lambda d: d["date"])
        # unique editions by date
        seen_dates, eds_unique = set(), []
        for d in eds_sorted:
            if d["date"] not in seen_dates:
                seen_dates.add(d["date"])
                eds_unique.append(d)

        related = [{"key": ok, "shared": n} for ok, n in cooc[k].most_common(8)]

        out.append({
            "name": name,
            "slug": slug,
            "key": k,
            "category": category,
            "color": CAT_COLOR.get(category, "accent"),
            "definition": canonical,
            "definition_history": [
                {"text": d["text"], "edition": d["edition"], "date": d["date"], "slug": d["slug"]}
                for d in history
            ],
            "edition_count": len(eds_unique),
            "first": eds_unique[0],
            "latest": eds_unique[-1],
            "editions": eds_unique,
            "timeline": [{"period": q, "count": t["_qcount"].get(q, 0)} for q in qkeys],
            "related": related,  # keys; names resolved after
        })

    by_key = {t["key"]: t for t in out}
    for t in out:
        t["related"] = [
            {"name": by_key[r["key"]]["name"], "slug": by_key[r["key"]]["slug"],
             "color": by_key[r["key"]]["color"], "shared": r["shared"]}
            for r in t["related"] if r["key"] in by_key
        ]
    out.sort(key=lambda t: (-t["edition_count"], t["name"].lower()))
    return out, qkeys


# ============================================================
# CHARTS
# ============================================================

def sparkline(timeline, color="accent", w=120, h=30):
    vals = [pt["count"] for pt in timeline]
    if not vals or max(vals) == 0:
        return ""
    n, mx, pad = len(vals), max(vals), 2
    iw, ih = w - pad * 2, h - pad * 2
    fx = lambda i: pad + (iw * i / (n - 1) if n > 1 else iw / 2)
    fy = lambda v: pad + ih - (ih * v / mx)
    pts = " ".join(f"{fx(i):.1f},{fy(v):.1f}" for i, v in enumerate(vals))
    c = COLOR_VAR.get(color, "var(--accent)")
    area = ""
    if n > 1:
        area = (f'<polygon points="{pad},{pad+ih:.1f} {pts} {pad+iw:.1f},{pad+ih:.1f}" '
                f'fill="{c}" opacity="0.10"/>')
    pi = vals.index(mx)
    dot = f'<circle cx="{fx(pi):.1f}" cy="{fy(mx):.1f}" r="2.4" fill="{c}"/>'
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'{area}<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dot}</svg>')


def bar_timeline(timeline, color="accent", h=130):
    vals = [pt["count"] for pt in timeline]
    if not vals or max(vals) == 0:
        return ""
    mx = max(vals)
    c = COLOR_VAR.get(color, "var(--accent)")
    n = len(timeline)
    bw = 100 / n
    bars = ""
    for pt in timeline:
        bh = (pt["count"] / mx) * 100 if mx else 0
        label = pt["period"].replace("-Q", "·Q")
        bars += (f'<div class="bt-col" style="width:{bw:.3f}%" title="{label}: {pt["count"]}">'
                 f'<div class="bt-bar" style="height:{bh:.1f}%;background:{c}"></div></div>')
    return f'<div class="bar-timeline" style="--bt-h:{h}px">{bars}</div>'


# ============================================================
# RENDER
# ============================================================

def _ed_link(ed, label):
    """Link an edition to its post page if it exists in the static site (corpus)."""
    if ed.get("source") == "corpus" and ed.get("slug"):
        return f'<a href="../posts/{esc(ed["slug"])}.html">{esc(label)}</a>'
    return f'<span>{esc(label)}</span>'


def _clamp(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return (s[:n].rsplit(" ", 1)[0] + "…") if len(s) > n else s


def cat_file(c):
    return f"cat-{slugify(c)}.html"


CORE_MIN = 3
TOP_N = 20


def render_index(terms, qkeys, gs, ctx):
    by_cat = defaultdict(list)
    for t in terms:
        by_cat[t["category"]].append(t)
    for c in by_cat:
        by_cat[c].sort(key=lambda t: (-t["edition_count"], t["name"].lower()))
    core = [t for t in terms if t["edition_count"] >= CORE_MIN]
    total_entries = sum(t["edition_count"] for t in terms)
    span = f"{qkeys[0].replace('-Q', ' Q')} – {qkeys[-1].replace('-Q', ' Q')}" if qkeys else ""

    chips = "".join(
        f'<a class="lex-chip" href="#cat-{slugify(c)}">{esc(c)} <span>{len(by_cat[c])}</span></a>'
        for c in src.CATEGORY_ORDER if by_cat.get(c))

    core_cards = ""
    for t in core[:48]:
        core_cards += f'''
    <a class="lex-cc" href="{t['slug']}.html">
      <div class="lex-cc-term">{esc(t['name'])}</div>
      <p class="lex-cc-def">{esc(_clamp(t['definition'], 140))}</p>
      <div class="lex-cc-spark">{sparkline(t['timeline'], t.get('color', 'accent'), w=130, h=30)}</div>
    </a>'''

    sections = ""
    for c in src.CATEGORY_ORDER:
        items = by_cat.get(c)
        if not items:
            continue
        shown = items[:TOP_N]
        lines = ""
        for t in shown:
            badge = f'<span class="lex-badge">{t["edition_count"]}×</span>' if t["edition_count"] > 1 else ""
            lines += f'''
      <a class="lex-line" href="{t['slug']}.html">
        <span class="lex-line-term">{esc(t['name'])}{badge}</span>
        <span class="lex-line-def">{esc(_clamp(t['definition'], 150))}</span>
      </a>'''
        more = (f'<a class="lex-seeall" href="{cat_file(c)}">See all {len(items)} {esc(c)} terms &rarr;</a>'
                if len(items) > len(shown) else "")
        sections += f'''
  <section class="block lex-catsec" id="cat-{slugify(c)}">
    <div class="rule-head"><h2 class="rule-label">{esc(c)}</h2><span class="rule-meta">Top {len(shown)} of {len(items)}</span></div>
    <div class="lex-lines">{lines}
    </div>
    {more}
  </section>'''

    all_data = json.dumps([[t["name"], t["slug"]] for t in terms], ensure_ascii=False)
    body = f'''
<header class="lex-hero">
  <div class="kicker kicker-accent">§ The Lexicon</div>
  <h1 class="lex-h1">The Lexicon</h1>
  <p class="lex-lede">The working vocabulary of the future of now — {len(terms):,} terms, defined by hand in <em>The Less You Know</em> across {ctx['edition_count']} editions. Every definition is the newsletter's own; recurring terms trace how the language of the field accumulated, week over week.</p>
  <div class="lex-metaline">{total_entries:,} definitions · {len(core)} recurring terms · {span} · 100% authentic humanly chosen</div>
  <input id="lexSearch" class="lex-search" type="search" autocomplete="off" placeholder="Search all {len(terms):,} terms…" aria-label="Search the Lexicon">
  <div class="lex-chips">{chips}</div>
</header>
<div id="lexResults" class="lex-results" hidden></div>
<div id="lexBrowse">
<main class="wrap">
  <section class="block lex-core-sec">
    <div class="rule-head"><h2 class="rule-label">Core Vocabulary</h2><span class="rule-meta">Recurring in 3+ editions</span></div>
    <div class="lex-core-grid">{core_cards}
    </div>
  </section>
{sections}
</main>
<div class="lex-soon"><div class="lex-soon-inner">
  <h3>Coming to the Lab</h3>
  <p>The Lexicon is the data layer. Next on the bench, all powered by it: <strong>the Constellation</strong> (browse terms as a map of what's glossed together), <strong>Ask the Archive</strong> (question three years of writing), and <strong>the Zeitgeist Tracker</strong> (what mattered when, across {len(qkeys)} quarters).</p>
</div></div>
</div>
<script>window.LEX_BASE="";window.LEX_ALL={all_data};</script>
{theme.SEARCH_JS}
'''
    return theme.page("The Lexicon — Token Wisdom", body, prefix="../", lex=True, active="lexicon")


def render_category(c, items, gs, ctx):
    items = sorted(items, key=lambda t: (-t["edition_count"], t["name"].lower()))
    lines = ""
    for t in items:
        badge = f'<span class="lex-badge">{t["edition_count"]}×</span>' if t["edition_count"] > 1 else ""
        lines += f'''
      <a class="lex-line" href="{t['slug']}.html">
        <span class="lex-line-term">{esc(t['name'])}{badge}</span>
        <span class="lex-line-def">{esc(_clamp(t['definition'], 150))}</span>
      </a>'''
    body = f'''
<header class="lex-hero">
  <a class="lex-back" href="index.html">&larr; The Lexicon</a>
  <div class="kicker kicker-accent">§ Lexicon · Category</div>
  <h1 class="lex-h1">{esc(c)}</h1>
  <div class="lex-metaline">{len(items)} terms · sorted by how often they're glossed</div>
</header>
<main class="wrap"><section class="block"><div class="lex-lines">{lines}
</div></section></main>
'''
    return theme.page(f"{c} — The Lexicon", body, prefix="../", lex=True, active="lexicon")


def render_term(t, gs, ctx):
    color = t["color"]
    defn = re.sub(r"\s+", " ", t["definition"]).strip()
    first, latest = t["first"], t["latest"]

    def ed_label(ed):
        en = ed.get("edition")
        return f"{en}th Edition" if en else gs.fmt_date_short(ed["date"])

    src_line = (f'<div class="term-def-src">— defined in '
                f'{_ed_link(latest, ed_label(latest))}, {gs.fmt_date_short(latest["date"])}</div>')

    chart = bar_timeline(t["timeline"], color, h=130) if t["edition_count"] > 1 else ""
    arc = (f'''
  <section class="term-section"><h3 class="term-h3">The arc</h3>
    <p class="term-arc-note">Glossed in {t['edition_count']} editions — when this term was part of the working vocabulary. First defined in {_ed_link(first, ed_label(first))}.</p>
    {chart}</section>''' if chart else "")

    hist = ""
    if len(t["definition_history"]) > 1:
        rows = ""
        for d in t["definition_history"][:-1]:
            lbl = f"{d['edition']}th" if d.get("edition") else gs.fmt_date_short(d["date"])
            rows += f'<li><span class="dh-ed">{esc(lbl)}</span> {esc(d["text"])}</li>'
        hist = (f'<section class="term-section"><h3 class="term-h3">How the definition evolved '
                f'<span class="term-h3-count">({len(t["definition_history"])} versions)</span></h3>'
                f'<ul class="def-history">{rows}</ul></section>')

    ed_rows = ""
    for ed in sorted(t["editions"], key=lambda d: d["date"], reverse=True):
        wk = ('W%02d' % ed['week']) if ed.get('week') else ''
        ed_rows += (f'<div class="term-post"><span class="tp-title">{_ed_link(ed, ed_label(ed))}</span>'
                    f'<span class="tp-meta">{wk} · {gs.fmt_date_short(ed["date"])}</span></div>')

    related = ""
    if t["related"]:
        chips = "".join(
            f'<a class="lex-chip" href="{r["slug"]}.html">{esc(r["name"])} <span>{r["shared"]}</span></a>'
            for r in t["related"])
        related = f'<div class="term-side-block"><h4>Travels with</h4><div class="lex-chips">{chips}</div></div>'

    body = f'''
<div class="term-wrap">
  <a class="term-back" href="index.html">&larr; The Lexicon</a>
  <div class="term-eyebrow lex-text-{color}">§ {esc(t['category'])}</div>
  <h1 class="term-title">{esc(t['name'])}</h1>
  <p class="term-def">{esc(defn)}</p>
  {src_line}
  <div class="term-stats">
    <div class="term-stat"><span class="ts-num">{t['edition_count']}</span><span class="ts-lbl">editions defined</span></div>
    <div class="term-stat"><span class="ts-num">{gs.fmt_date(first['date'], '%b %Y')}</span><span class="ts-lbl">first defined</span></div>
    <div class="term-stat"><span class="ts-num">{gs.fmt_date(latest['date'], '%b %Y')}</span><span class="ts-lbl">most recent</span></div>
    <div class="term-stat"><span class="ts-num">{esc(t['category'])}</span><span class="ts-lbl">category</span></div>
  </div>
{arc}
{hist}
  <div class="term-body">
    <section class="term-section"><h3 class="term-h3">Defined in <span class="term-h3-count">({t['edition_count']})</span></h3>
      <div class="term-posts">{ed_rows}</div></section>
    <aside class="term-side">{related}
      <div class="term-side-block"><a class="term-back" href="index.html">← The full Lexicon</a></div>
    </aside>
  </div>
</div>
'''
    return theme.page(f"{t['name']} — The Lexicon", body, prefix="../", lex=True, active="lexicon")


def build(posts, ctx, gs):
    lex_dir = DOCS_DIR / "lexicon"
    lex_dir.mkdir(parents=True, exist_ok=True)

    pdfs = ctx.get("pdf_paths")
    if pdfs is None:
        corpus_eds = {e["edition"] for e in src.from_corpus(posts) if e["edition"]}
        pdfs = src.discover_pdfs(PDF_DIR, exclude_editions=corpus_eds)
    print(f"Lexicon: harvesting 'The Less You Know' (corpus + {len(pdfs)} gap-filling PDFs)…")

    editions = src.harvest(posts, pdfs)
    terms, qkeys = aggregate(editions)
    ctx = dict(ctx, edition_count=len(editions))
    print(f"  {len(editions)} editions · {len(terms)} distinct terms · "
          f"{sum(t['edition_count'] >= 3 for t in terms)} recurring")

    with open(lex_dir / "index.html", "w") as f:
        f.write(render_index(terms, qkeys, gs, ctx))

    by_cat = defaultdict(list)
    for t in terms:
        by_cat[t["category"]].append(t)
    cat_n = 0
    for c in src.CATEGORY_ORDER:
        if by_cat.get(c):
            with open(lex_dir / cat_file(c), "w") as f:
                f.write(render_category(c, by_cat[c], gs, ctx))
            cat_n += 1

    for t in terms:
        with open(lex_dir / f"{t['slug']}.html", "w") as f:
            f.write(render_term(t, gs, ctx))

    export = [{k: v for k, v in t.items() if k != "key"} for t in terms]
    with open(DATA_DIR / "lexicon.json", "w") as f:
        json.dump({"generated": ctx.get("now", ""), "quarters": qkeys,
                   "edition_count": len(editions), "terms": export},
                  f, indent=2, ensure_ascii=False)
    print(f"  Wrote index + {cat_n} category pages + {len(terms)} term pages + data/lexicon.json")
    return terms


if __name__ == "__main__":
    import generate_site as gs
    posts, tags, authors, pages = gs.load_data()
    tag_to_posts = defaultdict(list)
    for post in posts:
        for tg in post.get("tags", []) or []:
            tag_to_posts[tg["slug"]].append(post)
    public_tags = [t for t in tags if not (t.get("name", "") or "").startswith("#")]
    top_tags = sorted(public_tags, key=lambda t: len(tag_to_posts.get(t["slug"], [])), reverse=True)
    years = [p["published_at"][:4] for p in posts if p.get("published_at")]
    ctx = {
        "posts_count": len(posts), "tags_count": len(public_tags),
        "years_span": f"{min(years)}–{max(years)}" if years else "",
        "top_tags": top_tags, "now": datetime.now().strftime("%Y-%m-%d"),
    }
    build(posts, ctx, gs)
    print("Done. (Run generate_site.py for the full site + nav.)")

"""
The Corpus Report — a Feltron Annual Report for Token Wisdom.

A quantified portrait of the corpus from 2023 onward in the structural grammar
of Nicholas Felton's Annual Reports — big hero numerals, small-caps label→value
rows, dotted-leader ranked lists, hatched overlapping area charts, italic-serif
subtitles — dressed in the Token Wisdom design system: warm paper, Libre Caslon
serif numerals, burnt-orange accent with teal and gold.

Scope: 2023–present. Earlier years (2013–2015, 2022) are handled separately.

Run standalone:  python3 metrics.py
Wired into the full build via generate_site.main().
"""

import json
import re
import statistics
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

BACKUP_DIR = Path(__file__).resolve().parent
DOCS_DIR = BACKUP_DIR / "docs"
DATA_DIR = BACKUP_DIR / "data"

START_YEAR = 2023  # report scope — pre-2023 lives in a separate supplement

WORD_RX = re.compile(r"[A-Za-z']+")
SENT_RX = re.compile(r"(?<=[.!?])\s+")

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


# ============================================================
# MEASUREMENT
# ============================================================

def _words(text):
    return WORD_RX.findall(text or "")


def _sentences(text):
    return [s for s in SENT_RX.split(text or "") if s.strip()]


def _post_text(p):
    return p.get("plaintext") or p.get("html") or ""


def compute(posts, gs):
    pub = [p for p in posts
           if p.get("published_at") and p["published_at"][:4].isdigit()
           and int(p["published_at"][:4]) >= START_YEAR]
    pub.sort(key=lambda p: p["published_at"])

    nl = [p for p in pub if gs.is_newsletter(p)]
    essays = [p for p in pub if not gs.is_newsletter(p)]

    wc = {id(p): len(_words(_post_text(p))) for p in pub}
    total_words = sum(wc.values())
    total_rt = sum(p.get("reading_time") or 0 for p in pub)
    words_nl = sum(wc[id(p)] for p in nl)
    words_essay = sum(wc[id(p)] for p in essays)

    counts = sorted(wc.values())
    longest = max(pub, key=lambda p: wc[id(p)])
    median_wc = int(statistics.median(counts))
    mean_wc = total_words // len(pub)

    vocab = set()
    for p in pub:
        vocab.update(w.lower() for w in _words(_post_text(p)))

    # ---- monthly series (essays vs newsletters) for the area chart ----
    month_keys = []
    y0 = START_YEAR
    last = pub[-1]["published_at"][:7]
    y, m = START_YEAR, 1
    while f"{y:04d}-{m:02d}" <= last:
        month_keys.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    mo_nl = {k: 0 for k in month_keys}
    mo_es = {k: 0 for k in month_keys}
    for p in pub:
        k = p["published_at"][:7]
        if k in mo_nl:
            (mo_nl if gs.is_newsletter(p) else mo_es)[k] += wc[id(p)]

    # ---- by year ----
    by_year = defaultdict(list)
    for p in pub:
        by_year[p["published_at"][:4]].append(p)
    year_rows = []
    for yk in sorted(by_year):
        ps = by_year[yk]
        txt = " ".join(_post_text(p) for p in ps)
        w, s = _words(txt), _sentences(txt)
        if not w:
            continue
        ttrs = []
        for i in range(0, len(w), 1000):
            chunk = w[i:i + 1000]
            if len(chunk) >= 250:
                ttrs.append(len(set(c.lower() for c in chunk)) / len(chunk))
        year_rows.append({
            "year": yk, "posts": len(ps), "words": len(w),
            "rt": sum(p.get("reading_time") or 0 for p in ps),
            "asl": len(w) / max(1, len(s)),
            "awl": sum(len(x) for x in w) / len(w),
            "ttr": (statistics.mean(ttrs) * 100) if ttrs else None,
        })

    # ---- read-time distribution ----
    rt_buckets = Counter()
    for p in pub:
        rt = p.get("reading_time") or 0
        b = ("1–3" if rt <= 3 else "4–6" if rt <= 6 else
             "7–10" if rt <= 10 else "11–15" if rt <= 15 else "16+")
        rt_buckets[b] += 1

    # ---- lexicon (filter to terms seen from START_YEAR on) ----
    lex = json.load(open(DATA_DIR / "lexicon.json"))
    terms = [t for t in lex["terms"]
             if (t.get("latest") or {}).get("date", "9999")[:4] >= str(START_YEAR)]
    cats = Counter(t["category"] for t in terms)
    recurring = [t for t in terms if t.get("edition_count", 0) >= 3]
    multi = [t for t in terms if t.get("edition_count", 0) > 1]
    top_terms = sorted(terms, key=lambda t: t.get("edition_count", 0), reverse=True)[:12]

    coin_q = Counter()
    for t in terms:
        dt = (t.get("first") or {}).get("date", "")
        if len(dt) >= 7 and dt[:4] >= str(START_YEAR):
            coin_q[f"{dt[:4]} Q{(int(dt[5:7]) - 1) // 3 + 1}"] += 1

    ed_terms = defaultdict(set)
    for t in terms:
        for e in t.get("editions", []):
            if e.get("edition"):
                ed_terms[e["edition"]].add(t["name"])
    ed_sizes = [len(v) for v in ed_terms.values()]

    links = json.load(open(DATA_DIR / "links.json"))

    return {
        "now": datetime.now().strftime("%B %-d, %Y"),
        "span": f"{pub[0]['published_at'][:4]}–{pub[-1]['published_at'][:4]}",
        "n_years": len({p["published_at"][:4] for p in pub}),
        "n_posts": len(pub), "n_nl": len(nl), "n_essay": len(essays),
        "total_words": total_words, "total_rt": total_rt,
        "max_rt": max((p.get("reading_time") or 0) for p in pub),
        "words_nl": words_nl, "words_essay": words_essay,
        "longest": longest, "longest_wc": wc[id(longest)],
        "median_wc": median_wc, "mean_wc": mean_wc, "vocab": len(vocab),
        "month_keys": month_keys, "mo_nl": mo_nl, "mo_es": mo_es,
        "year_rows": year_rows, "rt_buckets": rt_buckets,
        "n_terms": len(terms), "ed_count": len(ed_terms),
        "cats": cats, "recurring": len(recurring), "multi": len(multi),
        "top_terms": top_terms, "coin_q": coin_q,
        "ed_terms_avg": statistics.mean(ed_sizes) if ed_sizes else 0,
        "ed_terms_max": max(ed_sizes) if ed_sizes else 0,
        "n_links": len(links.get("all_links", [])),
        "link_weeks": links.get("total_weeks", 0),
        "gs": gs,
    }


# ============================================================
# FORMAT HELPERS
# ============================================================

def _n(x):
    return f"{int(round(x)):,}"


_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def spell(n):
    """Spell an int 0–99 in Title Case: Forty-Eight, Nine, Twelve."""
    n = int(n)
    if n < 20:
        w = _ONES[n]
    elif n < 100:
        w = _TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else "")
    else:
        return _n(n)
    return w.title()


# ============================================================
# SVG CHARTS
# ============================================================

def _smooth_path(pts):
    """Catmull-Rom → cubic bezier for a soft Feltron ridge."""
    if len(pts) < 2:
        return ""
    d = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d)


def area_chart(d, w=720, h=300):
    """Two overlapping hatched areas — newsletters vs essays words per month."""
    keys = d["month_keys"]
    nl = [d["mo_nl"][k] for k in keys]
    es = [d["mo_es"][k] for k in keys]
    vmax = max(max(nl), max(es)) or 1
    pad_l, pad_r, pad_t, pad_b = 2, 2, 26, 30
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    n = len(keys)
    base = pad_t + ph

    def pts(series):
        return [(pad_l + (i / (n - 1)) * pw, pad_t + ph - (v / vmax) * ph)
                for i, v in enumerate(series)]

    def area(series, fill, stroke):
        p = pts(series)
        line = _smooth_path(p)
        d_attr = f"{line} L{p[-1][0]:.1f} {base:.1f} L{p[0][0]:.1f} {base:.1f} Z"
        return (f'<path d="{d_attr}" fill="{fill}" stroke="none"/>'
                f'<path d="{line}" fill="none" stroke="{stroke}" stroke-width="1.6"/>')

    # year gridlines + labels
    grid = []
    seen = set()
    for i, k in enumerate(keys):
        yr = k[:4]
        x = pad_l + (i / (n - 1)) * pw
        if k[5:7] == "01" or i == 0:
            if yr not in seen:
                seen.add(yr)
                grid.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{base:.1f}" class="fx-grid"/>')
                grid.append(f'<text x="{x + 4:.1f}" y="{h - 9:.1f}" class="fx-axis">{yr}</text>')

    # peak callout (essays usually peak highest)
    peak_i = max(range(n), key=lambda i: es[i])
    px = pad_l + (peak_i / (n - 1)) * pw
    py = pad_t + ph - (es[peak_i] / vmax) * ph

    return f'''<svg class="fx-svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img">
<defs>
  <pattern id="hatchTeal" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
    <line x1="0" y1="0" x2="0" y2="6" stroke="var(--teal)" stroke-width="0.9" stroke-opacity="0.55"/></pattern>
  <pattern id="hatchAccent" width="6" height="6" patternTransform="rotate(-45)" patternUnits="userSpaceOnUse">
    <line x1="0" y1="0" x2="0" y2="6" stroke="var(--accent)" stroke-width="0.9" stroke-opacity="0.7"/></pattern>
</defs>
{''.join(grid)}
<line x1="{pad_l}" y1="{base:.1f}" x2="{w - pad_r}" y2="{base:.1f}" class="fx-base"/>
{area(es, 'url(#hatchTeal)', 'var(--teal)')}
{area(nl, 'url(#hatchAccent)', 'var(--accent-deep)')}
<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="var(--paper)" stroke="var(--ink)" stroke-width="1.4"/>
<line x1="{px:.1f}" y1="{py - 4:.1f}" x2="{px:.1f}" y2="{pad_t + 4:.1f}" class="fx-callout"/>
<text x="{px + 5:.1f}" y="{pad_t + 12:.1f}" class="fx-note">PEAK · {keys[peak_i][:4]} {MONTHS[int(keys[peak_i][5:7]) - 1]}</text>
</svg>'''


def ranked(data, w=520, row_h=30, color="var(--teal)", value_fmt=_n):
    """Feltron 'passport stamp' list: caps label · bar · dotted leader · value."""
    if not data:
        return ""
    vmax = max(v for _, v in data) or 1
    label_w, val_w = 200, 46
    bar_max = w - label_w - val_w - 14
    h = row_h * len(data)
    rows = []
    for i, (lab, val) in enumerate(data):
        y = i * row_h
        cy = y + row_h / 2
        bw = max(2, (val / vmax) * bar_max)
        rows.append(
            f'<text x="0" y="{cy:.1f}" class="fx-rank-lbl" dominant-baseline="central">{lab}</text>'
            f'<rect x="{label_w}" y="{cy - 2.5:.1f}" width="{bw:.1f}" height="5" fill="{color}"/>'
            f'<line x1="{label_w + bw + 4:.1f}" y1="{cy:.1f}" x2="{w - val_w:.1f}" y2="{cy:.1f}" class="fx-leader"/>'
            f'<text x="{w:.1f}" y="{cy:.1f}" class="fx-rank-val" text-anchor="end" dominant-baseline="central">{value_fmt(val)}</text>'
        )
        if i:
            rows.append(f'<line x1="0" y1="{y:.1f}" x2="{w}" y2="{y:.1f}" class="fx-rowrule"/>')
    return (f'<svg class="fx-svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img">'
            + "".join(rows) + "</svg>")


def line_mini(rows, key, w=300, h=150, color="var(--teal)", fmt="{:.0f}"):
    pts = [(r["year"], r[key]) for r in rows if r.get(key) is not None]
    if len(pts) < 2:
        return ""
    vals = [p[1] for p in pts]
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or 1
    pad_l, pad_r, pad_t, pad_b = 6, 6, 24, 26
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b
    n = len(pts)
    coords = [(pad_l + (i / (n - 1)) * pw, pad_t + ph - ((v - vmin) / span) * ph)
              for i, (_, v) in enumerate(pts)]
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    dots = []
    for i, ((yr, v), (x, yy)) in enumerate(zip(pts, coords)):
        dots.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="3.2" fill="{color}"/>')
        dots.append(f'<text x="{x:.1f}" y="{yy - 9:.1f}" class="fx-pt" text-anchor="middle">{fmt.format(v)}</text>')
        dots.append(f'<text x="{x:.1f}" y="{h - 8:.1f}" class="fx-axis" text-anchor="middle">{yr[2:]}</text>')
    return (f'<svg class="fx-svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img">'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round"/>'
            + "".join(dots) + "</svg>")


def columns(data, w=520, h=200, color="var(--teal)", value_fmt=_n):
    if not data:
        return ""
    vmax = max(v for _, v in data) or 1
    pad_t, pad_b = 18, 30
    pw, ph = w - 8, h - pad_t - pad_b
    n = len(data)
    slot = pw / n
    bw = min(slot * 0.5, 40)
    base = pad_t + ph
    out = [f'<line x1="4" y1="{base:.1f}" x2="{w - 4:.1f}" y2="{base:.1f}" class="fx-base"/>']
    for i, (lab, val) in enumerate(data):
        bh = (val / vmax) * ph
        x = 4 + i * slot + (slot - bw) / 2
        y = base - bh
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}"/>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 6:.1f}" class="fx-pt" text-anchor="middle">{value_fmt(val)}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 9:.1f}" class="fx-axis" text-anchor="middle">{lab}</text>')
    return (f'<svg class="fx-svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img">'
            + "".join(out) + "</svg>")


# ============================================================
# HTML BUILDERS
# ============================================================

def cell(label, value, note="", tone="ink", size="big"):
    """Feltron label→value cell: tiny caps label, giant numeral, tiny note."""
    note_h = f'<div class="fc-note">{note}</div>' if note else ""
    return (f'<div class="fc fc-{size}">'
            f'<div class="fc-label">{label}</div>'
            f'<div class="fc-value t-{tone}">{value}</div>{note_h}</div>')


def spread(kicker, title, subtitle, body):
    return f'''
<section class="fs">
  <div class="fs-head">
    <div class="fs-kicker">{kicker}</div>
    <h2 class="fs-title">{title}</h2>
    <p class="fs-sub">{subtitle}</p>
  </div>
  {body}
</section>'''


def chart(label, svg, foot=""):
    foot_h = f'<div class="fx-foot">{foot}</div>' if foot else ""
    return f'<figure class="fx"><figcaption class="fx-label">{label}</figcaption>{svg}{foot_h}</figure>'


# ============================================================
# RENDER
# ============================================================

def render(d):
    gs = d["gs"]
    hrs = d["total_rt"] / 60
    pct_nl = round(d["words_nl"] / d["total_words"] * 100)
    longest_t = gs.clean_title(d["longest"])

    # ---- masthead ----
    head = f'''
<header class="fm">
  <div class="fm-top">
    <div class="fm-meta">{d['span']} · The Quantified Corpus</div>
    <div class="fm-meta fm-meta-r">Compiled {d['now']}</div>
  </div>
  <h1 class="fm-title">The Corpus Report</h1>
  <p class="fm-sub">A record of the writing — every word, edition, and idea
     counted, from {d['span'].split('–')[0]} to today.</p>
  <div class="fm-rule fm-rule-b"></div>
</header>

<div class="fg fg-hero">
  {cell('WORDS WRITTEN', _n(d['total_words']), f"across {d['n_posts']} entries", 'ink', 'xl')}
  {cell('HOURS OF READING', f"{hrs:.0f}", f"{_n(d['total_rt'])} minutes, cover to cover", 'accent')}
  {cell('ENTRIES PUBLISHED', _n(d['n_posts']), f"{d['n_nl']} editions · {d['n_essay']} essays", 'ink')}
  {cell('TERMS DEFINED', _n(d['n_terms']), 'in The Lexicon', 'teal')}
  {cell('DISTINCT WORDS', _n(d['vocab']), 'the working vocabulary', 'ink')}
  {cell('LINKS CURATED', _n(d['n_links']), f"over {d['link_weeks']} weeks", 'accent')}
  {cell('YEARS ON RECORD', spell(d['n_years']), d['span'], 'gold')}
  {cell('AVERAGE ENTRY', _n(d['mean_wc']), 'words', 'ink')}
  {cell('LONGEST ENTRY', _n(d['longest_wc']), 'words, single piece', 'teal')}
</div>'''

    # ---- §01 Volume ----
    stamp_split = ranked([("NEWSLETTERS", d["words_nl"]), ("ESSAYS", d["words_essay"])],
                         w=520, row_h=40, color="var(--ink)",
                         value_fmt=lambda v: _n(v))
    vol = spread(
        "01 · Volume", "Word Count",
        "A record of consumption — what the corpus is made of, and when it arrived.",
        f'''
  <div class="fg fg-3">
    {cell('AVERAGE ENTRY', _n(d['mean_wc']), 'words', 'ink', 'big')}
    {cell('MEDIAN ENTRY', _n(d['median_wc']), 'words', 'ink', 'big')}
    {cell('LONGEST', _n(d['longest_wc']), gs.esc(longest_t[:40]), 'teal', 'big')}
  </div>
  <div class="fsplit">
    <div class="fc-label">NEWSLETTERS vs ESSAYS · words</div>
    {stamp_split}
    <div class="fx-foot">Newsletters {pct_nl}% · essays {100 - pct_nl}% of the {_n(d['total_words'])}-word corpus.</div>
  </div>
  {chart("WORDS PUBLISHED PER MONTH — NEWSLETTERS (ORANGE) vs ESSAYS (TEAL)",
         area_chart(d),
         "Each band is words shipped that month; the curves track the publication's two voices.")}''')

    # ---- §02 Read Time ----
    rt_order = ["1–3", "4–6", "7–10", "11–15", "16+"]
    rt_data = [(b, d["rt_buckets"].get(b, 0)) for b in rt_order]
    year_rt = [(r["year"][2:], r["rt"]) for r in d["year_rows"]]
    read = spread(
        "02 · Attention", "Read Time",
        f"At a steady pace the whole corpus is {hrs:.0f} hours — a work-week of reading. "
        "Most single entries ask for far less.",
        f'''
  <div class="fg fg-3">
    {cell('TOTAL', f"{hrs:.0f}", 'hours, end to end', 'teal', 'big')}
    {cell('AVERAGE ENTRY', f"{d['total_rt'] / d['n_posts']:.0f}", 'minutes', 'ink', 'big')}
    {cell('LONGEST READ', _n(d['max_rt']), 'minutes', 'gold', 'big')}
  </div>
  <div class="fg fg-2">
    {chart("ENTRIES BY READING TIME · minutes", columns(rt_data, w=520, color="var(--teal)"))}
    {chart("READING MINUTES ADDED PER YEAR", columns(year_rt, w=520, color="var(--gold)"))}
  </div>''')

    # ---- §03 Concentration / Lexicon ----
    cat_order = sorted(d["cats"].items(), key=lambda kv: kv[1], reverse=True)
    cat_rank = ranked([(c.upper(), n) for c, n in cat_order], w=520, color="var(--gold)")
    coin_data = [(k.split()[0][2:] + k.split()[1], d["coin_q"][k]) for k in sorted(d["coin_q"])]
    conc = spread(
        "03 · Density", "The Lexicon",
        "The corpus distilled. Every edition mints vocabulary; the rate of coinage "
        "marks when the field — and the writing — accelerated.",
        f'''
  <div class="fg fg-4">
    {cell('TERMS DEFINED', _n(d['n_terms']), f"from {d['ed_count']} editions", 'gold', 'big')}
    {cell('PER EDITION', f"{d['ed_terms_avg']:.0f}", 'on average', 'ink', 'big')}
    {cell('DENSEST EDITION', _n(d['ed_terms_max']), 'defined terms', 'ink', 'big')}
    {cell('CATEGORIES', spell(len(cat_order)), 'fields of knowledge', 'teal', 'big')}
  </div>
  <div class="fg fg-2 fg-top">
    <div class="fsplit">
      <div class="fc-label">THE LEXICON BY CATEGORY</div>
      {cat_rank}
    </div>
    {chart("NEW TERMS FIRST DEFINED, BY QUARTER", columns(coin_data, w=520, color="var(--gold)"),
           "Each column counts terms making their first appearance — the corpus's rate of new ideas.")}
  </div>''')

    # ---- §04 Interconnectedness ----
    top_rank = ranked([(gs.esc(t["name"]).upper(), t.get("edition_count", 0)) for t in d["top_terms"]],
                      w=520, color="var(--teal)")
    pct_multi = round(d["multi"] / d["n_terms"] * 100)
    inter = spread(
        "04 · The Graph", "Interconnectedness",
        "Ideas don't live in one edition. Terms recur, binding issues into a web — "
        "and a curated trail of outside reading anchors it to the wider world.",
        f'''
  <div class="fg fg-4">
    {cell('RECURRING TERMS', _n(d['multi']), f"in 2+ editions ({pct_multi}%)", 'teal', 'big')}
    {cell('LOAD-BEARING', _n(d['recurring']), 'terms in 3+ editions', 'ink', 'big')}
    {cell('OUTBOUND LINKS', _n(d['n_links']), f"over {d['link_weeks']} weeks", 'gold', 'big')}
    {cell('PER WEEK', f"{d['n_links'] / max(1, d['link_weeks']):.0f}", 'links curated', 'ink', 'big')}
  </div>
  <div class="fsplit">
    <div class="fc-label">MOST-CONNECTED TERMS · appearances across editions</div>
    {top_rank}
    <div class="fx-foot">The concepts that thread through the most issues are the corpus's load-bearing ideas.</div>
  </div>''')

    # ---- §05 Style ----
    sr = d["year_rows"]
    first, last = sr[0], sr[-1]
    peak_ttr = max(r["ttr"] for r in sr if r["ttr"] is not None)
    style = spread(
        "05 · Evolution", "Progress in Style",
        "Measured year over year within this window, the prose tightened even as the "
        "ideas thickened — leaner sentences carrying a denser, richer vocabulary.",
        f'''
  <div class="fg fg-c3">
    {chart("AVG SENTENCE LENGTH · words", line_mini(sr, 'asl', w=320, color="var(--ink)", fmt="{:.0f}"))}
    {chart("AVG WORD LENGTH · letters", line_mini(sr, 'awl', w=320, color="var(--teal)", fmt="{:.1f}"))}
    {chart("VOCABULARY RICHNESS · TTR %", line_mini(sr, 'ttr', w=320, color="var(--gold-deep)", fmt="{:.0f}"))}
  </div>
  <p class="fs-caption">Across {first['year']}–{last['year']} the average sentence tightened
     from {first['asl']:.0f} to {last['asl']:.0f} words, while vocabulary richness climbed
     from {first['ttr']:.0f}% toward a high of {peak_ttr:.0f}% — leaner prose carrying denser
     ideas. Richness is measured on length-normalised 1,000-word windows, comparable across
     years of very different size.</p>''')

    method = f'''
<section class="fmeth">
  <div class="fs-kicker">Methodology &amp; Scope</div>
  <p>This report covers {d['n_posts']} entries published from {d['span'].split('–')[0]} onward;
     earlier writing (2013–2022) is documented in a separate supplement. Word counts tokenise
     the plain-text body of each post; reading time is Ghost's own estimate. Lexicon figures
     cover {_n(d['n_terms'])} terms harvested from every edition's <em>“The Less You Know”</em>
     across {d['ed_count']} editions. The link graph counts {_n(d['n_links'])} curated outbound
     references logged over {d['link_weeks']} weeks. Set in the Token Wisdom house style —
     Libre Caslon numerals on warm paper, with the burnt-orange accent. Compiled {d['now']}.</p>
</section>'''

    return CSS + '<div class="fwrap">' + head + vol + read + conc + inter + style + method + "</div>"


# ============================================================
# STYLES — Feltron grammar, Token Wisdom palette
# ============================================================

CSS = """
<style>
.fwrap {
  --ink:        #1a1814;   /* primary ink — warm charcoal          */
  --ink-muted:  #6b6760;   /* deks, labels                         */
  --ink-faint:  #a39e96;   /* notes, timestamps                    */
  --accent:     #c8521a;   /* Token Wisdom burnt orange — the soul */
  --accent-deep:#8a3610;
  --teal:       #1a6b5c;
  --gold:       #b8860b;
  --gold-deep:  #8a6309;
  --paper:      #faf8f4;   /* warm near-white                      */
  --paper-2:    #f4f1ea;
  --rule:       #e6e2d9;
  --fdisp: 'Libre Caslon Display', Georgia, serif;  /* the elegant numerals */
  --fsans: 'Archivo', -apple-system, sans-serif;
  --fmono: 'DM Mono', monospace;
  --fserif: 'Source Serif 4', Georgia, serif;

  background: var(--paper);
  color: var(--ink);
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 40px 6rem;
  font-family: var(--fsans);
}
.fwrap ::selection { background: var(--accent); color: var(--paper); }

/* tone helpers */
.fwrap .t-ink    { color: var(--ink); }
.fwrap .t-teal   { color: var(--teal); }
.fwrap .t-gold   { color: var(--gold); }
.fwrap .t-accent { color: var(--accent); }

/* ---------- masthead ---------- */
.fm { padding: 4rem 0 0; }
.fm-rule { height: 2px; background: var(--ink); }
.fm-rule-b { height: 2px; background: var(--ink); margin-top: 1.6rem; }
.fm-top { display: flex; justify-content: space-between; padding: .2rem 0 1.8rem; }
.fm-meta {
  font-family: var(--fmono); font-size: 10.5px; letter-spacing: .18em;
  text-transform: uppercase; color: var(--accent); font-weight: 300;
}
.fm-meta-r { color: var(--ink-faint); }
.fm-title {
  font-family: var(--fdisp); font-weight: 400; line-height: 1;
  font-size: clamp(2.8rem, 8.4vw, 5.8rem); letter-spacing: -.01em; color: var(--ink);
}
.fm-sub {
  font-family: var(--fserif); font-weight: 400;
  font-size: clamp(1.1rem, 2.4vw, 1.5rem); color: var(--ink-muted);
  max-width: 46ch; margin-top: 1.1rem; line-height: 1.45;
}

/* ---------- grids of cells ---------- */
.fg { display: grid; gap: 0; }
.fg-hero { grid-template-columns: repeat(3, 1fr); margin-top: 2.4rem;
           border-top: 1px solid var(--rule); }
.fg-2 { grid-template-columns: 1fr 1fr; gap: 2.6rem; }
.fg-c3 { grid-template-columns: repeat(3, 1fr); gap: 0 2.6rem; }
.fg-3 { grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--rule); }
.fg-4 { grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--rule); }
.fg-top { align-items: start; }

.fc {
  padding: 1.5rem 1.4rem 1.5rem 0;
  border-bottom: 1px solid var(--rule);
}
.fg-hero .fc {
  border-right: 1px solid var(--rule); padding-left: 1.4rem;
}
.fg-hero .fc:nth-child(3n) { border-right: none; }
.fc-label {
  font-family: var(--fmono); font-size: 10px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--ink-muted); font-weight: 300;
  margin-bottom: .6rem;
}
.fc-value {
  font-family: var(--fdisp); font-weight: 400; line-height: .95;
  letter-spacing: -.01em; font-variant-numeric: tabular-nums;
  font-size: clamp(2.3rem, 5vw, 3.4rem);
}
.fc-xl .fc-value { font-size: clamp(3rem, 8vw, 5rem); }
.fc-big .fc-value { font-size: clamp(2.1rem, 4.4vw, 3rem); }
.fc-note {
  font-family: var(--fmono); font-size: 10.5px; letter-spacing: .02em;
  color: var(--ink-faint); margin-top: .6rem; line-height: 1.45; font-weight: 300;
}

/* ---------- section spreads ---------- */
.fs { padding: 4.2rem 0 0; }
.fs-head { border-top: 2px solid var(--ink); padding-top: 1.1rem; margin-bottom: 1.4rem; }
.fs-kicker {
  font-family: var(--fmono); font-size: 11px; letter-spacing: .18em;
  text-transform: uppercase; color: var(--accent); font-weight: 400;
}
.fs-title {
  font-family: var(--fdisp); font-weight: 400;
  font-size: clamp(2rem, 5vw, 3.3rem); letter-spacing: -.01em;
  line-height: 1.02; color: var(--ink); margin-top: .25rem;
}
.fs-sub {
  font-family: var(--fserif); font-style: italic; font-size: 1.18rem;
  color: var(--ink-muted); max-width: 58ch; margin-top: .7rem; line-height: 1.45;
}
.fs-caption, .fmeth p {
  font-family: var(--fserif); font-size: 1rem; line-height: 1.6;
  color: var(--ink-muted); max-width: 70ch; margin-top: 1.6rem;
}
.fs-caption em, .fmeth em { font-style: italic; color: var(--ink); }

/* ---------- charts ---------- */
.fx, .fsplit { margin-top: 2.2rem; }
.fx-label, .fsplit > .fc-label {
  font-family: var(--fmono); font-size: 10px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--ink); font-weight: 400;
  padding-bottom: .7rem; border-bottom: 1px solid var(--rule); margin-bottom: 1.2rem;
}
.fx-foot {
  font-family: var(--fmono); font-size: 10.5px; letter-spacing: .02em;
  color: var(--ink-faint); margin-top: .9rem; line-height: 1.5; max-width: 70ch; font-weight: 300;
}
.fx-svg { width: 100%; height: auto; overflow: visible; display: block; }

/* svg text + strokes */
.fx-rank-lbl { font-family: var(--fmono); font-size: 11px; letter-spacing: .03em; fill: var(--ink); font-weight: 300; }
.fx-rank-val { font-family: var(--fdisp); font-weight: 400; font-size: 18px; fill: var(--ink); }
.fx-leader { stroke: var(--ink-faint); stroke-width: 1; stroke-dasharray: 1.5 3; }
.fx-rowrule { stroke: var(--rule); stroke-width: 1; }
.fx-base { stroke: var(--ink); stroke-width: 1; }
.fx-grid { stroke: var(--rule); stroke-width: 1; }
.fx-axis { font-family: var(--fmono); font-size: 10px; letter-spacing: .06em; fill: var(--ink-muted); font-weight: 300; }
.fx-pt { font-family: var(--fdisp); font-weight: 400; font-size: 15px; fill: var(--ink); }
.fx-callout { stroke: var(--ink); stroke-width: 1; stroke-dasharray: 1.5 2.5; }
.fx-note { font-family: var(--fmono); font-size: 9.5px; letter-spacing: .1em; fill: var(--ink); text-transform: uppercase; font-weight: 300; }

/* ---------- methodology ---------- */
.fmeth { margin-top: 4.5rem; border-top: 2px solid var(--ink); padding-top: 1.2rem; }

@media (max-width: 900px) {
  .fwrap { padding: 0 22px 4rem; }
  .fg-hero, .fg-3, .fg-4 { grid-template-columns: repeat(2, 1fr); }
  .fg-hero .fc:nth-child(3n) { border-right: 1px solid var(--rule); }
  .fg-hero .fc:nth-child(2n) { border-right: none; }
  .fg-2 { grid-template-columns: 1fr; gap: 1.6rem; }
}
@media (max-width: 540px) {
  .fg-hero, .fg-3, .fg-4 { grid-template-columns: 1fr; }
  .fg-hero .fc, .fg-hero .fc:nth-child(n) { border-right: none; }
}
</style>
"""


# ============================================================
# BUILD
# ============================================================

def build(posts, ctx, gs):
    d = compute(posts, gs)
    body = render(d)
    page = gs.page_shell("The Corpus Report", body, "style.css", from_dir="root")
    page += gs.colophon(ctx["posts_count"], ctx["tags_count"],
                        ctx["years_span"], ctx["top_tags"], from_dir="root")
    with open(DOCS_DIR / "metrics.html", "w") as f:
        f.write(page)
    print(f"  Wrote docs/metrics.html — {START_YEAR}+ scope · {_n(d['total_words'])} words, "
          f"{d['n_posts']} entries, {d['n_terms']} terms")


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
        "top_tags": top_tags,
    }
    build(posts, ctx, gs)
    print("Done. (Run generate_site.py for the full site + nav.)")

"""
The Corpus Report — a Feltron-style quantified portrait of Token Wisdom.

Renders docs/metrics.html from the corpus (all_posts.json), the Lexicon
(data/lexicon.json), and the curated link graph (data/links.json). The page
shares the site chrome (nav + colophon) via generate_site.page_shell, and
carries its own scoped <style> block for the report layout + inline SVG charts.

Run standalone with:  python3 metrics.py   (after generate_site has data)
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

WORD_RX = re.compile(r"[A-Za-z']+")
SENT_RX = re.compile(r"(?<=[.!?])\s+")


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
    """Crunch the corpus into the report's figures. Returns a dict."""
    pub = [p for p in posts if p.get("published_at")]
    pub.sort(key=lambda p: p["published_at"])

    nl = [p for p in pub if gs.is_newsletter(p)]
    essays = [p for p in pub if not gs.is_newsletter(p)]

    # ---- volume ----
    wc = {p["slug"]: len(_words(_post_text(p))) for p in pub}
    total_words = sum(wc.values())
    total_rt = sum(p.get("reading_time") or 0 for p in pub)
    words_nl = sum(wc[p["slug"]] for p in nl)
    words_essay = sum(wc[p["slug"]] for p in essays)

    counts = sorted(wc.values())
    longest = max(pub, key=lambda p: wc[p["slug"]])
    median_wc = int(statistics.median(counts))
    mean_wc = total_words // len(pub)

    # corpus vocabulary
    vocab = set()
    for p in pub:
        vocab.update(w.lower() for w in _words(_post_text(p)))

    # ---- by year ----
    by_year = defaultdict(list)
    for p in pub:
        by_year[p["published_at"][:4]].append(p)

    years = sorted(by_year)
    year_rows = []
    for y in years:
        ps = by_year[y]
        txt = " ".join(_post_text(p) for p in ps)
        w = _words(txt)
        s = _sentences(txt)
        if not w:
            continue
        # length-normalised vocabulary richness: mean TTR over 1k-word windows
        ttrs = []
        for i in range(0, len(w), 1000):
            chunk = w[i:i + 1000]
            if len(chunk) >= 250:
                ttrs.append(len(set(c.lower() for c in chunk)) / len(chunk))
        year_rows.append({
            "year": y,
            "posts": len(ps),
            "words": len(w),
            "rt": sum(p.get("reading_time") or 0 for p in ps),
            "asl": len(w) / max(1, len(s)),                 # avg sentence length
            "awl": sum(len(x) for x in w) / len(w),         # avg word length
            "ttr": (statistics.mean(ttrs) * 100) if ttrs else None,
            "uniq": len(set(x.lower() for x in w)),
        })

    # ---- read-time distribution ----
    rt_buckets = Counter()
    for p in pub:
        rt = p.get("reading_time") or 0
        if rt <= 3:
            rt_buckets["≤3"] += 1
        elif rt <= 6:
            rt_buckets["4–6"] += 1
        elif rt <= 10:
            rt_buckets["7–10"] += 1
        elif rt <= 15:
            rt_buckets["11–15"] += 1
        else:
            rt_buckets["16+"] += 1

    # ---- lexicon ----
    lex = json.load(open(DATA_DIR / "lexicon.json"))
    terms = lex["terms"]
    ed_count = lex.get("edition_count", 0)
    cats = Counter(t["category"] for t in terms)
    cat_color = {}
    for t in terms:
        cat_color.setdefault(t["category"], t.get("color", "ink"))
    recurring = [t for t in terms if t.get("edition_count", 0) >= 3]
    multi = [t for t in terms if t.get("edition_count", 0) > 1]
    top_terms = sorted(terms, key=lambda t: t.get("edition_count", 0), reverse=True)[:14]

    # new terms first-defined per quarter
    coin_q = Counter()
    for t in terms:
        d = (t.get("first") or {}).get("date", "")
        if len(d) >= 7:
            mo = int(d[5:7])
            coin_q[f"{d[:4]} Q{(mo - 1) // 3 + 1}"] += 1

    # terms per edition (concentration)
    ed_terms = defaultdict(set)
    for t in terms:
        for e in t.get("editions", []):
            if e.get("edition"):
                ed_terms[e["edition"]].add(t["name"])
    ed_sizes = [len(v) for v in ed_terms.values()]

    # ---- links / interconnectedness ----
    links = json.load(open(DATA_DIR / "links.json"))

    return {
        "now": datetime.now().strftime("%B %-d, %Y"),
        "span": f"{years[0]}–{years[-1]}",
        "span_years": int(years[-1]) - int(years[0]),
        "n_posts": len(pub), "n_nl": len(nl), "n_essay": len(essays),
        "total_words": total_words, "total_rt": total_rt,
        "max_rt": max((p.get("reading_time") or 0) for p in pub),
        "words_nl": words_nl, "words_essay": words_essay,
        "longest": longest, "longest_wc": wc[longest["slug"]],
        "median_wc": median_wc, "mean_wc": mean_wc,
        "vocab": len(vocab),
        "year_rows": year_rows,
        "rt_buckets": rt_buckets,
        "n_terms": len(terms), "ed_count": ed_count,
        "cats": cats, "cat_color": cat_color,
        "recurring": len(recurring), "multi": len(multi),
        "top_terms": top_terms, "coin_q": coin_q,
        "ed_terms_avg": statistics.mean(ed_sizes) if ed_sizes else 0,
        "ed_terms_max": max(ed_sizes) if ed_sizes else 0,
        "n_editions_termed": len(ed_terms),
        "n_links": len(links.get("all_links", [])),
        "link_weeks": links.get("total_weeks", 0),
        "tnl": links.get("total_tnl", 0), "tws": links.get("total_tws", 0),
        "gs": gs,
    }


# ============================================================
# FORMAT + SVG HELPERS
# ============================================================

def _n(x):
    return f"{int(round(x)):,}"


def _color(name):
    """Map a lexicon color keyword to a CSS var; default to accent."""
    return {
        "teal": "var(--teal)", "gold": "var(--gold)",
        "orange": "var(--accent)", "accent": "var(--accent)",
    }.get(name, "var(--accent)")


def svg_col(data, w=560, h=200, pad_b=34, label_fmt=None, accent="var(--accent)",
            faint=None, value_fmt=_n):
    """Vertical column chart. data: list of (label, value[, is_faint])."""
    if not data:
        return ""
    vals = [d[1] for d in data]
    vmax = max(vals) or 1
    n = len(data)
    pad_l, pad_t, pad_r = 4, 16, 4
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    slot = plot_w / n
    bw = min(slot * 0.62, 46)
    bars = []
    for i, d in enumerate(data):
        lab, val = d[0], d[1]
        is_faint = len(d) > 2 and d[2]
        bh = (val / vmax) * plot_h
        x = pad_l + i * slot + (slot - bw) / 2
        y = pad_t + (plot_h - bh)
        fill = (faint or "var(--paper-rule)") if is_faint else accent
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'fill="{fill}" rx="1"/>'
        )
        # value above bar
        bars.append(
            f'<text x="{x + bw / 2:.1f}" y="{y - 5:.1f}" class="m-svg-val" '
            f'text-anchor="middle">{value_fmt(val)}</text>'
        )
        # label below
        lbl = label_fmt(lab) if label_fmt else lab
        bars.append(
            f'<text x="{x + bw / 2:.1f}" y="{h - 8:.1f}" class="m-svg-lbl" '
            f'text-anchor="middle">{lbl}</text>'
        )
    baseline = pad_t + plot_h
    return (
        f'<svg class="m-svg" viewBox="0 0 {w} {h}" role="img" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<line x1="{pad_l}" y1="{baseline:.1f}" x2="{w - pad_r}" y2="{baseline:.1f}" '
        f'class="m-svg-axis"/>'
        + "".join(bars) + "</svg>"
    )


def svg_ranked(data, w=560, row_h=26, accent="var(--accent)", value_fmt=_n):
    """Horizontal ranked bars. data: list of (label, value)."""
    if not data:
        return ""
    vmax = max(d[1] for d in data) or 1
    label_w = 168
    val_w = 52
    bar_max = w - label_w - val_w - 10
    h = row_h * len(data)
    rows = []
    for i, (lab, val) in enumerate(data):
        y = i * row_h
        cy = y + row_h / 2
        bw = (val / vmax) * bar_max
        rows.append(
            f'<text x="{label_w - 10}" y="{cy:.1f}" class="m-rank-lbl" '
            f'text-anchor="end" dominant-baseline="central">{lab}</text>'
            f'<rect x="{label_w}" y="{y + 4:.1f}" width="{bw:.1f}" '
            f'height="{row_h - 9:.1f}" fill="{accent}" rx="1"/>'
            f'<text x="{label_w + bw + 7:.1f}" y="{cy:.1f}" class="m-rank-val" '
            f'dominant-baseline="central">{value_fmt(val)}</text>'
        )
    return (
        f'<svg class="m-svg" viewBox="0 0 {w} {h}" role="img" '
        f'preserveAspectRatio="xMidYMid meet">' + "".join(rows) + "</svg>"
    )


def svg_line(rows, key, w=560, h=160, accent="var(--accent)", value_fmt="{:.1f}",
             dot_faint_below=5):
    """Single-metric line over years. rows: compute()['year_rows']."""
    pts = [(r["year"], r[key], r["posts"]) for r in rows if r.get(key) is not None]
    if len(pts) < 2:
        return ""
    vals = [p[1] for p in pts]
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or 1
    pad_l, pad_r, pad_t, pad_b = 6, 6, 22, 26
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    n = len(pts)

    def xy(i, v):
        x = pad_l + (i / (n - 1)) * plot_w
        y = pad_t + plot_h - ((v - vmin) / span) * plot_h
        return x, y

    path = []
    dots = []
    for i, (yr, v, posts) in enumerate(pts):
        x, y = xy(i, v)
        path.append(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}")
        faint = posts < dot_faint_below
        r = 2.4 if faint else 3.4
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
            f'fill="{"var(--paper)" if faint else accent}" '
            f'stroke="{accent}" stroke-width="{1.4 if faint else 0}"/>'
        )
        dots.append(
            f'<text x="{x:.1f}" y="{y - 9:.1f}" class="m-svg-val" '
            f'text-anchor="middle">{value_fmt.format(v)}</text>'
        )
        dots.append(
            f'<text x="{x:.1f}" y="{h - 8:.1f}" class="m-svg-lbl" '
            f'text-anchor="middle">{yr[2:]}</text>'
        )
    return (
        f'<svg class="m-svg" viewBox="0 0 {w} {h}" role="img" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<path d="{" ".join(path)}" fill="none" stroke="{accent}" '
        f'stroke-width="1.6" stroke-linejoin="round"/>'
        + "".join(dots) + "</svg>"
    )


def svg_stack(segments, w=560, h=30):
    """Single horizontal stacked bar. segments: list of (label, value, color)."""
    total = sum(s[1] for s in segments) or 1
    x = 0.0
    parts = []
    for lab, val, col in segments:
        seg_w = (val / total) * w
        parts.append(f'<rect x="{x:.1f}" y="0" width="{seg_w:.1f}" height="{h}" fill="{col}"/>')
        x += seg_w
    return (
        f'<svg class="m-svg" viewBox="0 0 {w} {h}" role="img" '
        f'preserveAspectRatio="none" style="height:{h}px">' + "".join(parts) + "</svg>"
    )


# ============================================================
# RENDER
# ============================================================

def _stat(num, label, sub=""):
    sub_html = f'<div class="m-stat-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="m-stat"><div class="m-stat-num">{num}</div>'
        f'<div class="m-stat-lbl">{label}</div>{sub_html}</div>'
    )


def _section(idx, kicker, title, note=""):
    note_html = f'<p class="m-sec-note">{note}</p>' if note else ""
    return f"""
<section class="m-sec">
  <div class="m-sec-head">
    <span class="m-sec-no">{idx}</span>
    <div>
      <div class="m-sec-kicker">{kicker}</div>
      <h2 class="m-sec-title">{title}</h2>
    </div>
  </div>
  {note_html}
"""


def render(d):
    gs = d["gs"]
    hrs = d["total_rt"] / 60
    pct_nl = d["words_nl"] / d["total_words"] * 100

    # ----- masthead + headline figures -----
    head = f"""
<header class="m-masthead">
  <div class="m-mast-kicker">Annual Report · The Quantified Corpus</div>
  <h1 class="m-mast-title">The Corpus Report</h1>
  <p class="m-mast-sub">A measured portrait of <strong>Token Wisdom</strong> —
     every word, edition, and idea, counted. {d['span']}.</p>
  <div class="m-mast-meta">Compiled {d['now']} · {d['n_posts']} entries ·
     {d['span_years']} years on record</div>
</header>

<div class="m-hero-grid">
  {_stat(_n(d['total_words']), 'Words written', f"across {d['n_posts']} entries")}
  {_stat(f"{hrs:.0f}", 'Hours of reading', f"{_n(d['total_rt'])} minutes, cover to cover")}
  {_stat(_n(d['n_terms']), 'Terms defined', 'in The Lexicon')}
  {_stat(_n(d['vocab']), 'Distinct words', 'the working vocabulary')}
  {_stat(_n(d['n_links']), 'Links curated', f"over {d['link_weeks']} weeks")}
  {_stat(d['span_years'], 'Years on record', d['span'])}
</div>
"""

    # ----- §1 word count -----
    year_words = [(r["year"], r["words"], r["posts"] < 5) for r in d["year_rows"]]
    longest_t = gs.clean_title(d["longest"]) if hasattr(gs, "clean_title") else d["longest"].get("title", "")
    s1 = _section("01", "Volume", "Word Count",
                  "538-thousand words is a long shelf. Here is how the corpus splits "
                  "between the weekly digest and the long-form essays, and how it "
                  "accumulated year over year.") + f"""
  <div class="m-split">
    <div class="m-split-bar">
      {svg_stack([('Newsletters', d['words_nl'], 'var(--accent)'),
                  ('Essays', d['words_essay'], 'var(--teal)')])}
      <div class="m-legend">
        <span><i style="background:var(--accent)"></i>Newsletters · {_n(d['words_nl'])} words ({pct_nl:.0f}%) · {d['n_nl']} editions</span>
        <span><i style="background:var(--teal)"></i>Essays · {_n(d['words_essay'])} words ({100 - pct_nl:.0f}%) · {d['n_essay']} pieces</span>
      </div>
    </div>
    <div class="m-mini-stats">
      {_stat(_n(d['mean_wc']), 'Average entry', 'words')}
      {_stat(_n(d['median_wc']), 'Median entry', 'words')}
      {_stat(_n(d['longest_wc']), 'Longest entry', 'words')}
    </div>
  </div>
  <p class="m-caption">The longest single entry — <em>{gs.esc(longest_t)}</em> —
     runs {_n(d['longest_wc'])} words on its own.</p>

  <div class="m-chart">
    <div class="m-chart-label">Words published per year</div>
    {svg_col(year_words, label_fmt=lambda y: y[2:], value_fmt=lambda v: f"{v/1000:.0f}k")}
    <div class="m-chart-foot">Faint columns are years with fewer than five entries.</div>
  </div>
"""

    # ----- §2 read time -----
    rt_order = ["≤3", "4–6", "7–10", "11–15", "16+"]
    rt_data = [(b, d["rt_buckets"].get(b, 0)) for b in rt_order]
    year_rt = [(r["year"], r["rt"], r["posts"] < 5) for r in d["year_rows"]]
    s2 = _section("02", "Attention", "Read Time",
                  f"At a steady pace the whole corpus is {hrs:.0f} hours of reading — "
                  "a full work-week and then some. Most entries, though, ask for far less.") + f"""
  <div class="m-two">
    <div class="m-chart">
      <div class="m-chart-label">Entries by reading time (minutes)</div>
      {svg_col(rt_data, w=420, accent="var(--teal)")}
    </div>
    <div class="m-chart">
      <div class="m-chart-label">Reading minutes added per year</div>
      {svg_col(year_rt, w=420, label_fmt=lambda y: y[2:], accent="var(--teal)")}
    </div>
  </div>
  <p class="m-caption">{hrs:.1f} hours all told · {d['total_rt'] / d['n_posts']:.0f} minutes
     for the average entry · the single longest read runs {d['max_rt']} minutes.</p>
"""

    # ----- §3 concentration -----
    cat_order = sorted(d["cats"].items(), key=lambda kv: kv[1], reverse=True)
    cat_segs = [(c, n, _color(d["cat_color"].get(c, "accent"))) for c, n in cat_order]
    cat_legend = "".join(
        f'<span><i style="background:{_color(d["cat_color"].get(c, "accent"))}"></i>'
        f'{c} · {_n(n)}</span>'
        for c, n in cat_order
    )
    coin_keys = sorted(d["coin_q"])
    coin_data = [(k, d["coin_q"][k]) for k in coin_keys]
    s3 = _section("03", "Density", "Concentration of Writing",
                  "The Lexicon is the corpus distilled. Every edition mints new "
                  "vocabulary; the average edition introduces dozens of defined terms, "
                  "and the rate of coinage tells you when the field — and the writing — "
                  "accelerated.") + f"""
  <div class="m-mini-stats m-mini-4">
    {_stat(f"{d['ed_terms_avg']:.0f}", 'Terms per edition', 'on average')}
    {_stat(_n(d['ed_terms_max']), 'Densest edition', 'defined terms')}
    {_stat(_n(d['n_terms']), 'Terms total', f"from {d['ed_count']} editions")}
    {_stat(f"{d['n_terms'] / max(1, d['ed_count']):.0f}", 'Net new / edition', 'across the run')}
  </div>

  <div class="m-chart">
    <div class="m-chart-label">The Lexicon by category</div>
    {svg_stack(cat_segs)}
    <div class="m-legend m-legend-wrap">{cat_legend}</div>
  </div>

  <div class="m-chart">
    <div class="m-chart-label">New terms first defined, by quarter</div>
    {svg_col(coin_data, w=620, label_fmt=lambda k: k.replace(' ', '<tspan class="m-q"> ') + '</tspan>',
             accent="var(--gold)")}
    <div class="m-chart-foot">Each column counts terms making their first
       appearance that quarter — the corpus's rate of new ideas.</div>
  </div>
"""

    # ----- §4 interconnectedness -----
    top_rank = [(gs.esc(t["name"]), t.get("edition_count", 0)) for t in d["top_terms"]]
    pct_multi = d["multi"] / d["n_terms"] * 100
    s4 = _section("04", "The Graph", "Interconnectedness",
                  "Ideas don't live in one edition. Terms recur, binding issues "
                  "together into a web — and a curated trail of outside reading "
                  "anchors the whole thing to the wider world.") + f"""
  <div class="m-mini-stats m-mini-4">
    {_stat(_n(d['multi']), 'Recurring terms', f"appear in 2+ editions ({pct_multi:.0f}%)")}
    {_stat(_n(d['recurring']), 'Connective tissue', 'terms in 3+ editions')}
    {_stat(_n(d['n_links']), 'Outbound links', f"across {d['link_weeks']} weeks")}
    {_stat(f"{d['n_links'] / max(1, d['link_weeks']):.0f}", 'Links per week', 'curated, on average')}
  </div>

  <div class="m-chart">
    <div class="m-chart-label">Most-connected terms — appearances across editions</div>
    {svg_ranked(top_rank)}
    <div class="m-chart-foot">The terms that thread through the most issues are the
       corpus's load-bearing concepts.</div>
  </div>
"""

    # ----- §5 writing style progression -----
    style_rows = [r for r in d["year_rows"] if r["posts"] >= 5]
    first, last = style_rows[0], style_rows[-1]
    peak_asl = max(style_rows, key=lambda r: r["asl"])
    peak_awl = max(style_rows, key=lambda r: r["awl"])
    s5 = _section("05", "Evolution", "Progress in Writing Style",
                  f"Measured across {len(style_rows)} substantial years, the prose "
                  "lengthened and thickened: longer sentences, longer words, a denser "
                  "register. The corpus grew up.") + f"""
  <div class="m-three">
    <div class="m-chart">
      <div class="m-chart-label">Average sentence length (words)</div>
      {svg_line(d['year_rows'], 'asl', w=360, value_fmt="{:.0f}")}
    </div>
    <div class="m-chart">
      <div class="m-chart-label">Average word length (letters)</div>
      {svg_line(d['year_rows'], 'awl', w=360, accent="var(--teal)", value_fmt="{:.1f}")}
    </div>
    <div class="m-chart">
      <div class="m-chart-label">Vocabulary richness (TTR %)</div>
      {svg_line(d['year_rows'], 'ttr', w=360, accent="var(--gold)", value_fmt="{:.0f}")}
    </div>
  </div>
  <p class="m-caption">From {first['year']}'s {first['asl']:.0f}-word sentences the prose
     stretched to a peak of {peak_asl['asl']:.0f} words in {peak_asl['year']}, before
     settling back; average word length thickened from {first['awl']:.1f} letters to a high
     of {peak_awl['awl']:.1f} in {peak_awl['year']}. Vocabulary richness is measured on
     length-normalised 1,000-word windows, so it compares fairly across years of very
     different size.</p>
"""

    # ----- methodology -----
    method = f"""
<section class="m-method">
  <div class="m-sec-kicker">Methodology</div>
  <p>Figures are computed directly from {d['n_posts']} published entries
     ({d['span']}). Word counts tokenise the plain-text body of each post;
     reading time is Ghost's own estimate. Lexicon figures come from
     {d['n_terms']} terms harvested from every edition's <em>“The Less You Know”</em>
     section across {d['ed_count']} editions. The link graph counts
     {_n(d['n_links'])} curated outbound references logged over {d['link_weeks']}
     weeks. Vocabulary richness uses the mean type–token ratio over consecutive
     1,000-word windows to stay comparable across years. Compiled {d['now']}.</p>
</section>
"""

    return CSS + head + s1 + "</section>" + s2 + "</section>" + s3 + "</section>" \
        + s4 + "</section>" + s5 + "</section>" + method


# ============================================================
# SCOPED STYLES
# ============================================================

CSS = """
<style>
.m-wrap { max-width: var(--max-wide); margin: 0 auto; padding: 0 24px 5rem; }

/* masthead */
.m-masthead { padding: 4rem 0 2.4rem; border-bottom: 2px solid var(--ink); }
.m-mast-kicker {
  font-family: var(--mono); font-weight: var(--mono-weight);
  font-size: 11px; letter-spacing: .22em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 1.1rem;
}
.m-mast-title {
  font-family: var(--display); font-weight: 700; line-height: .95;
  font-size: clamp(3rem, 9vw, 6.4rem); letter-spacing: -.02em; color: var(--ink);
}
.m-mast-sub {
  font-family: var(--serif); font-size: clamp(1.05rem, 2.2vw, 1.45rem);
  line-height: 1.5; color: var(--ink-muted); max-width: 40ch; margin-top: 1.2rem;
}
.m-mast-sub strong { color: var(--ink); font-weight: 600; }
.m-mast-meta {
  font-family: var(--mono); font-weight: var(--mono-weight); font-size: 11px;
  letter-spacing: .14em; text-transform: uppercase; color: var(--ink-faint);
  margin-top: 1.4rem;
}

/* hero figures */
.m-hero-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--paper-rule); margin-top: 2.4rem;
}
.m-hero-grid .m-stat {
  border-bottom: 1px solid var(--paper-rule); border-right: 1px solid var(--paper-rule);
  padding: 1.6rem 1.4rem;
}
.m-hero-grid .m-stat:nth-child(3n) { border-right: none; }

.m-stat-num {
  font-family: var(--display); font-weight: 700; line-height: 1;
  font-size: clamp(2.1rem, 4.5vw, 3.2rem); letter-spacing: -.02em; color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.m-stat-lbl {
  font-family: var(--mono); font-weight: 400; font-size: 11px;
  letter-spacing: .14em; text-transform: uppercase; color: var(--ink); margin-top: .7rem;
}
.m-stat-sub {
  font-family: var(--mono); font-weight: var(--mono-weight); font-size: 11px;
  letter-spacing: .04em; color: var(--ink-faint); margin-top: .25rem;
}

/* sections */
.m-sec { padding: 3.6rem 0 0.5rem; }
.m-sec-head { display: flex; gap: 1.2rem; align-items: baseline; border-top: 2px solid var(--ink); padding-top: 1rem; }
.m-sec-no {
  font-family: var(--mono); font-weight: 500; font-size: 13px;
  letter-spacing: .1em; color: var(--accent);
}
.m-sec-kicker {
  font-family: var(--mono); font-weight: var(--mono-weight); font-size: 11px;
  letter-spacing: .2em; text-transform: uppercase; color: var(--ink-muted);
}
.m-sec-title {
  font-family: var(--display); font-weight: 700; font-size: clamp(1.8rem, 4vw, 2.9rem);
  letter-spacing: -.015em; color: var(--ink); line-height: 1.04; margin-top: .15rem;
}
.m-sec-note {
  font-family: var(--serif); font-size: 1.12rem; line-height: 1.65;
  color: var(--ink-muted); max-width: 62ch; margin: 1.4rem 0 2rem;
}
.m-caption {
  font-family: var(--serif); font-size: .98rem; line-height: 1.6;
  color: var(--ink-muted); max-width: 64ch; margin: 1.6rem 0 0;
}
.m-caption em, .m-sec-note em, .m-method em { font-style: italic; color: var(--ink); }

/* layout helpers */
.m-split { display: grid; grid-template-columns: 1.6fr 1fr; gap: 2.4rem; align-items: start; margin-top: .5rem; }
.m-two { display: grid; grid-template-columns: 1fr 1fr; gap: 2.4rem; }
.m-three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.8rem; }
.m-mini-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0; border-top: 1px solid var(--paper-rule); }
.m-mini-4 { grid-template-columns: repeat(4, 1fr); }
.m-mini-stats .m-stat { padding: 1.1rem 1.2rem 1.1rem 0; border-bottom: 1px solid var(--paper-rule); }
.m-mini-stats .m-stat-num { font-size: clamp(1.6rem, 3.2vw, 2.3rem); }

/* charts */
.m-chart { margin-top: 2.2rem; }
.m-chart-label {
  font-family: var(--mono); font-weight: 400; font-size: 11px;
  letter-spacing: .14em; text-transform: uppercase; color: var(--ink);
  padding-bottom: .7rem; border-bottom: 1px solid var(--paper-rule); margin-bottom: 1.1rem;
}
.m-chart-foot, .m-legend {
  font-family: var(--mono); font-weight: var(--mono-weight); font-size: 11px;
  letter-spacing: .03em; color: var(--ink-faint); margin-top: .9rem; line-height: 1.5;
}
.m-svg { width: 100%; height: auto; overflow: visible; display: block; }
.m-svg-val { font-family: var(--mono); font-weight: 400; font-size: 11px; fill: var(--ink-muted); }
.m-svg-lbl { font-family: var(--mono); font-weight: var(--mono-weight); font-size: 10px; fill: var(--ink-faint); letter-spacing: .05em; }
.m-svg-axis { stroke: var(--ink); stroke-width: 1; }
.m-rank-lbl { font-family: var(--mono); font-weight: 400; font-size: 12px; fill: var(--ink); }
.m-rank-val { font-family: var(--mono); font-weight: 500; font-size: 12px; fill: var(--accent); }
.m-q { fill: var(--ink-faint); }

.m-legend { display: flex; flex-wrap: wrap; gap: 1.4rem; color: var(--ink-muted); }
.m-legend-wrap span { font-size: 11px; }
.m-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: .5rem; vertical-align: middle; }
.m-split-bar .m-svg { border-radius: 2px; overflow: hidden; }
.m-mini-stats.m-mini-4 + .m-chart { margin-top: 2.6rem; }

/* methodology */
.m-method {
  margin-top: 4rem; padding: 2rem 0 0; border-top: 2px solid var(--ink);
}
.m-method p {
  font-family: var(--serif); font-size: .98rem; line-height: 1.7;
  color: var(--ink-muted); max-width: 72ch; margin-top: 1rem;
}

@media (max-width: 860px) {
  .m-hero-grid { grid-template-columns: repeat(2, 1fr); }
  .m-hero-grid .m-stat:nth-child(3n) { border-right: 1px solid var(--paper-rule); }
  .m-hero-grid .m-stat:nth-child(2n) { border-right: none; }
  .m-split, .m-two, .m-three { grid-template-columns: 1fr; gap: 1.6rem; }
  .m-mini-4 { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 520px) {
  .m-hero-grid { grid-template-columns: 1fr; }
  .m-hero-grid .m-stat, .m-hero-grid .m-stat:nth-child(n) { border-right: none; }
  .m-mini-stats, .m-mini-4 { grid-template-columns: 1fr 1fr; }
}
</style>
<div class="m-wrap">
"""


# ============================================================
# BUILD
# ============================================================

def build(posts, ctx, gs):
    d = compute(posts, gs)
    body = render(d) + "</div>"  # close .m-wrap
    page = gs.page_shell("The Corpus Report", body, "style.css", from_dir="root")
    page += gs.colophon(ctx["posts_count"], ctx["tags_count"],
                        ctx["years_span"], ctx["top_tags"], from_dir="root")
    with open(DOCS_DIR / "metrics.html", "w") as f:
        f.write(page)
    print(f"  Wrote docs/metrics.html — {_n(d['total_words'])} words, "
          f"{d['n_terms']} terms, {d['n_links']} links charted")


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

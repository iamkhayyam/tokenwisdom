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
CONSTELLATION_MIN = 2  # terms glossed in 2+ editions form the live network map


def _constellation_data(terms, min_ed=CONSTELLATION_MIN):
    """Nodes = recurring terms; edges = the 'travels with' co-occurrence links,
    kept undirected (max shared weight) and restricted to the node set."""
    nodes = [t for t in terms if t["edition_count"] >= min_ed]
    idx = {t["slug"]: i for i, t in enumerate(nodes)}
    node_rows = [
        [t["slug"], t["name"], t.get("color", "accent"),
         t["category"], t["edition_count"], _clamp(t["definition"], 90)]
        for t in nodes
    ]
    seen = {}
    for t in nodes:
        a = idx[t["slug"]]
        for r in t.get("related", []):
            b = idx.get(r["slug"])
            if b is None or b == a:
                continue
            key = (a, b) if a < b else (b, a)
            w = int(r.get("shared", 1) or 1)
            if w > seen.get(key, 0):
                seen[key] = w
    links = [[a, b, w] for (a, b), w in seen.items()]
    return node_rows, links


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
  <div class="kicker kicker-accent">The Lexicon</div>
  <h1 class="lex-h1">The Lexicon</h1>
  <p class="lex-lede">The working vocabulary of the future of now — {len(terms):,} terms, defined by hand in <em>The Less You Know</em> across {ctx['edition_count']} editions. Every definition is the newsletter's own; recurring terms trace how the language of the field accumulated, week over week.</p>
  <div class="lex-metaline">{total_entries:,} definitions · {len(core)} recurring terms · {span} · 100% authentic humanly chosen</div>
  <input id="lexSearch" class="lex-search" type="search" autocomplete="off" placeholder="Search all {len(terms):,} terms…" aria-label="Search the Lexicon">
  <div class="lex-chips">{chips}</div>
  <a class="lex-constellation-cta" href="constellation.html">✦ Open the Constellation — the Lexicon as a living map &rarr;</a>
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
  <h3>From the Lab</h3>
  <p>The Lexicon is the data layer. <strong><a href="constellation.html">The Constellation</a></strong> is now live — browse the recurring terms as a map of what's glossed together. Next on the bench, both powered by the same data: <strong>Ask the Archive</strong> (question three years of writing), and <strong>the Zeitgeist Tracker</strong> (what mattered when, across {len(qkeys)} quarters).</p>
</div></div>
</div>
<script>window.LEX_BASE="";window.LEX_ALL={all_data};</script>
{theme.SEARCH_JS}
'''
    return theme.page("The Lexicon — Token Wisdom", body, prefix="../", lex=True, active="lexicon")


CONSTELLATION_CSS = r'''
.cst-hero{max-width:var(--w);margin:0 auto;padding:30px 28px 14px}
.cst-back{display:inline-block;font-family:var(--mono);font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin-bottom:1.2rem}
.cst-lede{font-family:var(--serif);font-size:1.05rem;line-height:1.5;color:var(--ink-muted);max-width:60ch;margin:.5rem 0 0}
.cst-stage{position:relative;max-width:var(--w);margin:1.2rem auto 0;padding:0 28px}
.cst-canvas-wrap{position:relative;border:2px solid var(--ink);background:
  radial-gradient(circle at 50% 40%, color-mix(in oklch,var(--accent) 5%,transparent), transparent 60%),
  var(--bg);height:min(74vh,720px);overflow:hidden;touch-action:none;cursor:grab}
.cst-canvas-wrap.is-panning{cursor:grabbing}
#cstCanvas{display:block;width:100%;height:100%}
.cst-hud{position:absolute;top:14px;left:14px;right:14px;display:flex;gap:12px;align-items:flex-start;justify-content:space-between;pointer-events:none;flex-wrap:wrap}
.cst-search{pointer-events:auto;font-family:var(--mono);font-size:.78rem;letter-spacing:.02em;padding:.55em .8em;width:min(260px,46vw);background:color-mix(in oklch,var(--bg) 88%,transparent);border:1.5px solid var(--ink);color:var(--ink);backdrop-filter:blur(6px)}
.cst-search::placeholder{color:var(--ink-faint)}
.cst-legend{pointer-events:auto;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;max-width:60%}
.cst-leg{display:inline-flex;align-items:center;gap:.45em;font-family:var(--mono);font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;padding:.35em .6em;border:1.5px solid var(--rule);background:color-mix(in oklch,var(--bg) 85%,transparent);color:var(--ink-muted);cursor:pointer;backdrop-filter:blur(6px);user-select:none;transition:border-color .15s,color .15s,opacity .15s}
.cst-leg .dot{width:9px;height:9px;border-radius:50%}
.cst-leg.off{opacity:.4} .cst-leg:hover{color:var(--ink)}
.cst-leg span.n{color:var(--ink-faint)}
.cst-tip{position:absolute;pointer-events:none;z-index:5;max-width:260px;padding:.6em .75em;background:var(--ink);color:var(--bg);border-radius:2px;opacity:0;transform:translateY(4px);transition:opacity .12s,transform .12s;font-family:var(--sans)}
.cst-tip.show{opacity:1;transform:translateY(0)}
.cst-tip b{display:block;font-weight:800;font-size:.92rem;margin-bottom:.2em}
.cst-tip .cat{font-family:var(--mono);font-size:.56rem;letter-spacing:.1em;text-transform:uppercase;opacity:.7}
.cst-tip .def{font-family:var(--serif);font-size:.82rem;line-height:1.35;margin-top:.35em;opacity:.92}
.cst-bar{display:flex;align-items:center;gap:18px;flex-wrap:wrap;max-width:var(--w);margin:.8rem auto 0;padding:0 28px;font-family:var(--mono);font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}
.cst-bar b{color:var(--ink);font-weight:700}
.cst-bar .cst-reset{margin-left:auto;pointer-events:auto;cursor:pointer;border:1.5px solid var(--rule);background:transparent;color:var(--ink-muted);font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;padding:.4em .7em}
.cst-bar .cst-reset:hover{border-color:var(--ink);color:var(--ink)}
/* mobile: collapse the legend toggles to colour-only swatches (no text) */
@media(max-width:640px){
  .cst-canvas-wrap{height:64vh}.cst-hud{gap:10px}.cst-search{width:100%}
  .cst-legend{width:100%;max-width:100%;flex-wrap:nowrap;gap:8px}
  .cst-leg{flex:1;justify-content:center;font-size:0;gap:0;padding:11px 8px;letter-spacing:0}
  .cst-leg .dot{width:100%;height:14px;border-radius:4px}
  .cst-leg.off{opacity:.3}
}
'''

# Self-contained force-directed renderer — no external libraries (matches the
# static-site, zero-build ethos of the rest of generate_site.py).
CONSTELLATION_JS = r'''
<script>
(function(){
  var D = window.CONSTELLATION; if(!D) return;
  var N = D.nodes, L = D.links;
  var cvs = document.getElementById('cstCanvas');
  var wrap = document.getElementById('cstWrap');
  var tip = document.getElementById('cstTip');
  var search = document.getElementById('cstSearch');
  var ctx = cvs.getContext('2d');
  var cs = getComputedStyle(document.documentElement);
  function v(n){return cs.getPropertyValue(n).trim();}
  var COL = {accent:v('--accent')||'#c0562b', teal:v('--teal')||'#2e8a8a', gold:v('--gold')||'#caa14a'};
  var INK = v('--ink')||'#222', FAINT = v('--ink-faint')||'#aaa', RULE = v('--rule')||'#e2e2e2';
  var BG = v('--bg')||'#faf8f4';

  // ---- model ----
  var n = N.length, i;
  var px=new Float64Array(n), py=new Float64Array(n), vx=new Float64Array(n), vy=new Float64Array(n);
  var deg=new Int32Array(n);
  for(i=0;i<L.length;i++){deg[L[i][0]]++;deg[L[i][1]]++;}
  // seed on a spiral so the layout opens predictably (no Math.random — deterministic build)
  for(i=0;i<n;i++){var a=i*2.399963, r=8+Math.sqrt(i)*16; px[i]=Math.cos(a)*r; py[i]=Math.sin(a)*r;}
  function radius(k){return 4 + Math.sqrt(N[k][4])*2.1;}        // by editions glossed
  var catSet = {};                                              // active category filter
  D.cats.forEach(function(c){catSet[c[0]]=true;});

  // ---- view transform ----
  var scale=1, tx=0, ty=0, W=0, H=0, dpr=Math.min(window.devicePixelRatio||1,2);
  function resize(){
    var r=wrap.getBoundingClientRect(); W=r.width; H=r.height;
    cvs.width=W*dpr; cvs.height=H*dpr; cvs.style.width=W+'px'; cvs.style.height=H+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }
  function fit(onlyVisible){
    var minx=1e9,miny=1e9,maxx=-1e9,maxy=-1e9,any=false;
    for(i=0;i<n;i++){ if(onlyVisible&&!catSet[N[i][3]])continue; any=true;
      if(px[i]<minx)minx=px[i];if(px[i]>maxx)maxx=px[i];if(py[i]<miny)miny=py[i];if(py[i]>maxy)maxy=py[i]; }
    if(!any){fit(false);return;}
    var gw=(maxx-minx)||1, gh=(maxy-miny)||1, pad=70;
    scale=Math.min((W-pad)/gw,(H-pad)/gh); scale=Math.max(.06,Math.min(scale,2.0));
    tx=W/2 - ((minx+maxx)/2)*scale; ty=H/2 - ((miny+maxy)/2)*scale;
  }
  function toScreen(k){return [px[k]*scale+tx, py[k]*scale+ty];}
  function toWorld(sx,sy){return [(sx-tx)/scale,(sy-ty)/scale];}

  // ---- physics (O(n^2) repulsion — fine for a few hundred nodes) ----
  var alpha=1, ALPHA_MIN=0.012, ALPHA_DECAY=0.015, running=true, dragK=-1, pinned={};
  var K_REP=2600, K_SPRING=0.06, REST=50, K_GRAV=0.03, DMIN2=64, MAXV=22;
  function tick(){
    var dx,dy,d2,d,f,a,b;
    for(i=0;i<n;i++){
      // gravity to centre
      vx[i]-=px[i]*K_GRAV*alpha; vy[i]-=py[i]*K_GRAV*alpha;
    }
    for(a=0;a<n;a++) for(b=a+1;b<n;b++){
      dx=px[a]-px[b]; dy=py[a]-py[b]; d2=dx*dx+dy*dy; if(d2<DMIN2)d2=DMIN2;  // distance floor → bounded force
      d=Math.sqrt(d2); f=K_REP/d2*alpha; var ux=dx/d,uy=dy/d;
      vx[a]+=ux*f; vy[a]+=uy*f; vx[b]-=ux*f; vy[b]-=uy*f;
    }
    for(i=0;i<L.length;i++){
      a=L[i][0]; b=L[i][1]; dx=px[b]-px[a]; dy=py[b]-py[a];
      d=Math.sqrt(dx*dx+dy*dy)||0.01; f=(d-REST)*K_SPRING*alpha;
      var sx=dx/d*f, sy=dy/d*f; vx[a]+=sx; vy[a]+=sy; vx[b]-=sx; vy[b]-=sy;
    }
    for(i=0;i<n;i++){
      if(pinned[i]){vx[i]=0;vy[i]=0;continue;}
      vx[i]*=0.85; vy[i]*=0.85;
      var sp=Math.sqrt(vx[i]*vx[i]+vy[i]*vy[i]); if(sp>MAXV){var sc2=MAXV/sp; vx[i]*=sc2; vy[i]*=sc2;}  // velocity clamp → no blow-up
      px[i]+=vx[i]; py[i]+=vy[i];
    }
    alpha*=(1-ALPHA_DECAY);
    if(alpha<ALPHA_MIN){alpha=0; running=false;}
  }
  function reheat(a){alpha=Math.max(alpha,a||0.5); if(!running){running=true;loop();}}

  // ---- interaction state ----
  var hover=-1, focusK=-1, q='';
  function matches(k){
    if(!catSet[N[k][3]]) return false;
    if(q && N[k][1].toLowerCase().indexOf(q)<0) return false;
    return true;
  }
  var nbr = {};                                  // adjacency for highlight
  for(i=0;i<L.length;i++){ (nbr[L[i][0]]=nbr[L[i][0]]||{})[L[i][1]]=1; (nbr[L[i][1]]=nbr[L[i][1]]||{})[L[i][0]]=1; }
  function isNbr(a,b){return a===b || (nbr[a]&&nbr[a][b]);}

  // ---- draw ----
  function draw(){
    ctx.clearRect(0,0,W,H);
    var hi = hover>=0?hover:focusK;            // node whose neighbourhood we spotlight
    var anyDim = hi>=0 || q;
    // edges
    for(i=0;i<L.length;i++){
      var a=L[i][0], b=L[i][1];
      if(!matches(a)&&!matches(b)) continue;
      var sa=toScreen(a), sb=toScreen(b);
      var lit = hi>=0 ? (isNbr(hi,a)&&isNbr(hi,b)) : true;
      ctx.beginPath(); ctx.moveTo(sa[0],sa[1]); ctx.lineTo(sb[0],sb[1]);
      ctx.lineWidth=Math.max(.4,Math.min(L[i][2]*0.22,3))*(lit?1:1);
      ctx.strokeStyle = lit ? colWithA(COL[N[a][2]],0.5) : colWithA(FAINT,anyDim?0.06:0.16);
      ctx.stroke();
    }
    // nodes
    for(i=0;i<n;i++){
      if(!catSet[N[i][3]]) continue;
      var s=toScreen(i), r=radius(i);
      var on = matches(i);
      var lit = hi>=0 ? isNbr(hi,i) : true;
      var faded = (!on) || (anyDim && !lit);
      ctx.beginPath(); ctx.arc(s[0],s[1],r,0,6.2832);
      ctx.fillStyle = faded ? colWithA(COL[N[i][2]],0.12) : COL[N[i][2]];
      ctx.fill();
      if(i===hi){ctx.lineWidth=2;ctx.strokeStyle=INK;ctx.stroke();}
      // labels for big / hovered / searched nodes
      if((!faded) && (N[i][4]>=6 || i===hi || (q && on) || scale>1.25)){
        ctx.font='600 '+(11)+'px Archivo, system-ui, sans-serif';
        ctx.fillStyle = faded?FAINT:INK; ctx.textAlign='left'; ctx.textBaseline='middle';
        ctx.fillText(N[i][1], s[0]+r+4, s[1]);
      }
    }
  }
  function colWithA(c,a){ // wrap any color string with alpha via color-mix-free rgba fallback
    return 'color-mix(in oklch, '+c+' '+(a*100)+'%, transparent)';
  }

  function loop(){ if(running){tick();} draw(); if(running) requestAnimationFrame(loop); }

  // ---- hit testing ----
  function nodeAt(sx,sy){
    var best=-1,bd=1e9;
    for(i=0;i<n;i++){ if(!catSet[N[i][3]])continue; var s=toScreen(i),r=radius(i)+4; var dx=sx-s[0],dy=sy-s[1],d=dx*dx+dy*dy; if(d<r*r&&d<bd){bd=d;best=i;} }
    return best;
  }

  // ---- pointer: pan / drag / hover / click ----
  var dragging=false, panning=false, moved=false, lx=0, ly=0, downK=-1;
  cvs.addEventListener('pointerdown',function(e){
    var rect=cvs.getBoundingClientRect(), sx=e.clientX-rect.left, sy=e.clientY-rect.top;
    cvs.setPointerCapture(e.pointerId); lx=sx; ly=sy; moved=false;
    var k=nodeAt(sx,sy);
    if(k>=0){downK=k; dragging=true; pinned[k]=1; reheat(0.3);}
    else {panning=true; wrap.classList.add('is-panning');}
  });
  cvs.addEventListener('pointermove',function(e){
    var rect=cvs.getBoundingClientRect(), sx=e.clientX-rect.left, sy=e.clientY-rect.top;
    if(dragging&&downK>=0){ var w=toWorld(sx,sy); px[downK]=w[0]; py[downK]=w[1]; vx[downK]=vy[downK]=0; moved=true; reheat(0.35); }
    else if(panning){ tx+=sx-lx; ty+=sy-ly; lx=sx; ly=sy; moved=true; if(!running)draw(); }
    else { var k=nodeAt(sx,sy); if(k!==hover){hover=k; updateTip(k,sx,sy); if(!running)draw();} else updateTip(k,sx,sy); }
  });
  function endPtr(e){
    if(dragging&&downK>=0){ pinned[downK]=0; if(!moved){ location.href = N[downK][0]+'.html'; } }
    dragging=panning=false; downK=-1; wrap.classList.remove('is-panning');
  }
  cvs.addEventListener('pointerup',endPtr);
  cvs.addEventListener('pointerleave',function(){hover=-1;tip.classList.remove('show');if(!running)draw();});
  cvs.addEventListener('wheel',function(e){
    e.preventDefault();
    var rect=cvs.getBoundingClientRect(), sx=e.clientX-rect.left, sy=e.clientY-rect.top;
    var w=toWorld(sx,sy), f=Math.exp(-e.deltaY*0.0014); var ns=Math.max(.12,Math.min(scale*f,5));
    tx=sx-w[0]*ns; ty=sy-w[1]*ns; scale=ns; if(!running)draw();
  },{passive:false});

  function updateTip(k,sx,sy){
    if(k<0){tip.classList.remove('show');return;}
    tip.innerHTML='<span class="cat">'+esc(N[k][3])+' · '+N[k][4]+'×</span><b>'+esc(N[k][1])+'</b><span class="def">'+esc(N[k][5])+'</span>';
    var tw=tip.offsetWidth, th=tip.offsetHeight;
    tip.style.left=Math.min(sx+14, W-tw-8)+'px'; tip.style.top=Math.max(8, sy-th-12)+'px';
    tip.classList.add('show');
  }
  function esc(s){return String(s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}

  // ---- search ----
  search.addEventListener('input',function(){
    q=search.value.trim().toLowerCase(); focusK=-1;
    if(q){ var hit=-1; for(i=0;i<n;i++){ if(N[i][1].toLowerCase().indexOf(q)===0){hit=i;break;} } if(hit<0)for(i=0;i<n;i++){if(matches(i)){hit=i;break;}}
      if(hit>=0){ focusK=hit; centerOn(hit, 1.4); } }
    if(!running)draw();
  });
  function centerOn(k, sc){
    sc=sc||1.3; scale=sc; tx=W/2-px[k]*scale; ty=H/2-py[k]*scale; if(!running)draw();
  }

  // ---- legend ----
  document.querySelectorAll('.cst-leg').forEach(function(el){
    el.addEventListener('click',function(){
      var c=el.getAttribute('data-cat'); catSet[c]=!catSet[c]; el.classList.toggle('off',!catSet[c]); if(!running)draw();
    });
  });
  document.getElementById('cstReset').addEventListener('click',function(){
    search.value=''; q=''; focusK=-1; hover=-1; D.cats.forEach(function(c){catSet[c[0]]=true;});
    document.querySelectorAll('.cst-leg').forEach(function(e){e.classList.remove('off');});
    fit(); reheat(0.6);
  });

  // ---- boot ----
  resize();
  // settle the layout headlessly so first paint is already readable
  for(i=0;i<420 && alpha>ALPHA_MIN;i++) tick();
  alpha=0; running=false; fit();
  // deep link: #slug focuses a node
  if(location.hash.length>1){ var h=decodeURIComponent(location.hash.slice(1)); for(i=0;i<n;i++){ if(N[i][0]===h){ focusK=i; centerOn(i,1.5); break; } } }
  draw();
  window.addEventListener('resize',function(){resize();draw();});
})();
</script>
'''


def render_constellation(terms, gs, ctx):
    nodes, links = _constellation_data(terms)
    # category legend, in canonical order, coloured by the category's own colour
    by_cat = Counter(n[3] for n in nodes)
    cat_color = {}
    for n in nodes:
        cat_color.setdefault(n[3], n[2])
    cats = [[c, cat_color[c], by_cat[c]] for c in src.CATEGORY_ORDER if by_cat.get(c)]
    legend = "".join(
        f'<button class="cst-leg" data-cat="{esc(c)}">'
        f'<span class="dot" style="background:{COLOR_VAR.get(col, "var(--accent)")}"></span>'
        f'{esc(c)} <span class="n">{n}</span></button>'
        for c, col, n in cats)
    legend_data = [[c] for c, _, _ in cats]

    payload = json.dumps({"nodes": nodes, "links": links, "cats": legend_data},
                         ensure_ascii=False, separators=(",", ":"))

    body = f'''
<style>{CONSTELLATION_CSS}</style>
<header class="cst-hero">
  <a class="cst-back" href="index.html">&larr; The Lexicon</a>
  <div class="kicker kicker-accent">The Lexicon · The Constellation</div>
  <h1 class="lex-h1">The Constellation</h1>
  <p class="cst-lede">The Lexicon as a map of what's glossed together. Each of these {len(nodes)} recurring terms is a star; a line ties two terms that were defined in the same editions — the more often they travel together, the brighter the link. Drag a star, search to find one, click through to its full entry.</p>
</header>
<div class="cst-stage">
  <div id="cstWrap" class="cst-canvas-wrap">
    <canvas id="cstCanvas"></canvas>
    <div class="cst-hud">
      <input id="cstSearch" class="cst-search" type="search" autocomplete="off" placeholder="Find a term in the map…" aria-label="Find a term">
      <div class="cst-legend" role="group" aria-label="Toggle categories">{legend}</div>
    </div>
    <div id="cstTip" class="cst-tip"></div>
  </div>
</div>
<div class="cst-bar">
  <span><b>{len(nodes)}</b> terms</span>
  <span><b>{len(links)}</b> co-occurrence links</span>
  <span>drag · scroll to zoom · click a star to open it</span>
  <button id="cstReset" class="cst-reset">Reset view</button>
</div>
<script>window.CONSTELLATION={payload};</script>
{CONSTELLATION_JS}
'''
    return theme.page("The Constellation — The Lexicon", body, prefix="../", lex=True, active="lexicon")


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
  <div class="kicker kicker-accent">Lexicon · Category</div>
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

    constellation = ""
    if t["edition_count"] >= CONSTELLATION_MIN:
        constellation = (f'<div class="term-side-block"><a class="lex-seeall" '
                         f'href="constellation.html#{t["slug"]}">✦ See it in the Constellation &rarr;</a></div>')

    body = f'''
<div class="term-wrap">
  <a class="term-back" href="index.html">&larr; The Lexicon</a>
  <div class="term-eyebrow lex-text-{color}">{esc(t['category'])}</div>
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
    <aside class="term-side">{related}{constellation}
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

    with open(lex_dir / "constellation.html", "w") as f:
        f.write(render_constellation(terms, gs, ctx))

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
    print(f"  Wrote index + Constellation + {cat_n} category pages + {len(terms)} term pages + data/lexicon.json")
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

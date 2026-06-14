#!/usr/bin/env python3
"""
Lexicon index redesign mockup — brand-consistent with the new homepage.

Reuses the homepage's base CSS + masthead (from mockup_home) so the chrome is
identical, then lays out the Lexicon index (hero + search + Core Vocabulary +
category sections) in the new system. Writes docs/lexicon-v2.html for preview.

Run:  python3 mockup_lexicon.py   ·   Preview: localhost:8765/lexicon-v2.html
"""

import json
from pathlib import Path
import mockup_home as mh          # base CSS + masthead chrome
import lexicon as lx             # sparkline

BACKUP = Path(__file__).parent
DOCS = BACKUP / "docs"
e = mh.e

CATEGORY_ORDER = ["Technologies", "Concepts", "Technical Terms", "Acronyms", "People & Works"]

lex = json.load(open(BACKUP / "data" / "lexicon.json"))
terms = lex["terms"]
qkeys = lex["quarters"]
by_cat = {}
for t in terms:
    by_cat.setdefault(t["category"], []).append(t)
# rank each category by recurrence (most-glossed first), then alphabetical
for c in by_cat:
    by_cat[c].sort(key=lambda t: (-t["edition_count"], t["name"].lower()))
TOP_N = 20
core = [t for t in terms if t["edition_count"] >= 3]


def cat_slug(c):
    return f"lexcat-{lx.slugify(c)}-v2.html"
total_defs = sum(t["edition_count"] for t in terms)
span = f"{qkeys[0].replace('-Q', ' Q')} – {qkeys[-1].replace('-Q', ' Q')}" if qkeys else ""


def clamp(s, n):
    s = " ".join((s or "").split())
    return (s[:n].rsplit(" ", 1)[0] + "…") if len(s) > n else s


def term_href(t):
    return f"lexicon/{t['slug']}.html"


def chips():
    out = ""
    for c in CATEGORY_ORDER:
        if by_cat.get(c):
            out += (f'<a class="lex-chip" href="#cat-{lx.slugify(c)}">{e(c)} '
                    f'<span>{len(by_cat[c])}</span></a>')
    return out


def core_cards():
    out = ""
    for t in core[:48]:
        out += f"""
    <a class="lex-cc" href="{term_href(t)}" data-term="{e(t['name'].lower())}">
      <div class="lex-cc-term">{e(t['name'])}</div>
      <div class="lex-cc-meta">{t['edition_count']} editions · {e(t['category'])}</div>
      <p class="lex-cc-def">{e(clamp(t['definition'], 140))}</p>
      <div class="lex-cc-spark">{lx.sparkline(t['timeline'], t.get('color','accent'), w=130, h=30)}</div>
    </a>"""
    return out


def render_lines(items):
    lines = ""
    for t in items:
        badge = f'<span class="lex-badge">{t["edition_count"]}×</span>' if t["edition_count"] > 1 else ""
        lines += f"""
      <a class="lex-line" href="{term_href(t)}">
        <span class="lex-line-term">{e(t['name'])}{badge}</span>
        <span class="lex-line-def">{e(clamp(t['definition'], 150))}</span>
      </a>"""
    return lines


def category_sections():
    """Index: each category shows its top TOP_N terms + a link to the full page."""
    out = ""
    for c in CATEGORY_ORDER:
        items = by_cat.get(c)
        if not items:
            continue
        shown = items[:TOP_N]
        more = len(items) - len(shown)
        more_link = (f'<a class="lex-seeall" href="{cat_slug(c)}">See all {len(items)} '
                     f'{e(c)} terms &rarr;</a>') if more > 0 else ""
        out += f"""
  <section class="block lex-catsec" id="cat-{lx.slugify(c)}">
    <div class="rule-head"><h2 class="rule-label">{e(c)}</h2>
      <span class="rule-meta">Top {len(shown)} of {len(items)}</span></div>
    <div class="lex-lines">{render_lines(shown)}
    </div>
    {more_link}
  </section>"""
    return out


def render_category_page(c):
    items = by_cat[c]
    body = f"""
<header class="lex-hero">
  <a class="lex-back" href="lexicon-v2.html">&larr; The Lexicon</a>
  <div class="kicker kicker-accent">Lexicon · Category</div>
  <h1 class="lex-h1">{e(c)}</h1>
  <p class="lex-metaline">{len(items)} terms · sorted by how often they're glossed</p>
</header>
<main class="wrap">
  <section class="block">
    <div class="lex-lines">{render_lines(items)}
    </div>
  </section>
</main>"""
    return _page(f"{c} — The Lexicon", body)


LEX_CSS = r"""
.lex-hero{max-width:var(--w);margin:0 auto;padding:50px 28px 6px}
.lex-h1{font-family:var(--display);font-weight:var(--display-weight);font-size:clamp(3rem,8.5vw,6.2rem);line-height:.88;letter-spacing:-.03em;margin:.5rem 0 .7rem}
.lex-lede{font-family:var(--serif);font-size:1.26rem;line-height:1.5;color:var(--ink-muted);max-width:62ch;margin-bottom:.8rem}
.lex-lede em{font-style:italic}
.lex-metaline{font-family:var(--mono);font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:1.5rem}
.lex-search{width:100%;padding:.95rem 1.1rem;font-family:var(--mono);font-size:.82rem;letter-spacing:.02em;color:var(--ink);background:var(--bg);border:2px solid var(--ink);outline:none}
.lex-search::placeholder{color:var(--ink-faint)}
.lex-search:focus{border-color:var(--accent)}
.lex-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.2rem}
.lex-chip{font-family:var(--mono);font-size:.64rem;letter-spacing:.1em;text-transform:uppercase;padding:.5em .75em;border:1px solid var(--rule);color:var(--ink-muted);display:inline-flex;align-items:center;gap:.5em;transition:border-color .15s,color .15s}
.lex-chip span{color:var(--ink-faint)}
.lex-chip:hover{border-color:var(--accent);color:var(--accent)}
.lex-noresults{font-family:var(--mono);font-size:.8rem;color:var(--ink-faint);max-width:var(--w);margin:1.5rem auto 0;padding:0 28px}
/* Core Vocabulary cards */
.lex-core-grid{display:grid;grid-template-columns:1fr 1fr;gap:0;border-top:1px solid var(--rule)}
.lex-cc{display:grid;grid-template-columns:1fr 130px;grid-template-areas:"term spark" "def spark";gap:.2rem 1rem;align-items:center;padding:1.15rem 1.2rem;border-bottom:1px solid var(--rule);border-right:1px solid var(--rule)}
.lex-core-grid .lex-cc:nth-child(odd){border-left:1px solid var(--rule)}
.lex-cc:hover{background:var(--surface)}
.lex-cc-term{grid-area:term;font-family:var(--display);font-weight:var(--display-weight);font-size:1.3rem;line-height:1.05;color:var(--ink)}
.lex-cc:hover .lex-cc-term{color:var(--accent)}
.lex-cc-meta{display:none}
.lex-cc-def{grid-area:def;font-family:var(--serif);font-size:.92rem;line-height:1.45;color:var(--ink-muted)}
.lex-cc-spark{grid-area:spark;align-self:center}
/* category lists */
.lex-catsec{scroll-margin-top:80px}
.lex-lines{display:grid;grid-template-columns:1fr 1fr;gap:0}
.lex-line{display:grid;grid-template-columns:minmax(150px,40%) 1fr;gap:1rem;align-items:baseline;padding:.8rem 1.1rem;border-bottom:1px solid var(--rule);border-right:1px solid var(--rule)}
.lex-lines .lex-line:nth-child(odd){border-left:1px solid var(--rule)}
.lex-line:hover{background:var(--surface)}
.lex-line-term{font-family:var(--display);font-weight:var(--display-weight);font-size:1.12rem;line-height:1.1;color:var(--ink)}
.lex-line:hover .lex-line-term{color:var(--accent)}
.lex-badge{font-family:var(--mono);font-size:.56em;color:var(--accent);vertical-align:super;margin-left:.4em}
.lex-line-def{font-family:var(--serif);font-size:.88rem;line-height:1.4;color:var(--ink-muted)}
.lex-soon{max-width:var(--w);margin:0 auto;padding:10px 28px 60px}
.lex-soon-inner{background:var(--surface-ink);color:oklch(0.92 0.006 70);padding:2rem 2.2rem}
.lex-soon h3{font-family:var(--mono);font-size:.68rem;letter-spacing:.18em;text-transform:uppercase;color:oklch(0.80 0.10 55);margin-bottom:.7rem}
.lex-soon p{font-family:var(--serif);font-size:1.05rem;color:oklch(0.82 0.008 70);max-width:70ch}
.lex-soon strong{color:oklch(0.97 0.006 70)}
/* see-all + back links */
.lex-seeall{display:inline-block;margin-top:1rem;font-family:var(--mono);font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.lex-seeall:hover{color:var(--accent-deep)}
.lex-back{display:inline-block;font-family:var(--mono);font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);margin-bottom:1.2rem}
/* live search results */
.lex-results{max-width:var(--w);margin:0 auto;padding:24px 28px 60px}
.lex-rescount{font-family:var(--mono);font-size:.66rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin:.4rem 0 1rem}
.lex-resgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:0;border-top:1px solid var(--rule)}
.lex-resitem{font-family:var(--display);font-weight:var(--display-weight);font-size:1.05rem;color:var(--ink);padding:.7rem .8rem;border-bottom:1px solid var(--rule);border-right:1px solid var(--rule)}
.lex-resitem:hover{background:var(--surface);color:var(--accent)}
@media(max-width:820px){
  .lex-core-grid{grid-template-columns:1fr}
  .lex-core-grid .lex-cc{border-left:1px solid var(--rule)}
  .lex-lines{grid-template-columns:1fr}
  .lex-lines .lex-line{border-left:1px solid var(--rule);grid-template-columns:1fr;gap:.2rem}
}
"""

SEARCH_JS = r"""
<script>
(function(){
  var q=document.getElementById('lexSearch'); if(!q) return;
  var R=document.getElementById('lexResults'), B=document.getElementById('lexBrowse');
  var A=window.LEX_ALL||[];
  q.addEventListener('input',function(){
    var v=q.value.trim().toLowerCase();
    if(!v){R.hidden=true; B.hidden=false; R.innerHTML=''; return;}
    var hits=A.filter(function(x){return x[0].toLowerCase().indexOf(v)>-1;});
    var h='<div class="lex-rescount">'+hits.length+' term'+(hits.length!=1?'s':'')+' matching "'+v.replace(/[<>&]/g,'')+'"</div><div class="lex-resgrid">';
    hits.slice(0,240).forEach(function(x){h+='<a class="lex-resitem" href="lexicon/'+x[1]+'.html">'+x[0]+'</a>';});
    h+='</div>';
    if(hits.length>240) h+='<div class="lex-rescount">+ '+(hits.length-240)+' more — refine your search</div>';
    R.innerHTML=h; R.hidden=false; B.hidden=true;
  });
})();
</script>
"""


def _page(title, body, extra_head=""):
    css = mh.CSS + LEX_CSS
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=Libre+Caslon+Display&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;1,8..60,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style>{extra_head}
</head><body>
{mh.render_masthead()}
{body}
<footer class="foot">
  <div class="foot-inner">
    <div class="wordmark"><img src="assets/crystal-ball.svg" alt="" class="tw-orb"> Token Wisdom</div>
    <p class="foot-tag">The Newsletter of Record for the Future of Now · Knowware is measured in lifetimes.</p>
  </div>
</footer>
</body></html>"""


def build(out_name="lexicon-v2.html"):
    all_data = json.dumps([[t["name"], t["slug"]] for t in terms], ensure_ascii=False)
    body = f"""
<header class="lex-hero">
  <div class="kicker kicker-accent">The Lexicon</div>
  <h1 class="lex-h1">The Lexicon</h1>
  <p class="lex-lede">The working vocabulary of the future of now — {len(terms):,} terms,
  defined by hand in <em>The Less You Know</em> across {lex['edition_count']} editions.
  Every definition is the newsletter's own; recurring terms trace how the language of the
  field accumulated, week over week.</p>
  <div class="lex-metaline">{total_defs:,} definitions · {len(core)} recurring terms · {span} · 100% authentic humanly chosen</div>
  <input id="lexSearch" class="lex-search" type="search" autocomplete="off" placeholder="Search all {len(terms):,} terms…" aria-label="Search the Lexicon">
  <div class="lex-chips">{chips()}</div>
</header>
<div id="lexResults" class="lex-results" hidden></div>
<div id="lexBrowse">
<main class="wrap">
  <section class="block lex-core-sec">
    <div class="rule-head"><h2 class="rule-label">Core Vocabulary</h2>
      <span class="rule-meta">Recurring in 3+ editions</span></div>
    <div class="lex-core-grid">{core_cards()}
    </div>
  </section>
{category_sections()}
</main>
<div class="lex-soon"><div class="lex-soon-inner">
  <h3>Coming to the Lab</h3>
  <p>The Lexicon is the data layer. Next on the bench, all powered by it:
  <strong>the Constellation</strong> (browse terms as a map of what's glossed together),
  <strong>Ask the Archive</strong> (question three years of writing), and
  <strong>the Zeitgeist Tracker</strong> (what mattered when, across {len(qkeys)} quarters).</p>
</div></div>
</div>
<script>window.LEX_ALL={all_data};</script>
{SEARCH_JS}
"""
    out = DOCS / out_name
    out.write_text(_page("The Lexicon — Token Wisdom", body))
    # per-category full-list pages
    for c in CATEGORY_ORDER:
        if by_cat.get(c):
            (DOCS / cat_slug(c)).write_text(render_category_page(c))
    return out


if __name__ == "__main__":
    o = build("lexicon-v2.html")
    print(f"Wrote {o} + {len([c for c in CATEGORY_ORDER if by_cat.get(c)])} category pages")
    print(f"  {len(terms)} terms · {len(core)} core · top {TOP_N}/category on index")
    print("  preview: http://localhost:8765/lexicon-v2.html")

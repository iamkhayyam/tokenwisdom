#!/usr/bin/env python3
"""
Generate docs/links/index.html — the Token Wisdom Reading Room.

All TNL (The Newest Latest) articles and TWS (Time Well Spent) videos,
organised by week, with the current week's top-5 of each featured at the top.

Run standalone: python generate_links.py
Also called by generate_site.py during full site builds.
"""

import json
from pathlib import Path
from tw_theme import page, BASE_CSS

DOCS   = Path(__file__).parent / "docs"
DATA   = Path(__file__).parent / "data" / "links.json"


# ── CSS specific to the links page ────────────────────────────────────────────

LINKS_CSS = """
/* Reading Room ─ top-5 featured strip */
.rr-featured{padding:2.4rem 0 2rem}
.rr-featured-head{display:flex;align-items:baseline;gap:1rem;border-top:2px solid var(--ink);padding-top:.8rem;margin-bottom:1.6rem}
.rr-featured-label{font-family:var(--mono);font-weight:300;font-size:.64rem;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-muted)}
.rr-featured-title{font-family:var(--display);font-weight:400;font-size:1.5rem;color:var(--ink)}
.rr-week-badge{margin-left:auto;font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}

.rr-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:1rem}
.rr-card{display:block;color:var(--ink);border:1px solid var(--rule);border-radius:4px;overflow:hidden;background:var(--surface);transition:border-color .2s,transform .2s}
.rr-card:hover{border-color:var(--accent);transform:translateY(-2px);color:var(--ink)}
.rr-card-img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:var(--rule)}
.rr-card-img-placeholder{width:100%;aspect-ratio:16/9;background:var(--rule);display:flex;align-items:center;justify-content:center}
.rr-card-body{padding:.75rem .85rem .9rem}
.rr-card-type{font-family:var(--mono);font-weight:300;font-size:.58rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:.4rem}
.rr-card-title{font-family:var(--sans);font-weight:600;font-size:.92rem;line-height:1.3;color:var(--ink);margin-bottom:.4rem;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.rr-card-excerpt{font-family:var(--serif);font-optical-sizing:none;font-variation-settings:"opsz" 17;font-size:.8rem;line-height:1.45;color:var(--ink-muted);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}

/* Archive ─ week accordion rows */
.rr-archive{padding-top:2rem}
.rr-year-head{font-family:var(--display);font-weight:400;font-size:1.9rem;color:var(--ink);border-top:2px solid var(--ink);padding-top:.7rem;margin:2.4rem 0 1rem;letter-spacing:-.01em}
.rr-week{margin-bottom:.5rem}
.rr-week-toggle{width:100%;display:flex;align-items:center;gap:1rem;background:none;border:none;border-top:1px solid var(--rule);padding:.7rem 0;cursor:pointer;text-align:left}
.rr-week-toggle:hover .rr-week-num{color:var(--accent)}
.rr-week-num{font-family:var(--mono);font-weight:300;font-size:.64rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-muted);min-width:5rem}
.rr-week-counts{font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}
.rr-week-caret{margin-left:auto;font-size:.7rem;color:var(--ink-faint);transition:transform .2s}
.rr-week-toggle[aria-expanded=true] .rr-week-caret{transform:rotate(180deg)}
.rr-week-body{display:none;padding:.6rem 0 1rem}
.rr-week-toggle[aria-expanded=true]+.rr-week-body{display:block}
.rr-week-cols{display:grid;grid-template-columns:1fr 1fr;gap:0 2.5rem}
@media(max-width:640px){.rr-week-cols{grid-template-columns:1fr}}
.rr-section-label{font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin:.9rem 0 .5rem;padding-bottom:.35rem;border-bottom:.5px solid var(--rule)}
.rr-list{list-style:none}
.rr-item{display:grid;grid-template-columns:52px 1fr;gap:.75rem;padding:.5rem 0;border-bottom:.5px solid var(--rule);align-items:start}
.rr-item:last-child{border-bottom:none}
.rr-item-thumb{width:52px;height:36px;object-fit:cover;border-radius:2px;display:block;background:var(--rule)}
.rr-item-thumb-ph{width:52px;height:36px;border-radius:2px;background:var(--rule)}
.rr-item-title{font-family:var(--sans);font-weight:500;font-size:.88rem;line-height:1.3;color:var(--ink)}
.rr-item-title:hover{color:var(--accent)}
.rr-item-excerpt{font-family:var(--serif);font-optical-sizing:none;font-variation-settings:"opsz" 17;font-size:.78rem;color:var(--ink-muted);line-height:1.4;margin-top:.2rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

/* Stats bar */
.rr-stats{display:flex;gap:2.5rem;padding:1.2rem 0;border-bottom:1px solid var(--rule);margin-bottom:2rem}
.rr-stat-num{font-family:var(--display);font-weight:400;font-size:1.6rem;color:var(--ink);line-height:1}
.rr-stat-lbl{font-family:var(--mono);font-weight:300;font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-top:.3rem}

@media(max-width:860px){.rr-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:580px){.rr-grid{grid-template-columns:1fr 1fr}.rr-stats{gap:1.5rem}}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def cover_img(item, cls="rr-card-img", ph_cls="rr-card-img-placeholder"):
    if item.get("cover"):
        return f'<img class="{cls}" src="{esc(item["cover"])}" alt="" loading="lazy">'
    return f'<div class="{ph_cls}"></div>'

def thumb(item):
    if item.get("cover"):
        return f'<img class="rr-item-thumb" src="{esc(item["cover"])}" alt="" loading="lazy">'
    return '<div class="rr-item-thumb-ph"></div>'

def card(item, section):
    type_label = "Article" if section == "tnl" else "Video"
    excerpt = esc(item.get("excerpt") or item.get("note") or "")
    return f"""
<a class="rr-card" href="{esc(item['url'])}" target="_blank" rel="noopener">
  {cover_img(item)}
  <div class="rr-card-body">
    <div class="rr-card-type">{type_label}</div>
    <div class="rr-card-title">{esc(item['title'])}</div>
    {'<div class="rr-card-excerpt">' + excerpt + '</div>' if excerpt else ''}
  </div>
</a>"""

def list_item(item):
    excerpt = esc(item.get("excerpt") or item.get("note") or "")
    return f"""
<li class="rr-item">
  {thumb(item)}
  <div>
    <a class="rr-item-title" href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a>
    {'<div class="rr-item-excerpt">' + excerpt + '</div>' if excerpt else ''}
  </div>
</li>"""


# ── Page sections ─────────────────────────────────────────────────────────────

def render_featured(db):
    cw = next((w for w in db["weeks"] if w["year"] == db["current_year"] and w["week"] == db["current_week"]), None)
    if not cw:
        return ""

    week_label = f"2026 · W{cw['week']:02d}"
    tnl5 = cw["tnl"][:5]
    tws5 = cw["tws"][:5]

    tnl_cards = "".join(card(i, "tnl") for i in tnl5)
    tws_cards = "".join(card(i, "tws") for i in tws5)

    return f"""
<section class="rr-featured">
  <div class="rr-featured-head">
    <span class="rr-featured-label">This Week</span>
    <span class="rr-featured-title">The Newest Latest</span>
    <span class="rr-week-badge">{week_label}</span>
  </div>
  <div class="rr-grid">{tnl_cards}</div>

  <div class="rr-featured-head" style="margin-top:2.2rem">
    <span class="rr-featured-label">This Week</span>
    <span class="rr-featured-title">Time Well Spent</span>
    <span class="rr-week-badge">{week_label}</span>
  </div>
  <div class="rr-grid">{tws_cards}</div>
</section>"""


def render_archive(db):
    # Group weeks by year
    from itertools import groupby
    years = {}
    for w in sorted(db["weeks"], key=lambda x: (x["year"], x["week"]), reverse=True):
        y = w["year"]
        if y not in years:
            years[y] = []
        years[y].append(w)

    html = '<section class="rr-archive">'

    for year in sorted(years.keys(), reverse=True):
        html += f'<div class="rr-year-head">{year}</div>'
        for w in years[year]:
            wk = f"W{w['week']:02d}"
            tnl_count = len(w["tnl"])
            tws_count = len(w["tws"])
            wid = f"w{year}-{w['week']:02d}"

            tnl_items = "".join(list_item(i) for i in w["tnl"])
            tws_items = "".join(list_item(i) for i in w["tws"])

            html += f"""
<div class="rr-week">
  <button class="rr-week-toggle" aria-expanded="false" aria-controls="{wid}" onclick="toggle(this)">
    <span class="rr-week-num">{wk}</span>
    <span class="rr-week-counts">{tnl_count} articles · {tws_count} videos</span>
    <span class="rr-week-caret">▾</span>
  </button>
  <div class="rr-week-body" id="{wid}">
    <div class="rr-week-cols">
      <div>
        <div class="rr-section-label">The Newest Latest</div>
        <ul class="rr-list">{tnl_items}</ul>
      </div>
      <div>
        <div class="rr-section-label">Time Well Spent</div>
        <ul class="rr-list">{tws_items}</ul>
      </div>
    </div>
  </div>
</div>"""

    html += "</section>"
    return html


def render_stats(db):
    return f"""
<div class="rr-stats">
  <div><div class="rr-stat-num">{db['total_tnl'] + db['total_tws']:,}</div><div class="rr-stat-lbl">Total links</div></div>
  <div><div class="rr-stat-num">{db['total_tnl']:,}</div><div class="rr-stat-lbl">Articles</div></div>
  <div><div class="rr-stat-num">{db['total_tws']:,}</div><div class="rr-stat-lbl">Videos</div></div>
  <div><div class="rr-stat-num">{db['total_weeks']}</div><div class="rr-stat-lbl">Weeks</div></div>
  <div><div class="rr-stat-num">2</div><div class="rr-stat-lbl">Years</div></div>
</div>"""


TOGGLE_JS = """
<script>
function toggle(btn) {
  var expanded = btn.getAttribute('aria-expanded') === 'true';
  btn.setAttribute('aria-expanded', !expanded);
}
</script>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def build():
    db = json.loads(DATA.read_text())
    out_dir = DOCS / "links"
    out_dir.mkdir(exist_ok=True)

    body = f"""
<style>{LINKS_CSS}</style>
<div class="wrap" style="padding-top:2.5rem;padding-bottom:4rem">
  <div style="border-bottom:2px solid var(--ink);padding-bottom:1.2rem;margin-bottom:1.6rem">
    <div class="kicker kicker-accent" style="margin-bottom:.5rem">Reading Room</div>
    <h1 style="font-family:var(--display);font-weight:400;font-size:clamp(2.4rem,6vw,4rem);line-height:.97;letter-spacing:-.025em;color:var(--ink)">The Stack</h1>
    <p style="font-family:var(--serif);font-optical-sizing:none;font-variation-settings:'opsz' 17;font-size:1.1rem;color:var(--ink-muted);margin-top:.7rem;max-width:52ch">Every article and video from The Newest Latest and Time Well Spent, week by week.</p>
  </div>
  {render_stats(db)}
  {render_featured(db)}
  {render_archive(db)}
</div>
{TOGGLE_JS}"""

    html = page("The Stack — Reading Room", body, prefix="../", active="links")
    (out_dir / "index.html").write_text(html)
    print(f"Wrote {out_dir / 'index.html'}")
    return db


if __name__ == "__main__":
    build()

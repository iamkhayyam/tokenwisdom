#!/usr/bin/env python3
"""
Homepage redesign mockup — "Spectrum bones, Token Wisdom soul".

Standalone, high-fidelity prototype that reads real data and writes a single
self-contained file to docs/home-v2.html for preview. Once the direction is
locked, the structure + CSS port into generate_site.py's render_homepage + CSS.

Design tokens follow DESIGN.md. Run:  python3 mockup_home.py
Preview:  http://localhost:8765/home-v2.html
"""

import json
import re as _re
from pathlib import Path
import generate_site as gs
import lexicon as lx
import tw_theme

BACKUP = Path(__file__).parent
DOCS = BACKUP / "docs"
e = gs.esc


def img(url, w=1400):
    """Localize Ghost-hosted image URLs to local content/images/ paths."""
    return gs.localize_url(url) or url or ""


# ---- data ----
posts, tags, authors, pages = gs.load_data()
for _p in posts:
    if _p.get("feature_image"):
        _p["feature_image"] = gs.localize_url(_p["feature_image"]) or _p["feature_image"]
for _t in tags:
    if _t.get("feature_image"):
        _t["feature_image"] = gs.localize_url(_t["feature_image"]) or _t["feature_image"]
chrono = sorted([p for p in posts if p.get("published_at") and not gs.is_hidden(p)],
                key=lambda p: p["published_at"], reverse=True)
issue_nums = gs.issue_number_map(posts)
essays = [p for p in chrono if not gs.is_newsletter(p)]
editions = [p for p in chrono if gs.is_newsletter(p)]
hero = essays[0]
top_three = essays[1:4]
secondary = essays[4:6]
more = essays[6:12]
latest_ed = editions[0]


def _is_featured(p):
    # Ghost's featured flag, a 'featured' tag, or 'featured' in the description.
    # #unlisted is intentionally NOT excluded — featured posts surface here
    # regardless of listing (the unlisted flag gated other feeds, not this rail).
    if p.get("featured"):
        return True
    if any(t.get("slug", "") == "featured" or (t.get("name", "") or "").strip().lower() == "featured"
           for t in (p.get("tags") or [])):
        return True
    blurb = ((p.get("custom_excerpt") or "") + " " + (p.get("excerpt") or "")).lower()
    return "featured" in blurb


# Curated highlights (chronological). The rail shows the first few; the
# /featured page lists them all.
all_featured = [p for p in chrono if _is_featured(p)]
featured_posts = all_featured[:6]


_WK_RX = _re.compile(r"\bW\s*0?(\d{1,2})\b")  # essays write "W13"; editions write "Week 13"


def _week_of(p, fields=("custom_excerpt", "excerpt", "title", "slug")):
    for f in fields:
        val = p.get(f, "") or ""
        m = gs.WEEK_RX.search(val) or _WK_RX.search(val)
        if m:
            return int(m.group(1))
    return None


# map (year, week) -> newsletter edition, so each essay can link its same-week edition
ed_by_yw = {}
for _ed in editions:
    _wk = _week_of(_ed, ("title", "slug"))
    if _wk:
        ed_by_yw[((_ed.get("published_at") or "")[:4], _wk)] = _ed


def paired_edition(p):
    wk = _week_of(p)
    return ed_by_yw.get(((p.get("published_at") or "")[:4], wk)) if wk else None


def _ep_week(ep):
    t = ep.get("title", "") or ""
    m = gs.WEEK_RX.search(t) or _WK_RX.search(t)
    return int(m.group(1)) if m else None

tag_to_posts = {}
for p in posts:
    if gs.is_hidden(p):
        continue
    for t in p.get("tags", []) or []:
        tag_to_posts.setdefault(t["slug"], []).append(p)
public_tags = [t for t in tags if not (t.get("name", "") or "").startswith("#")
               and t["slug"] not in gs.SECTION_TAGS]
top_tags = sorted(public_tags, key=lambda t: len(tag_to_posts.get(t["slug"], [])), reverse=True)[:12]

lex = json.load(open(BACKUP / "data" / "lexicon.json"))
links_db = json.load(open(BACKUP / "data" / "links.json"))
lex_by_name = {t["name"]: t for t in lex["terms"]}
# Pick 4 terms by edition frequency, rotating by ISO week so they change each build
_lex_pool = sorted(
    [t for t in lex["terms"] if t.get("edition_count", 0) >= 2 and len(t["name"]) > 5 and t.get("definition")],
    key=lambda t: t.get("edition_count", 0), reverse=True
)[:40]
from datetime import datetime as _dt
_offset = _dt.now().isocalendar()[1] % max(len(_lex_pool) - 3, 1)
feature_terms = [t["name"] for t in _lex_pool[_offset:_offset + 4]]

# Podcast — each week ships an A/B pair: •A• is the essay dive, •B• is the edition
# dive. Surface the most recent of each (matched to the featured week when present).
import re as _re
# Read the cached feed deterministically (generate_site refreshes the cache in its
# podcast step before building the homepage). Avoids a flaky import-time network
# fetch that could yield 0 episodes for a given build.
_feed = gs.PODCAST_CACHE.read_bytes() if gs.PODCAST_CACHE.exists() else gs.fetch_podcast_feed()
_ch, _eps = gs.parse_podcast(_feed)


def _find_ep(marker, week=None):
    cand = [ep for ep in _eps if f"•{marker}•" in (ep.get("title", "") or "")]
    if week is not None:
        for ep in cand:
            if _re.search(rf"\bW0?{week}\b", ep.get("title", "") or ""):
                return ep
    return cand[0] if cand else None


_wk = gs.WEEK_RX.search(latest_ed.get("title", "") or "") or gs.WEEK_RX.search(latest_ed.get("slug", "") or "")
_week = int(_wk.group(1)) if _wk else None
essay_ep = _find_ep("A", _week_of(hero))
edition_ep = _find_ep("B", _week)

# (year, week) -> the edition's •B• podcast episode, so an essay can link its
# correlating edition audio on the podcast page.
epB_by_yw = {}
for _ep in _eps:
    if "•B•" not in (_ep.get("title", "") or ""):
        continue
    _w = _ep_week(_ep)
    _y = str(_ep.get("pub_date") or "")[:4]
    if _w and (_y, _w) not in epB_by_yw:
        epB_by_yw[(_y, _w)] = _ep


def paired_audio(p):
    wk = _week_of(p)
    return epB_by_yw.get(((p.get("published_at") or "")[:4], wk)) if wk else None


def ep_title(ep):
    t = ep.get("title", "") or ""
    t = _re.sub(r"^W\d+\s*•[AB]•\s*", "", t)
    t = _re.sub(r"^Pearls of Wisdom\s*[-–—]\s*", "", t)
    t = _re.sub(r"🔮.*$", "", t)
    return _re.sub(r"\s*✨\s*$", "", t).strip() or t


def kicker(p):
    code, label = gs.section_code(p)
    pt = gs.primary_tag(p)
    extra = ""
    for t in (p.get("tags") or []):
        if t.get("slug") not in gs.SECTION_TAGS and not (t.get("name", "") or "").startswith("#"):
            extra = t["name"]
            break
    return f"{label}" + (f" · {extra}" if extra else "")


def meta(p):
    return f"{gs.author_name(p)} · {gs.reading_time(p)} · {gs.fmt_date_short(p.get('published_at'))}"


def href(p):
    return f"posts/{p['slug']}.html"


def pair_link(p):
    ep = paired_audio(p)
    if not ep:
        return ""
    m = gs.EDITION_RX.search(ep.get("title", "") or "")
    label = m.group(0) if m else "the edition"
    anchor = "ep-" + e(ep.get("guid", "") or "")[:24]
    return (f'<a class="pairlink" href="podcast.html#{anchor}">'
            f'&#127911; Hear the {label} &rarr;</a>')


# ---- sections ----

def _render_ed_accordion(all_eds, all_eps):
    items = ""
    for i, (p, ep) in enumerate(zip(all_eds, all_eps)):
        issue_str = e(gs.issue_code_string(p, issue_nums.get(p["slug"], 0)))
        ed_title = e(gs.edition_meta(p) or gs.clean_title(p))
        feat_img = img(p.get("feature_image"))
        player_html = render_player(ep, "The Edition", href(p), rail=True) if ep else ""
        expanded = "true" if i == 0 else "false"
        body_hidden = "" if i == 0 else " hidden"
        items += f"""
<div class="ed-item">
  <button class="ed-row" aria-expanded="{expanded}" onclick="edToggle(this)">
    <span class="ed-row-title">{ed_title}</span>
    <span class="ed-row-caret">▾</span>
  </button>
  <div class="ed-body"{body_hidden}>
    <a class="edition-feature" href="{href(p)}">
      <div class="ef-figure">
        <img src="{e(feat_img)}" alt="{e(p.get('title'))}" loading="lazy">
        <span class="figure-tag">Newsletter</span>
      </div>
      <div class="kicker kicker-accent">{issue_str}</div>
      <h2 class="edition-title">{ed_title}</h2>
      <p class="edition-dek">{gs.excerpt(p, 180)}</p>
      <span class="readlink">Read the edition &rarr;</span>
    </a>
    {player_html}
  </div>
</div>"""
    return items


def render_hero():
    wk = gs.edition_meta(latest_ed) or "This Week"
    return f"""
<section class="thisweek-head">
  <span class="tw-eyebrow">This Week</span>
  <span class="tw-line"></span>
  <span class="tw-meta">{e(wk)} · The essay &amp; the edition, like clockwork</span>
</section>
<section class="lead">
  <div class="lead-col">
  <a class="lead-main" href="{href(hero)}">
    <div class="lead-figure"><img src="{e(img(hero.get('feature_image')))}" alt="{e(hero.get('title'))}" loading="eager">
      <span class="figure-tag">Essay</span></div>
    <div class="lead-body">
      <div class="kicker kicker-accent">{e(kicker(hero))}</div>
      <h1 class="lead-title">{e(hero.get('title'))}</h1>
      <p class="lead-dek">{gs.excerpt(hero, 240)}</p>
      <div class="meta">{e(meta(hero))}</div>
    </div>
  </a>
  {pair_link(hero)}
  </div>
  <aside class="lead-side">
    <div class="side-list">
      {_render_ed_accordion(
          editions[0:5],
          [edition_ep] + [epB_by_yw.get(((p.get("published_at") or "")[:4], _week_of(p))) for p in editions[1:5]]
      )}
    </div>
  </aside>
</section>"""


def render_player(ep, tag, link, rail=False):
    if not ep:
        return ""
    dur = e(ep.get("duration") or "")
    if rail:
        return f"""
    <div class="player player-rail" data-src="{e(ep.get('audio_url'))}">
      <div class="pkicker"><span class="pk-tag">{e(tag)}</span> · NotebookLM · {dur}</div>
      <a class="ptitle" href="{link}">{e(ep_title(ep))}</a>
      <div class="prow">
        <button class="pp" aria-label="Play"><span class="pp-icon"></span></button>
        <div class="ptrack"><div class="pfill"></div><div class="pknob"></div></div>
        <span class="ptime"><span class="pcur">0:00</span> / {dur}</span>
      </div>
    </div>"""
    return f"""
    <div class="player" data-src="{e(ep.get('audio_url'))}">
      <button class="pp" aria-label="Play">
        <span class="pp-icon"></span>
      </button>
      <div class="pbody">
        <div class="pkicker"><span class="pk-tag">{e(tag)}</span> · NotebookLM deep dive · {dur}</div>
        <a class="ptitle" href="{link}">{e(ep_title(ep))}</a>
        <div class="prow">
          <div class="ptrack"><div class="pfill"></div><div class="pknob"></div></div>
          <span class="ptime"><span class="pcur">0:00</span> / {dur}</span>
        </div>
      </div>
    </div>"""


def render_listen():
    player = render_player(essay_ep, "The Essay", href(hero))
    if not player.strip():
        return ""
    return f"""
<section class="block listen-week">
  <div class="rule-head"><h2 class="rule-label">The Essay, Aloud</h2>
    <a class="rule-meta linky" href="podcast.html">All episodes &rarr;</a></div>
  <div class="players">{player}
  </div>
</section>"""


def _story_card(p):
    ep = paired_audio(p)
    ed_post = paired_edition(p)
    audio = (render_player(ep, "Paired edition",
                           href(ed_post) if ed_post else "podcast.html", rail=True)
             if ep else pair_link(p))
    return f"""
    <div class="story-wrap">
    <a class="story" href="{href(p)}">
      <div class="story-figure"><img src="{e(img(p.get('feature_image')))}" alt="{e(p.get('title'))}" loading="lazy"></div>
      <div class="kicker kicker-accent">{e(kicker(p))}</div>
      <h3 class="story-title">{e(p.get('title'))}</h3>
      <p class="story-dek">{gs.excerpt(p, 150)}</p>
      <div class="meta">{e(meta(p))}</div>
    </a>
    {audio}
    </div>"""


def render_recent():
    top_cards = "".join(_story_card(p) for p in top_three)
    cards = "".join(_story_card(p) for p in secondary)
    rows = ""
    for p in more:
        rows += f"""
      <a class="list-row" href="{href(p)}">
        <span class="list-kicker">{e(gs.section_code(p)[1])}</span>
        <span class="list-title">{e(p.get('title'))}</span>
        <span class="list-meta">{e(gs.reading_time(p))} · {e(gs.fmt_date_short(p.get('published_at')))}</span>
      </a>"""
    return f"""
<section class="block">
  <div class="rule-head"><h2 class="rule-label">A Closer Look</h2><span class="rule-meta">Essays &amp; OP-EDs</span></div>
  <div class="top-three-cards">{top_cards}
  </div>
  <div class="recent">
    <div class="recent-cards">{cards}
    </div>
    <div class="recent-list">
      <div class="kicker">More to read</div>{rows}
    </div>
  </div>
</section>"""


def _feat_card(p):
    return f"""
    <a class="feat-card" href="{href(p)}">
      <div class="feat-fig"><img src="{e(img(p.get('feature_image')))}" alt="{e(p.get('title'))}" loading="lazy"></div>
      <div class="feat-body">
        <div class="feat-kicker">{e(kicker(p))}</div>
        <h3 class="feat-title">{e(p.get('title'))}</h3>
        <p class="feat-dek">{gs.excerpt(p, 130)}</p>
        <div class="feat-meta">{e(meta(p))}</div>
      </div>
    </a>"""


def render_featured():
    if not featured_posts:
        return ""
    cards = "".join(_feat_card(p) for p in featured_posts)
    if len(all_featured) > len(featured_posts):
        meta_html = f'<a class="rule-meta linky" href="featured.html">All {len(all_featured)} featured &rarr;</a>'
    else:
        meta_html = '<span class="rule-meta">Editor&rsquo;s picks</span>'
    return f"""
<section class="block">
  <div class="rule-head"><h2 class="rule-label">Featured</h2>{meta_html}</div>
  <div class="feat-grid">{cards}
  </div>
</section>"""


def render_topics():
    cards = ""
    for t in top_tags[:8]:
        n = len(tag_to_posts.get(t["slug"], []))
        fig = t.get("feature_image") or ""
        figure = f'<img src="{e(fig)}" alt="" loading="lazy">' if fig else ""
        cards += f"""
    <a class="topic-card" href="tags/{t['slug']}.html">
      <div class="tc-figure">{figure}<div class="tc-bar"><span class="tc-count">{n}</span><span class="tc-name">{e(t['name'])}</span></div></div>
    </a>"""
    return f"""
<section class="block">
  <div class="rule-head"><h2 class="rule-label">Browse by Idea</h2>
    <a class="rule-meta linky" href="tags/index.html">All {len(public_tags)} topics &rarr;</a></div>
  <div class="topic-grid">{cards}
  </div>
</section>"""


def render_stack():
    cw = next((w for w in links_db["weeks"]
               if w["year"] == links_db["current_year"] and w["week"] == links_db["current_week"]), None)
    if not cw:
        return ""

    week_label = f"{cw['year']} · W{cw['week']:02d}"

    def card(item, label):
        cover = (f'<img class="stack-card-img" src="{e(item["cover"])}" alt="" loading="lazy">'
                 if item.get("cover") else '<div class="stack-card-ph"></div>')
        excerpt = e((item.get("excerpt") or item.get("note") or "")[:160])
        return f"""<a class="stack-card" href="{e(item['url'])}" target="_blank" rel="noopener">
  {cover}
  <div class="stack-card-body">
    <div class="stack-card-type">{label}</div>
    <div class="stack-card-title">{e(item['title'])}</div>
    {'<div class="stack-card-excerpt">' + excerpt + '</div>' if excerpt else ''}
  </div>
</a>"""

    tnl_cards = "".join(card(i, "Article") for i in cw["tnl"][:5])
    tws_cards = "".join(card(i, "Video")   for i in cw["tws"][:5])

    return f"""
<section class="block block-stack">
  <div class="rule-head">
    <h2 class="rule-label">This Week</h2>
    <span class="rule-meta">{week_label}</span>
    <a class="rule-meta linky" href="links/index.html" style="margin-left:auto">Full reading room &rarr;</a>
  </div>
  <div class="stack-row-label">The Newest Latest</div>
  <div class="stack-grid">{tnl_cards}</div>
  <div class="stack-row-label" style="margin-top:1.4rem">Time Well Spent</div>
  <div class="stack-grid">{tws_cards}</div>
</section>"""


def render_lexicon():
    cards = ""
    for n in feature_terms:
        t = lex_by_name[n]
        spark = lx.sparkline(t["timeline"], t.get("color", "accent"), w=160, h=34)
        defn = (t["definition"] or "")[:120]
        cards += f"""
    <a class="lexcard" href="lexicon/{t['slug']}.html">
      <div class="lexcard-term">{e(t['name'])}</div>
      <div class="lexcard-cat">{e(t['category'])} · {t['edition_count']} ed.</div>
      <p class="lexcard-def">{e(defn)}</p>
      <div class="lexcard-spark">{spark}</div>
    </a>"""
    return f"""
<section class="block block-lex">
  <div class="rule-head"><h2 class="rule-label">From the Lexicon</h2>
    <a class="rule-meta linky" href="lexicon/index.html">{len(lex['terms']):,} terms &rarr;</a></div>
  <p class="lex-intro">The working vocabulary of the future of now, defined by hand across {lex['edition_count']} editions, week over week.</p>
  <div class="lexcards">{cards}
  </div>
</section>"""


def render_subscribe():
    return f"""
<section class="subscribe">
  <div class="sub-inner">
    <div class="kicker kicker-on-dark">The Newsletter of Record for the Future of Now</div>
    <h2 class="sub-title">One signal per week, from three years of looking ahead.</h2>
    <p class="sub-dek">100% authentic, humanly chosen. No feed, no filler, no algorithm. Just the pearls.</p>
    <a class="sub-cta" href="{gs.GHOST_URL}/subscribe">Subscribe &rarr;</a>
  </div>
</section>"""


def render_masthead():
    import datetime as _dt
    today = "SAT · JUN 13, 2026"
    ed_no = gs.issue_nums.get(latest_ed['slug'], 153) if hasattr(gs, 'issue_nums') else 153
    return f"""
<div class="nameplate">
  <div class="np-inner">
    <div class="np-left">The Newsletter of Record<br>for the Future of Now</div>
    <a class="np-mark" href="index.html">Token&nbsp;Wisdom</a>
    <div class="np-right">No. 153<br>{today}</div>
  </div>
</div>
<header class="mast">
  <div class="mast-inner">
    <a class="mast-mark" href="index.html" aria-label="Token Wisdom — home"><img src="assets/crystal-ball.svg" alt="" class="tw-orb"></a>
    <nav class="mast-nav" id="mast-nav">
      {''.join(f'<a href="{href}">{label}</a>' for _, label, href in tw_theme.NAV)}
      <a class="mast-sub" href="{gs.GHOST_URL}/subscribe">Subscribe</a>
    </nav>
    <button class="mast-toggle" data-nav-toggle aria-label="Open menu" aria-expanded="false" aria-controls="nav-takeover">
      <span class="ham"><span></span><span></span><span></span></span>
      <span class="mtxt">Menu</span>
    </button>
  </div>
</header>
{tw_theme.nav_overlay("")}"""


CSS = r"""
@font-face{font-family:'FauxCRA';src:url('assets/fonts/FauxCRA-Light.otf') format('opentype');font-weight:300;font-style:normal}
@font-face{font-family:'FauxCRA';src:url('assets/fonts/FauxCRA-Regular.otf') format('opentype');font-weight:400;font-style:normal}
@font-face{font-family:'FauxCRA';src:url('assets/fonts/FauxCRA-Bold.otf') format('opentype');font-weight:700;font-style:normal}
@font-face{font-family:'FauxCRA Mono';src:url('assets/fonts/FauxCRA-Monospaced.otf') format('opentype');font-weight:400;font-style:normal}

:root{
  --bg: oklch(0.992 0.004 70);
  --surface: oklch(0.972 0.005 70);
  --surface-ink: oklch(0.205 0.012 65);
  --ink: oklch(0.235 0.012 60);
  --ink-muted: oklch(0.505 0.012 60);
  --ink-faint: oklch(0.66 0.010 60);
  --rule: oklch(0.905 0.006 70);
  --rule-strong: oklch(0.235 0.012 60);
  --accent: oklch(0.585 0.155 47);
  --accent-deep: oklch(0.475 0.140 44);
  --accent-wash: oklch(0.95 0.030 60);
  --teal: oklch(0.520 0.070 195);
  --gold: oklch(0.700 0.095 85);
  --sans:'Archivo',-apple-system,BlinkMacSystemFont,sans-serif;
  --display:'Libre Caslon Display',Georgia,serif;
  --display-weight:400;
  --serif:'Source Serif 4',Georgia,serif;
  --mono:'FauxCRA Mono','FauxCRA',ui-monospace,monospace;
  --w:1220px;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:17px;line-height:1.6;overflow-x:hidden}
img{max-width:100%;height:auto;display:block}
a{color:inherit;text-decoration:none}
.wrap{max-width:var(--w);margin:0 auto;padding:0 28px}

/* kicker / meta */
.kicker{font-family:var(--mono);font-weight:300;font-size:.66rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-muted)}
.kicker-accent{color:var(--accent)}
.kicker-on-dark{color:oklch(0.78 0.10 55)}
.meta{font-family:var(--mono);font-weight:300;font-size:.64rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint)}

/* nameplate — the signature front-page moment */
.nameplate{border-bottom:1px solid var(--ink);background:var(--bg)}
.np-inner{max-width:var(--w);margin:0 auto;padding:20px 28px 22px;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:18px}
.np-left{font-family:'FauxCRA',var(--mono);font-weight:400;font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-muted);line-height:1.5;justify-self:start}
.np-right{font-family:'FauxCRA',var(--mono);font-weight:400;font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-muted);line-height:1.5;text-align:right;justify-self:end}
.np-mark{font-family:var(--display);font-weight:var(--display-weight);font-size:clamp(2.4rem,6.8vw,4.7rem);letter-spacing:-.025em;color:var(--ink);white-space:nowrap;line-height:.88}
/* masthead nav */
.mast{position:sticky;top:0;z-index:50;background:color-mix(in oklch,var(--bg) 90%,transparent);backdrop-filter:blur(8px);border-bottom:2px solid var(--ink)}
.mast-inner{position:relative;max-width:var(--w);margin:0 auto;padding:11px 28px;display:flex;align-items:center;gap:24px}
.mast-mark{display:inline-flex;align-items:center}
.tw-orb{height:30px;width:auto;display:block}
.foot .tw-orb{height:26px;vertical-align:-.45em;display:inline-block;margin-right:.15em}
/* Inline text nav — visible on desktop, swapped for the menu button on mobile */
.mast-nav{display:flex;align-items:center;flex:1;gap:16px;margin-left:6px;flex-wrap:wrap}
.mast-nav a:not(.mast-sub){font-family:'FauxCRA',var(--mono);font-weight:700;font-size:.76rem;letter-spacing:.10em;text-transform:uppercase;color:var(--ink-muted);padding-top:4px;padding-bottom:2px;border-bottom:2px solid transparent;transition:color .15s}
.mast-nav a:not(.mast-sub):hover{color:var(--ink)}
.mast-nav a.is-active{color:var(--accent);border-color:var(--accent)}
.mast-sub{margin-left:auto;font-family:'FauxCRA',var(--mono);font-weight:700;font-size:.68rem;letter-spacing:.10em;text-transform:uppercase;background:var(--accent);color:oklch(0.99 0.004 70);padding:.6em 1.2em;transition:background .15s}
.mast-sub:hover{background:var(--accent-deep)}
/* Menu button — opens the full-page takeover on mobile only */
.mast-toggle{display:none;margin-left:auto;align-items:center;gap:.6em;height:42px;padding:0 16px;background:transparent;border:none;cursor:pointer;color:var(--ink);-webkit-tap-highlight-color:transparent;transition:color .2s}
.mast-toggle:hover{color:var(--accent)}
.mast-toggle .ham{display:inline-flex;flex-direction:column;justify-content:center;gap:4px;width:18px;height:14px}
.mast-toggle .ham span{display:block;height:2px;width:100%;background:currentColor}
.mast-toggle:hover .ham span{animation:tw-ham-ripple .45s ease}
.mast-toggle:hover .ham span:nth-child(2){animation-delay:.07s}
.mast-toggle:hover .ham span:nth-child(3){animation-delay:.14s}
@keyframes tw-ham-ripple{0%{transform:translateX(0)}45%{transform:translateX(4px)}100%{transform:translateX(0)}}
@media(prefers-reduced-motion:reduce){.mast-toggle:hover .ham span{animation:none}}
.mast-toggle .mtxt{font-family:'FauxCRA',var(--mono);font-weight:700;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase}

/* lead */
.lead{display:grid;grid-template-columns:1.7fr 1fr;gap:56px;padding:56px 0 12px;align-items:start}
.lead-figure{aspect-ratio:3/2;overflow:hidden;background:var(--surface);margin-bottom:26px}
.lead-figure img{width:100%;height:100%;object-fit:cover;transition:transform .6s cubic-bezier(.2,.8,.2,1)}
.lead-main:hover .lead-figure img{transform:scale(1.04)}
.lead-title{font-family:var(--display);font-weight:var(--display-weight);font-size:clamp(2.6rem,5.6vw,5.2rem);line-height:.93;letter-spacing:-.035em;margin:.7rem 0 .9rem;text-wrap:balance}
.lead-main:hover .lead-title{color:oklch(0.34 0.07 45)}
:where(.lead-dek,.edition-dek,.story-dek,.lexcard-def,.lex-intro,.sub-dek){font-optical-sizing:none;font-variation-settings:"opsz" 17}
.lead-dek{font-family:var(--serif);font-size:1.22rem;line-height:1.5;color:var(--ink-muted);max-width:48ch;margin-bottom:1rem}
.lead-side{align-self:stretch}
.rail-head{border-top:2px solid var(--rule-strong);padding-top:.7rem;margin-bottom:1.1rem}
/* this week's edition — image-led feature that balances the essay column */
.edition-feature{display:block;margin-bottom:18px}
.ef-figure{position:relative;aspect-ratio:4/3;overflow:hidden;background:var(--surface);margin-bottom:1rem}
.ef-figure img{width:100%;height:100%;object-fit:cover;transition:transform .6s cubic-bezier(.2,.8,.2,1)}
.edition-feature:hover .ef-figure img{transform:scale(1.04)}
.edition-feature:hover .edition-title{color:var(--accent-deep)}
.edition-title{font-family:var(--sans);font-weight:700;font-size:1.6rem;line-height:1.08;letter-spacing:-.02em;margin:.5rem 0 .5rem;color:var(--ink)}
.edition-dek{font-family:var(--serif);font-size:.98rem;line-height:1.45;color:var(--ink-muted);margin-bottom:.9rem}
.readlink{font-family:var(--mono);font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.side-list{display:flex;flex-direction:column}
.side-row{padding:.85rem 0;border-top:1px solid var(--rule);transition:color .15s}
.side-row:hover{color:var(--accent)}
.side-kicker{display:block;font-family:var(--mono);font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:.25rem}
.side-title{font-family:var(--sans);font-weight:600;font-size:1.02rem;line-height:1.25}

/* edition accordion */
.ed-item{border-top:1px solid var(--rule)}
.ed-row{display:flex;align-items:center;width:100%;background:none;border:none;padding:.72rem 0;cursor:pointer;text-align:left;gap:.5rem}
.ed-row-title{font-family:var(--sans);font-weight:600;font-size:.96rem;line-height:1.2;color:var(--ink-muted);flex:1;transition:color .15s}
.ed-row:hover .ed-row-title,.ed-row[aria-expanded=true] .ed-row-title{color:var(--ink)}
.ed-row-caret{font-size:.65rem;color:var(--ink-faint);transition:transform .2s;flex-shrink:0}
.ed-row[aria-expanded=true] .ed-row-caret{transform:rotate(180deg)}
.ed-body{padding-bottom:1rem}
.ed-body[hidden]{display:none}

/* section rule head */
.block{padding:46px 0}
.rule-head{display:flex;align-items:baseline;gap:1rem;border-top:3px solid var(--rule-strong);padding-top:.9rem;margin-bottom:2rem}
.rule-label{font-family:var(--display);font-weight:var(--display-weight);font-size:clamp(1.5rem,2.6vw,2.1rem);letter-spacing:-.02em}
.rule-meta{font-family:var(--mono);font-size:.66rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);margin-left:auto}
.rule-meta.linky{color:var(--accent)}

/* recent */
.top-three-cards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:32px;margin-bottom:44px}
.recent{display:grid;grid-template-columns:1.8fr 1fr;gap:44px}
.recent-cards{display:grid;grid-template-columns:1fr 1fr;gap:32px}
.lead-col,.story-wrap{min-width:0;display:flex;flex-direction:column}
.story-wrap .player-rail{margin-top:auto;padding-top:.9rem;margin-bottom:0}
.pairlink{font-family:var(--mono);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);align-self:flex-start;margin-top:.7rem;border-bottom:1px solid transparent;transition:border-color .15s}
.pairlink:hover{border-color:var(--accent)}
.story-figure{aspect-ratio:16/10;overflow:hidden;background:var(--surface);margin-bottom:14px}
.story-figure img{width:100%;height:100%;object-fit:cover;transition:transform .5s cubic-bezier(.2,.8,.2,1)}
.story:hover .story-figure img{transform:scale(1.03)}
.story-title{font-family:var(--display);font-weight:var(--display-weight);font-size:1.5rem;line-height:1.08;letter-spacing:-.01em;margin:.5rem 0 .5rem}
.story:hover .story-title{color:var(--accent-deep)}
.story-dek{font-family:var(--serif);font-size:1rem;line-height:1.45;color:var(--ink-muted);margin-bottom:.7rem}
.recent-list{display:flex;flex-direction:column}
.recent-list .kicker{margin-bottom:.4rem}
.list-row{display:flex;flex-direction:column;gap:.25rem;padding:.95rem 0;border-top:1px solid var(--rule);transition:color .15s}
.list-row:first-of-type{border-top:1px solid var(--rule-strong)}
.list-row:hover{color:var(--accent)}
.list-kicker{font-family:var(--mono);font-size:.56rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint)}
.list-title{font-family:var(--sans);font-weight:600;font-size:1.05rem;line-height:1.2}
.list-meta{font-family:var(--mono);font-size:.58rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint)}

/* topics */
.topic-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:0}
.topic-card{display:block}
.tc-figure{position:relative;aspect-ratio:16/10;overflow:hidden;background:var(--surface)}
.tc-figure img{width:100%;height:100%;object-fit:cover;transition:transform .55s cubic-bezier(.2,.8,.2,1),filter .4s ease}
.tc-figure img{filter:grayscale(1) contrast(1.1) brightness(1.15)}
.tc-figure::before{
  content:'';
  position:absolute;inset:0;z-index:1;pointer-events:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='4' height='4' fill='%23fff'/%3E%3Crect x='0' y='0' width='1' height='1' fill='%23000'/%3E%3Crect x='2' y='0' width='1' height='1' fill='%23000'/%3E%3Crect x='1' y='1' width='1' height='1' fill='%23000' opacity='.45'/%3E%3Crect x='3' y='1' width='1' height='1' fill='%23000' opacity='.45'/%3E%3Crect x='0' y='2' width='1' height='1' fill='%23000'/%3E%3Crect x='2' y='2' width='1' height='1' fill='%23000'/%3E%3Crect x='1' y='3' width='1' height='1' fill='%23000' opacity='.45'/%3E%3Crect x='3' y='3' width='1' height='1' fill='%23000' opacity='.45'/%3E%3C/svg%3E");
  background-size:6px 6px;
  mix-blend-mode:multiply;
  opacity:.35;transition:opacity .4s ease}
.topic-card:hover .tc-figure img{transform:scale(1.06);filter:grayscale(0) contrast(1) brightness(1)}
.topic-card:hover .tc-figure::before{opacity:0}
.tc-bar{position:absolute;bottom:0;left:0;right:0;z-index:2;display:flex;align-items:baseline;gap:.55em;background:oklch(0.235 0.012 60 / 20%);padding:.45em .65em}
.tc-count{font-family:var(--mono);font-weight:300;font-size:.58rem;letter-spacing:.08em;color:#fff;opacity:.6;flex-shrink:0}
.tc-name{font-family:var(--mono);font-weight:300;font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:820px){.topic-grid{grid-template-columns:1fr 1fr}}

/* stack — this week's top 5 TNL + TWS */
.block-stack{padding:2.4rem 0 2rem}
.stack-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:.85rem;margin-top:1rem}
.stack-card{display:block;color:var(--ink);border:1px solid var(--rule);border-radius:4px;overflow:hidden;background:var(--surface);transition:border-color .2s,transform .2s}
.stack-card:hover{border-color:var(--accent);transform:translateY(-2px);color:var(--ink)}
.stack-card-img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:var(--rule)}
.stack-card-ph{width:100%;aspect-ratio:16/9;background:var(--rule)}
.stack-card-body{padding:.7rem .8rem .85rem}
.stack-card-type{font-family:var(--mono);font-weight:300;font-size:.57rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:.35rem}
.stack-card-title{font-family:var(--sans);font-weight:600;font-size:.88rem;line-height:1.3;color:var(--ink);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.stack-card-excerpt{font-family:var(--serif);font-optical-sizing:none;font-variation-settings:"opsz" 17;font-size:.78rem;line-height:1.4;color:var(--ink-muted);margin-top:.3rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.stack-row-label{font-family:var(--mono);font-weight:300;font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin:.2rem 0 .15rem}

/* lexicon strip */
.block-lex{background:var(--surface);margin:0 -100vw;padding-left:100vw;padding-right:100vw}
.block-lex>.rule-head,.block-lex>.lex-intro,.block-lex>.lexcards{max-width:var(--w);margin-left:auto;margin-right:auto}
.lex-intro{font-family:var(--serif);font-size:1.1rem;color:var(--ink-muted);max-width:60ch;margin:-.6rem 0 1.6rem}
.lexcards{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid var(--rule)}
.lexcard{padding:1.3rem 1.3rem 1.4rem;border-right:1px solid var(--rule);border-bottom:1px solid var(--rule);transition:background .15s}
.lexcard:nth-child(4n){border-right:none}
.lexcard:hover{background:var(--bg)}
.lexcard-term{font-family:var(--display);font-weight:var(--display-weight);font-size:1.3rem;line-height:1.08;letter-spacing:-.01em}
.lexcard:hover .lexcard-term{color:var(--accent)}
.lexcard-cat{font-family:var(--mono);font-size:.56rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin:.35rem 0 .6rem}
.lexcard-def{font-family:var(--serif);font-size:.9rem;line-height:1.45;color:var(--ink-muted);margin-bottom:1rem;min-height:3.8em}
.lexcard-spark{opacity:.9}
.spark{display:block;width:100%;height:auto}

/* featured — curated picks, 3-up framed cards before Browse by Idea */
.feat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.4rem}
.feat-card{display:flex;flex-direction:column;border:1px solid var(--rule);border-radius:6px;overflow:hidden;background:var(--surface);color:var(--ink);transition:border-color .2s ease,transform .2s ease}
.feat-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.feat-fig{aspect-ratio:16/9;overflow:hidden;background:var(--surface)}
.feat-fig img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .5s cubic-bezier(.2,.8,.2,1)}
.feat-card:hover .feat-fig img{transform:scale(1.04)}
.feat-body{display:flex;flex-direction:column;gap:.45rem;padding:1rem 1.15rem 1.2rem}
.feat-kicker{font-family:var(--mono);font-size:.6rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}
.feat-title{font-family:var(--display);font-weight:var(--display-weight);font-size:1.3rem;line-height:1.08;letter-spacing:-.01em;color:var(--ink);transition:color .15s ease}
.feat-card:hover .feat-title{color:var(--accent)}
.feat-dek{font-family:var(--serif);font-size:.9rem;line-height:1.45;color:var(--ink-muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.feat-meta{font-family:var(--mono);font-size:.6rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint);margin-top:auto;padding-top:.3rem}
@media(max-width:820px){.feat-grid{grid-template-columns:1fr 1fr}}
@media(max-width:820px){.top-three-cards{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.feat-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.feat-card,.feat-fig img{transition:none}.feat-card:hover{transform:none}.feat-card:hover .feat-fig img{transform:none}}

/* subscribe — the Fortune Brand crystal ball glowing in the background */
.subscribe{
  margin-top:56px;
  color:oklch(0.95 0.02 65);
  background-color:oklch(0.195 0.055 31);
  background-image:
    linear-gradient(90deg, oklch(0.185 0.055 31) 0%, oklch(0.185 0.055 31 / .95) 40%, oklch(0.185 0.055 31 / .25) 68%, transparent 90%),
    url(assets/fortune_teller.gif);
  background-repeat:no-repeat,no-repeat;
  background-position:center, right -80px center;
  background-size:cover,contain;
}
.sub-inner{max-width:var(--w);margin:0 auto;padding:94px 28px;position:relative}
.sub-title{font-family:var(--display);font-weight:var(--display-weight);font-size:clamp(2.1rem,4.2vw,3.4rem);line-height:1.0;letter-spacing:-.02em;margin:.8rem 0 .7rem;max-width:16ch;color:oklch(0.97 0.02 72)}
.sub-dek{font-family:var(--serif);font-size:1.18rem;color:oklch(0.84 0.02 66);max-width:46ch;margin-bottom:1.8rem}
.sub-cta{display:inline-block;font-family:var(--mono);font-size:.76rem;letter-spacing:.1em;text-transform:uppercase;background:var(--accent);color:oklch(0.99 0.004 70);padding:.95em 1.7em;transition:background .15s,transform .15s}
.sub-cta:hover{background:oklch(0.66 0.16 50);transform:translateX(4px)}
.kicker-on-dark{color:oklch(0.80 0.11 62)}

/* footer */
.foot{border-top:1px solid var(--rule);background:var(--bg)}
.foot-inner{max-width:var(--w);margin:0 auto;padding:40px 28px}
.foot .wordmark{font-size:1.05rem;margin-bottom:.5rem}
.foot-tag{font-family:var(--serif);color:var(--ink-muted);margin-bottom:.4rem}
.foot-meta{font-family:var(--mono);font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint)}

/* this-week pair header */
.thisweek-head{display:flex;align-items:center;gap:1.1rem;max-width:var(--w);margin:0 auto;padding:46px 28px 0}
.tw-eyebrow{font-family:var(--mono);font-weight:500;font-size:.82rem;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
.tw-line{flex:1;height:2px;background:var(--rule-strong)}
.tw-meta{font-family:var(--mono);font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
.lead{padding-top:26px}
.lead-figure{position:relative}
.figure-tag{position:absolute;top:0;left:0;background:var(--ink);color:var(--bg);font-family:var(--mono);font-size:.58rem;letter-spacing:.14em;text-transform:uppercase;padding:.45em .75em}
/* podcast embed */
.listen{background:var(--surface-ink);padding:18px 20px 20px;margin-bottom:18px}
.listen .kicker{color:oklch(0.80 0.10 55)}
.listen-title{font-family:var(--sans);font-weight:700;font-size:1.08rem;line-height:1.18;margin:.45rem 0 .75rem;color:oklch(0.96 0.006 70)}
.listen-audio{width:100%;height:36px;margin-bottom:.55rem}
.listen-meta{font-family:var(--mono);font-size:.55rem;letter-spacing:.05em;text-transform:uppercase;color:oklch(0.72 0.008 70)}
/* full-width audio players (this week in audio) */
.players{display:flex;flex-direction:column}
.player{display:flex;align-items:center;gap:1.3rem;padding:1.5rem 0;border-top:1px solid var(--rule)}
.player:first-child{border-top:none}
.pp{flex-shrink:0;width:54px;height:54px;border-radius:50%;background:var(--ink);color:var(--bg);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s,transform .15s}
.pp:hover{background:var(--accent);transform:scale(1.05)}
.pp-icon{width:0;height:0;border-left:14px solid currentColor;border-top:9px solid transparent;border-bottom:9px solid transparent;margin-left:4px}
.player.playing .pp-icon{width:14px;height:15px;border:none;margin:0;background:linear-gradient(to right,currentColor 0 4px,transparent 4px 10px,currentColor 10px 14px)}
.pbody{flex:1;min-width:0}
.pkicker{font-family:var(--mono);font-size:.6rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint)}
.pk-tag{color:var(--accent)}
.ptitle{display:block;font-family:var(--sans);font-weight:700;font-size:clamp(1.1rem,1.8vw,1.4rem);line-height:1.18;letter-spacing:-.01em;margin:.25rem 0 .7rem;color:var(--ink)}
.ptitle:hover{color:var(--accent)}
.prow{display:flex;align-items:center;gap:1.1rem}
.ptrack{position:relative;flex:1;height:6px;background:var(--rule);cursor:pointer}
.pfill{position:absolute;left:0;top:0;height:100%;width:0;background:var(--accent)}
.pknob{position:absolute;top:50%;left:0;width:13px;height:13px;border-radius:50%;background:var(--accent);transform:translate(-50%,-50%);display:none;box-shadow:0 0 0 3px var(--bg)}
.player.playing .pknob,.ptrack:hover .pknob{display:block}
.ptime{font-family:var(--mono);font-size:.68rem;letter-spacing:.03em;color:var(--ink-muted);white-space:nowrap;flex-shrink:0}
.pcur{color:var(--ink)}
/* "The Essay, Aloud" is the 3rd beat of This Week, not a new section:
   thin hairline + tight spacing so it reads as a continuation. */
.listen-week{padding-top:12px}
.listen-week .rule-head{border-top:1px solid var(--rule);padding-top:.7rem;margin-bottom:1.3rem}
/* front-and-center essay player runs a touch grander */
.listen-week .player{padding:1.7rem 0}
.listen-week .pp{width:60px;height:60px}
.listen-week .ptitle{font-size:clamp(1.25rem,2.1vw,1.6rem)}
/* rail edition player — compact, stacked, on a surface */
.player-rail{flex-direction:column;align-items:stretch;gap:.5rem;background:var(--surface);padding:15px 17px 16px;border-top:none;margin-bottom:18px}
.player-rail .ptitle{font-size:1.05rem;margin:.1rem 0 .4rem}
.player-rail .prow{gap:.7rem}
.player-rail .pp{width:38px;height:38px}
.player-rail .pp-icon{border-left-width:11px;border-top-width:7px;border-bottom-width:7px}
.player-rail.playing .pp-icon{width:11px;height:12px}
.player-rail .ptime{font-size:.6rem;color:var(--ink-faint)}

@media(max-width:980px){
  .np-inner{grid-template-columns:1fr;justify-items:center;text-align:center;gap:10px}
  .thisweek-head{flex-wrap:wrap;gap:.6rem}
  .np-left,.np-right{justify-self:center;text-align:center}
  .lead{grid-template-columns:1fr;gap:32px}
  .recent{grid-template-columns:1fr;gap:32px}
  .lexcards{grid-template-columns:1fr 1fr}
  .lexcard:nth-child(4n){border-right:1px solid var(--rule)}
  .lexcard:nth-child(2n){border-right:none}
}
/* mobile — tighten the menu bar */
@media(max-width:1080px){.mast-nav{display:none}.mast-toggle{display:inline-flex}}
@media(max-width:860px){.mast-inner{padding:10px 16px;gap:14px}}
/* mobile — "This Week" card rows become edge-to-edge swipe rails */
@media(max-width:860px){
  .stack-grid{
    display:flex;grid-template-columns:none;gap:.75rem;
    overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;
    scrollbar-width:none;-ms-overflow-style:none;
    margin-inline:-28px;padding:0 28px .4rem;scroll-padding-left:28px;
    overscroll-behavior-x:contain;
  }
  .stack-grid::-webkit-scrollbar{display:none}
  .stack-card{flex:0 0 clamp(200px,70vw,250px);scroll-snap-align:start}
  .stack-row-label{display:flex;align-items:baseline;gap:.5em}
  .stack-row-label::after{content:"swipe →";margin-left:auto;color:var(--ink-faint);letter-spacing:.12em}
}
@media(max-width:620px){
  .top-three-cards{grid-template-columns:1fr}
  .recent-cards{grid-template-columns:1fr}
  .lexcards{grid-template-columns:1fr}
  .lexcard{border-right:1px solid var(--rule)!important}
}
"""

PLAYER_JS = r"""
<script>
(function(){
  function fmt(s){s=Math.floor(s||0);var m=Math.floor(s/60),x=s%60;return m+":"+(x<10?"0":"")+x;}
  var current=null;
  document.querySelectorAll('.player').forEach(function(p){
    var src=p.getAttribute('data-src'), audio=null;
    var btn=p.querySelector('.pp'), fill=p.querySelector('.pfill'),
        knob=p.querySelector('.pknob'), track=p.querySelector('.ptrack'),
        cur=p.querySelector('.pcur');
    function ensure(){
      if(audio) return audio;
      audio=new Audio(src); audio.preload='metadata';
      audio.addEventListener('timeupdate',function(){
        var d=audio.duration||0, pct=d?audio.currentTime/d*100:0;
        fill.style.width=pct+'%'; knob.style.left=pct+'%'; cur.textContent=fmt(audio.currentTime);
      });
      audio.addEventListener('ended',function(){p.classList.remove('playing');});
      return audio;
    }
    btn.addEventListener('click',function(){
      ensure();
      if(audio.paused){
        if(current&&current!==audio){current.pause();current.__p.classList.remove('playing');}
        audio.play(); audio.__p=p; current=audio; p.classList.add('playing');
      } else { audio.pause(); p.classList.remove('playing'); }
    });
    track.addEventListener('click',function(ev){
      ensure();
      var r=track.getBoundingClientRect(), pct=(ev.clientX-r.left)/r.width;
      if(audio.duration) audio.currentTime=Math.max(0,Math.min(1,pct))*audio.duration;
    });
  });
})();
function edToggle(btn){
  // one is always open: clicking the open row keeps it open; never all-closed
  if(btn.getAttribute('aria-expanded')==='true') return;
  var list=btn.closest('.side-list');
  list.querySelectorAll('.ed-row').forEach(function(b){b.setAttribute('aria-expanded','false');});
  list.querySelectorAll('.ed-body').forEach(function(d){d.hidden=true;});
  btn.setAttribute('aria-expanded','true');
  btn.nextElementSibling.hidden=false;
}
</script>
"""

def _site_colophon():
    """The dark colophon footer, shared by the homepage and the /featured page."""
    _yrs = [p["published_at"][:4] for p in posts if p.get("published_at")]
    _years = f"{min(_yrs)}–{max(_yrs)}" if _yrs else ""
    return gs.render_colophon(
        prefix="",
        mark_url="assets/crystal-ball.svg",
        primary=[
            {"label": "Home", "href": "index.html"},
            {"label": "Archive", "href": "archive.html"},
            {"label": "All Topics", "href": "tags/index.html"},
            {"label": "The Lexicon", "href": "lexicon/index.html"},
            {"label": "Essays", "href": "tags/a-closer-look.html"},
            {"label": "Newsletters", "href": "tags/worthafortune.html"},
            {"label": "Podcast", "href": "podcast.html"},
        ],
        meta=[
            {"label": "About", "href": "about/index.html"},
            {"label": "Links", "href": "links/index.html"},
            {"label": "Corpus Report", "href": "metrics.html"},
            {"label": "Ghost CMS", "href": gs.GHOST_URL, "external": True},
            {"label": "GitHub Archive", "href": "https://github.com/iamkhayyam/tokenwisdom", "external": True},
        ],
        tags=[{"name": t["name"], "href": f'tags/{t["slug"]}.html'} for t in top_tags[:7]],
        socials=[
            {"label": "X", "href": "https://x.com/worthafortune"},
            {"label": "LinkedIn", "href": "https://www.linkedin.com/company/token-wisdom-newsletter/"},
            {"label": "RSS", "href": f"{gs.GHOST_URL}/rss/"},
        ],
        signoff=" ".join(gs.SITE_SIGN_OFF_LINES),
        stats=f"{len(chrono)} Posts · {len(public_tags)} Tags",
        copyright=f"© {_years} Token Wisdom" if _years else "© Token Wisdom",
        subscribe_url=f"{gs.GHOST_URL}/subscribe",
        handle="@iamkhayyam",
        ama=gs.get_ama_cta(),
    )


def _doc(title, body):
    """Wrap body markup in the shared homepage shell (head + fonts + CSS)."""
    bare_title = title.split(" — ")[0] if " — " in title else title
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
{tw_theme.meta_head(bare_title, url=tw_theme.SITE_ORIGIN + "/")}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=Libre+Caslon+Display&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,300;1,8..60,400&display=swap" rel="stylesheet">
<style>{CSS}{gs.COLOPHON_CSS}{tw_theme.OVERLAY_CSS}</style>
</head><body>
{body}
{PLAYER_JS}
</body></html>"""


def build(out_name="home-v2.html"):
    """Assemble the homepage and write it to docs/<out_name>.
    generate_site.py calls build('index.html') for production; running this
    module directly writes 'home-v2.html' for preview."""
    body = f"""{render_masthead()}
<main class="wrap">
{render_hero()}
{render_listen()}
{render_stack()}
</main>
{render_subscribe()}
<div class="wrap">
{render_recent()}
{render_featured()}
{render_topics()}
{render_lexicon()}
</div>
{_site_colophon()}"""
    out = DOCS / out_name
    out.write_text(_doc("Token Wisdom — The Newsletter of Record for the Future of Now", body))
    return out


def build_featured(out_name="featured.html"):
    """The full Featured index — every featured piece, newest first."""
    cards = "".join(_feat_card(p) for p in all_featured)
    body = f"""{render_masthead()}
<main class="wrap">
  <section class="block">
    <div class="rule-head"><h2 class="rule-label">Featured</h2>
      <span class="rule-meta">{len(all_featured)} editor&rsquo;s picks</span></div>
    <p class="lex-intro">Hand-picked pieces worth your time — the essays, letters, and deep dives we keep coming back to. Newest first.</p>
    <div class="feat-grid">{cards}
    </div>
  </section>
</main>
{_site_colophon()}"""
    out = DOCS / out_name
    out.write_text(_doc("Featured — Token Wisdom", body))
    return out


if __name__ == "__main__":
    _out = build("home-v2.html")
    build_featured("featured.html")
    print(f"Wrote {_out}")
    print(f"  hero: {hero.get('title')!r}")
    print(f"  edition: {gs.clean_title(latest_ed)!r} ({gs.issue_code_string(latest_ed, issue_nums.get(latest_ed['slug'],0))})")
    print(f"  lexicon strip: {feature_terms}")
    print("  preview: http://localhost:8765/home-v2.html")

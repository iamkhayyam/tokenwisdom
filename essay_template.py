#!/usr/bin/env python3
"""
essay_template.py — the canonical "A Closer Look" essay template.

One template, two consumers:
  • the static site (generate_site.py maps a Ghost post onto an EssayDoc), and
  • the CMS backend (it builds an EssayDoc from its own fields).

Everything the page needs travels in the EssayDoc data contract below; the
renderer is pure (doc -> HTML string) and self-contained — it ships its own
tokens, fonts, dark-mode toggle, and prose styles, so a CMS can render a
complete standalone page without the rest of the site.

The design is the Claude Design mock "Essay — The Sky Has Been Warning Us":
1080 frame, 720 reading column held left, sidenotes in the right gutter, a
cover image and an opening epigraph always leading, Libre Caslon display /
Source Serif body / Archivo sans / FauxCRA mono, terracotta accent, and a
light/dark toggle (dark = the warm "Index" palette).

Run directly to write a worked example to docs/essay-template.html:
    python3 essay_template.py
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent


# ============================================================
# DATA CONTRACT
# ============================================================

@dataclass
class EssayDoc:
    """Everything the essay template renders. The CMS fills this; so does the
    site (from a Ghost post). Only `title` and `body_html` are truly required;
    the rest degrade gracefully (no cover, no epigraph, generic footer)."""

    # --- core ---
    title: str = ""
    body_html: str = ""                       # rich HTML; sanitized on render

    # --- kicker line: "A Closer Look · Week 13 · Infrastructure" ---
    section: str = "A Closer Look"
    week: int | None = None
    topic: str = ""

    # --- cover (we always lead with one) ---
    cover_image: str = ""
    cover_alt: str = ""
    cover_caption: str = "Illustration · Token Wisdom"

    # --- standfirst / dek ---
    dek: str = ""

    # --- byline ---
    author: str = "@iamkhayyam"
    date: str = ""                            # display string, e.g. "March 26, 2026"
    reading_time: str = ""                    # e.g. "9 min read"

    # --- epigraph (we always begin with a quote) ---
    epigraph_quote: str = ""
    epigraph_cite: str = ""

    # --- footer / back-to-edition ---
    edition_number: int | None = None
    edition_week: int | None = None
    edition_url: str = ""                     # link target for "back to the edition"

    # --- chrome ---
    theme: str = "light"                      # default theme: "light" | "dark"
    issue_code: str = ""                      # top-bar code, e.g. "ACL.153 · W13 · Mar 26, 2026"
    brand: str = "Token Wisdom"
    brand_mark_url: str = "assets/crystal-ball.svg"
    back_label: str = ""                      # top-bar back link text; "" hides it
    back_url: str = ""
    canonical_url: str = ""

    # --- standalone document options ---
    standalone: bool = True                   # emit a full <html> doc + <head>
    font_dir: str = "assets/fonts"            # where FauxCRA-Monospaced.otf lives
    extra_head: str = ""                      # CMS hook: analytics, canonical, etc.
    extra_body_end: str = ""                  # CMS hook: scripts before </body>


# ============================================================
# BODY SANITIZER — repairs Ghost-import damage
# ============================================================

# Ghost's bookmark-card export double-encoded the descriptions: a real space
# became "&nbsp;" and then the ampersand got re-escaped to "&amp;nbsp;". Rendered,
# that's the literal string "In&nbsp;this&nbsp;..." with no break opportunities,
# so it can't wrap and runs off the page. We undo exactly one layer of over-
# escaping; "&amp;nbsp;" in particular becomes a normal (breakable) space.
_OVERESC_NBSP = re.compile(r"&amp;nbsp;")
_OVERESC_ENTITY = re.compile(r"&amp;(#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]{1,30});")
_CAPTIVATE_IFRAME = re.compile(
    r"<iframe\b([^>]*\bsrc=\"[^\"]*captivate\.fm[^\"]*\"[^>]*)>\s*</iframe>",
    re.IGNORECASE,
)


def sanitize_body(html_str: str) -> str:
    """Make Ghost-exported body HTML safe for the reading column:
      1. undo the double-encoded entities (the captivate bookmark-card bug),
      2. wrap captivate player iframes in a responsive, contained box,
      3. tag bookmark cards so CSS can clamp them.
    Idempotent and conservative — it only touches the known-broken patterns."""
    if not html_str:
        return ""

    # 1. one level of over-escaping. nbsp -> real space so the line can wrap.
    html_str = _OVERESC_NBSP.sub(" ", html_str)
    html_str = _OVERESC_ENTITY.sub(r"&\1;", html_str)

    # 2. responsive container around captivate player iframes. Ghost wrapped some
    #    in a fixed 200px div and hard-coded the iframe's inline width/height; we
    #    strip that inline style so .tw-embed (the CSS) owns the sizing, then
    #    normalize all of them to the .tw-embed plate.
    def _wrap_iframe(m: re.Match) -> str:
        attrs = re.sub(r'\s*style="[^"]*"', "", m.group(1))
        return f'<div class="tw-embed"><iframe{attrs} loading="lazy"></iframe></div>'
    html_str = _CAPTIVATE_IFRAME.sub(_wrap_iframe, html_str)

    # collapse the now-redundant fixed-size Ghost wrapper around our .tw-embed
    html_str = re.sub(
        r'<div style="width:\s*100%;\s*height:\s*200px;[^"]*">\s*(<div class="tw-embed">)',
        r"\1", html_str)
    html_str = re.sub(r'(</div>)\s*</div>(\s*<!--kg-card-end)', r"\1\2", html_str)

    return html_str


def mark_lede(html_str: str) -> str:
    """Tag the first substantial opening paragraph 'essay-lede' so the drop cap
    lands on real prose, not a leading card, image, caption, or a short quote-
    attribution line. Adds a class only; content is otherwise untouched."""
    for m in re.finditer(r"<p(\s[^>]*)?>(.*?)</p>", html_str, re.S):
        inner = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if len(inner) >= 120 and re.match(r"[A-Za-z]", inner):
            attrs = m.group(1) or ""
            if "essay-lede" in attrs:
                return html_str
            if 'class="' in attrs:
                new_open = re.sub(r'class="', 'class="essay-lede ', attrs, count=1)
                new_tag = f"<p{new_open}>"
            else:
                new_tag = f'<p class="essay-lede"{attrs}>'
            return html_str[:m.start()] + new_tag + html_str[m.start(2):]
    return html_str


# ============================================================
# STYLES
# ============================================================

def _css(font_dir: str) -> str:
    return f"""
@font-face{{font-family:'FauxCRA Mono';src:url('{font_dir}/FauxCRA-Monospaced.otf') format('opentype');font-weight:400;font-style:normal;font-display:swap}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}
:root{{
  --ink:#1a1814; --ink-muted:#6b6760; --ink-faint:#b0aca6;
  --paper:#faf8f4; --paper-warm:#f4f1ea; --paper-rule:#e6e2d9;
  --accent:#c8521a; --accent-muted:#e8c4ae; --accent-deep:#8a3610;
  --serif:'Source Serif 4',Georgia,serif;
  --display:'Libre Caslon Display',Georgia,serif;
  --sans:'Archivo',-apple-system,BlinkMacSystemFont,sans-serif;
  --mono:'FauxCRA Mono','DM Mono',ui-monospace,'SFMono-Regular',Consolas,monospace;
}}
:root[data-theme="dark"]{{
  --ink:#f3ecdd; --ink-muted:#a59c8a; --ink-faint:#8e8470;
  --paper:#15130e; --paper-warm:#1f1c12; --paper-rule:#2a2718;
  --accent:#d98a4e; --accent-muted:#4a3a28; --accent-deep:#e3a464;
}}
body{{background-color:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:18px;line-height:1.6;transition:background-color .25s ease,color .25s ease}}
img{{max-width:100%;height:auto;display:block}}
a{{color:inherit;text-decoration:none}}

/* Theme toggle */
.theme-toggle{{position:fixed;top:22px;right:22px;z-index:90;display:flex;align-items:center;gap:9px;
  background:var(--paper);color:var(--ink);border:1.5px solid var(--ink);border-radius:999px;
  padding:9px 15px;cursor:pointer;font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;
  text-transform:uppercase;transition:background-color .2s,color .2s,border-color .2s}}
.theme-toggle:hover{{background:var(--paper-warm)}}
.theme-toggle .tt-glyph{{font-size:13px;line-height:1}}

/* Top bar */
.essay-topbar{{border-bottom:1px solid var(--paper-rule)}}
.essay-topbar-inner{{max-width:1080px;margin:0 auto;padding:18px 40px;display:flex;align-items:center;gap:14px}}
.essay-topbar .brand{{display:flex;align-items:center;gap:9px}}
.essay-topbar .brand img{{height:26px;width:auto}}
.essay-topbar .brand-name{{font-family:var(--display);font-size:20px;letter-spacing:-.02em;color:var(--ink);white-space:nowrap}}
.essay-topbar .sep{{color:var(--ink);opacity:.4}}
.essay-topbar .back{{font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);white-space:nowrap}}
.essay-topbar .back:hover{{opacity:.7}}

/* Frame + column */
.essay-frame{{max-width:1080px;margin:0 auto;padding:0 40px 1rem}}
.essay-col{{max-width:720px}}

/* Cover */
.essay-cover{{margin:30px 0 0}}
.essay-cover img{{width:100%;height:440px;object-fit:cover;object-position:50% 38%;border:1px solid var(--paper-rule)}}
.essay-cover figcaption{{font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-muted);margin-top:10px}}

/* Header */
.essay-head{{padding:48px 0 34px}}
.essay-eyebrow{{font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:24px}}
.essay-title{{font-family:var(--display);font-weight:400;font-size:clamp(40px,7vw,64px);line-height:1.0;letter-spacing:-.03em;color:var(--ink);margin:0 0 22px;text-wrap:balance}}
.essay-deck{{font-family:var(--serif);font-size:clamp(18px,2.4vw,21px);line-height:1.5;color:var(--ink-muted);margin:0 0 26px}}
.essay-byline{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-muted);border-top:1px solid var(--paper-rule);padding-top:18px}}
.essay-byline .by{{color:var(--ink)}}
.essay-byline .sep{{color:var(--ink-faint)}}

/* Epigraph */
.essay-epigraph{{border-left:3px solid var(--accent);padding:6px 0 6px 24px;margin:0 0 44px}}
.essay-epigraph p{{font-family:var(--serif);font-style:italic;font-size:clamp(20px,2.6vw,25px);line-height:1.4;color:var(--ink);margin:0 0 12px}}
.essay-epigraph cite{{display:block;font-style:normal;font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}}

/* Body */
.essay-body{{position:relative;padding:8px 0 40px}}
.prose{{max-width:720px;font-family:var(--serif);font-size:19px;line-height:1.72;color:var(--ink)}}
.prose p{{margin:0 0 24px}}
.prose p.essay-lede::first-letter{{float:left;font-family:var(--display);font-size:78px;line-height:.72;margin:8px 14px 0 0;color:var(--accent)}}
.prose h2{{font-family:var(--display);font-weight:400;font-size:clamp(26px,3.6vw,32px);line-height:1.1;letter-spacing:-.02em;color:var(--ink);margin:42px 0 18px;max-width:600px}}
.prose h3{{font-family:var(--display);font-weight:400;font-size:1.5rem;color:var(--ink);margin:32px 0 14px}}
.prose a{{color:var(--accent);border-bottom:1px solid var(--accent-muted)}}
.prose a:hover{{color:var(--accent-deep);border-color:var(--accent-deep)}}
.prose em{{font-style:italic}}
.prose strong{{font-weight:600}}
.prose ul,.prose ol{{margin:1.2rem 0 1.4rem 1.4rem}}
.prose li{{margin-bottom:.55rem}}
.prose blockquote{{margin:38px 0;max-width:640px}}
.prose blockquote p{{font-family:var(--display);font-weight:400;font-size:clamp(26px,4vw,36px);line-height:1.12;letter-spacing:-.02em;color:var(--ink);margin:0}}
.prose img,.prose figure{{margin:2rem 0}}
.prose figcaption{{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-muted);margin-top:.6rem}}
.prose hr{{border:none;border-top:1px solid var(--paper-rule);margin:2.4rem 0}}

/* Margin sidenote (authored) — lifts into the right gutter on wide screens */
.tw-note{{float:right;clear:right;width:250px;margin:4px -280px 18px 0;font-family:var(--mono);font-size:11.5px;line-height:1.58;letter-spacing:.01em;color:var(--ink-muted);border-top:2px solid var(--accent);padding-top:9px}}
.tw-note em{{font-style:italic}}

/* Closing line */
.essay-closer{{font-family:var(--serif);font-size:21px;line-height:1.6;font-style:italic;color:var(--ink);margin:34px 0 0;max-width:600px;border-top:2px solid var(--ink);padding-top:22px}}

/* Footer */
.essay-foot{{border-top:3px solid var(--ink);padding:30px 0 60px;display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between}}
.essay-foot .ef-edition{{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-muted)}}
.essay-foot .ef-back{{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);border-bottom:1px solid var(--accent-muted);padding-bottom:3px}}
.essay-foot .ef-back:hover{{border-color:var(--accent);color:var(--accent-deep)}}

/* ---- Link embeds: bookmark cards + media players. One component family —
   shared hairline + radius, hardened against overflow, alive on hover. ---- */
.prose iframe{{max-width:100%;border:0}}
.tw-embed{{width:100%;max-width:100%;margin:2rem 0;padding:6px;border:1px solid var(--ink-faint);border-radius:5px;background:var(--paper)}}
.tw-embed iframe{{display:block;width:100%;height:220px;margin:0;border:1px solid var(--paper-rule);border-radius:3px;background:var(--paper-warm)}}
.prose .kg-card{{max-width:100%}}
.prose .kg-bookmark-card{{margin:1.6rem 0;padding:6px;border:1px solid var(--ink-faint);border-radius:5px;background:var(--paper);transition:border-color .2s cubic-bezier(.22,1,.36,1)}}
.prose .kg-bookmark-card:has(.kg-bookmark-container:hover){{border-color:var(--accent)}}
.prose .kg-bookmark-container{{display:flex;min-height:130px;width:100%;max-width:100%;border:1px solid var(--paper-rule);border-radius:3px;overflow:hidden;background:var(--paper-warm);color:var(--ink);transition:border-color .2s cubic-bezier(.22,1,.36,1)}}
.prose .kg-bookmark-container:hover{{border-color:var(--accent)}}
.prose .kg-bookmark-container:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.prose .kg-bookmark-content{{flex:1 1 auto;min-width:0;padding:13px 18px;overflow:hidden;display:flex;flex-direction:column;justify-content:center}}
.prose .kg-bookmark-title{{font-family:var(--sans);font-weight:600;font-size:.95rem;line-height:1.28;letter-spacing:-.01em;margin:0 0 .2rem;color:var(--ink);overflow-wrap:anywhere;word-break:break-word;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;transition:color .2s ease}}
.prose .kg-bookmark-container:hover .kg-bookmark-title{{color:var(--accent)}}
.prose .kg-bookmark-description{{font-family:var(--serif);font-size:.85rem;line-height:1.4;color:var(--ink-muted);overflow-wrap:anywhere;word-break:break-word;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}}
.prose .kg-bookmark-metadata{{font-family:var(--mono);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin-top:.5rem;display:flex;align-items:center;gap:.5rem;overflow:hidden}}
.prose .kg-bookmark-metadata img{{width:15px;height:15px;margin:0;border-radius:3px;flex-shrink:0}}
.prose .kg-bookmark-author{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.prose .kg-bookmark-thumbnail{{flex:0 0 188px;max-width:188px;align-self:stretch;position:relative;overflow:hidden}}
.prose .kg-bookmark-thumbnail img{{position:absolute;inset:0;width:100%;height:100%;margin:0;object-fit:cover;transition:transform .5s cubic-bezier(.22,1,.36,1)}}
.prose .kg-bookmark-container:hover .kg-bookmark-thumbnail img{{transform:scale(1.06)}}

@media(max-width:1100px){{ .tw-note{{float:none;width:auto;margin:14px 0 22px}} }}
@media(max-width:680px){{
  .essay-topbar-inner,.essay-frame{{padding-left:1.25rem;padding-right:1.25rem}}
  .essay-cover img{{height:280px}}
  .essay-head{{padding:32px 0 26px}}
  .theme-toggle{{top:14px;right:14px;padding:7px 12px}}
  .prose{{font-size:18px}}
  .prose .kg-bookmark-container{{flex-direction:column-reverse}}
  .prose .kg-bookmark-thumbnail{{flex-basis:auto;max-width:100%;height:160px;align-self:auto}}
}}
@media(prefers-reduced-motion:reduce){{
  body,.theme-toggle,.prose .kg-bookmark-card,.prose .kg-bookmark-container,.prose .kg-bookmark-title,.prose .kg-bookmark-thumbnail img{{transition:none}}
  .prose .kg-bookmark-container:hover .kg-bookmark-thumbnail img{{transform:none}}
}}
""" + READING_APPARATUS_CSS + COLOPHON_CSS


_THEME_SCRIPT = """
<script>
(function(){
  var KEY='tw-theme';
  try{var s=localStorage.getItem(KEY);if(s)document.documentElement.setAttribute('data-theme',s);}catch(e){}
  window.__twToggleTheme=function(){
    var d=document.documentElement,next=d.getAttribute('data-theme')==='dark'?'light':'dark';
    d.setAttribute('data-theme',next);
    try{localStorage.setItem(KEY,next);}catch(e){}
    sync();
  };
  function sync(){
    var dk=document.documentElement.getAttribute('data-theme')==='dark';
    var b=document.querySelector('.theme-toggle');
    if(b){b.querySelector('.tt-glyph').textContent=dk?'\\u263c':'\\u263e';b.querySelector('.tt-label').textContent=dk?'Light':'Dark';}
  }
  document.addEventListener('DOMContentLoaded',sync);
})();
</script>
"""


# ============================================================
# READING APPARATUS — margin furniture + bottom index
# Shared by the static site (generate_site.py imports these) and the CMS
# template, so both render an identical reading experience.
# ============================================================

# Plain CSS (no f-string): single braces are literal. Uses the same custom
# properties both consumers define, so it themes for free in light and dark.
READING_APPARATUS_CSS = """
/* ---- Margin note types (right gutter; base .tw-note supplies the float) ---- */
.tw-note--term,.tw-note--stat{border-top-color:var(--ink)}
.tw-note--term .twn-term{display:block;font-family:var(--sans);font-weight:600;font-size:.82rem;line-height:1.25;letter-spacing:0;text-transform:none;color:var(--ink);margin-bottom:.3rem}
.tw-note--term .twn-def{display:block;font-family:var(--serif);font-size:.82rem;line-height:1.5;letter-spacing:0;text-transform:none;color:var(--ink-muted);margin-bottom:.5rem}
.tw-note--term .twn-link{font-family:var(--mono);font-size:.58rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.tw-note--term .twn-link:hover{color:var(--accent-deep)}
.tw-note--stat .twn-num{display:block;font-family:var(--display);font-weight:400;font-size:2.2rem;line-height:.95;letter-spacing:-.02em;text-transform:none;color:var(--ink);margin-bottom:.35rem}
.tw-note--stat .twn-cap{display:block;font-family:var(--mono);font-size:.62rem;line-height:1.45;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted)}

/* ---- Left-edge section markers (wide screens only) ---- */
@media (min-width:1160px){
  .essay-body .prose{counter-reset:tw-sec}
  .essay-body .prose h2{position:relative;counter-increment:tw-sec}
  .essay-body .prose h2::before{content:counter(tw-sec,decimal-leading-zero);position:absolute;left:-4.25rem;top:.6rem;font-family:var(--mono);font-size:.66rem;letter-spacing:.1em;color:var(--accent);opacity:.85}
}

/* ---- Bottom reading index ---- */
.essay-index{position:fixed;left:0;right:0;bottom:0;z-index:70;opacity:0;transform:translateY(10px);transition:opacity .3s ease,transform .3s ease;pointer-events:none}
.essay-index[data-shown]{opacity:1;transform:none;pointer-events:auto}
.essay-index .ei-inner{position:relative;max-width:1080px;margin:0 auto;padding:0 40px}
.essay-index .ei-bar{display:flex;align-items:center;gap:16px;height:46px;padding:0 16px;background:var(--paper);border:1px solid var(--paper-rule);border-bottom:none;border-radius:6px 6px 0 0;box-shadow:0 -6px 22px -14px rgba(20,16,10,.3);cursor:pointer}
.essay-index .ei-current{font-family:var(--sans);font-weight:600;font-size:.78rem;color:var(--ink);white-space:nowrap;max-width:38%;overflow:hidden;text-overflow:ellipsis}
.essay-index .ei-track{flex:1;display:flex;gap:5px;align-items:center}
.essay-index .ei-seg{position:relative;flex:1;height:3px;background:var(--paper-rule);border-radius:2px;overflow:hidden;cursor:pointer}
.essay-index .ei-seg::after{content:'';position:absolute;inset:-7px 0;display:block}
.essay-index .ei-seg.is-current{height:5px}
.essay-index .ei-seg-fill{position:absolute;inset:0;display:block;background:var(--accent);transform:scaleX(0);transform-origin:left;transition:transform .14s linear;border-radius:2px}
.essay-index .ei-pct{font-family:var(--mono);font-size:.62rem;letter-spacing:.1em;color:var(--ink-faint);white-space:nowrap}
.essay-index .ei-panel{position:absolute;left:40px;right:40px;bottom:46px;max-height:0;overflow:hidden;opacity:0;background:var(--paper);border:1px solid var(--paper-rule);border-bottom:none;border-radius:6px 6px 0 0;box-shadow:0 -10px 30px -18px rgba(20,16,10,.35);transition:max-height .32s cubic-bezier(.22,1,.36,1),opacity .25s ease}
.essay-index:hover .ei-panel,.essay-index[data-open] .ei-panel{max-height:60vh;opacity:1;overflow:auto}
.essay-index .ei-panel-head{font-family:var(--mono);font-size:.6rem;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-faint);padding:13px 16px 9px;border-bottom:1px solid var(--paper-rule)}
.essay-index .ei-row{display:flex;align-items:baseline;gap:12px;width:100%;text-align:left;background:none;border:none;border-bottom:1px solid var(--paper-rule);padding:11px 16px;cursor:pointer;color:var(--ink-muted);font-family:var(--sans);font-size:.92rem;line-height:1.3;transition:color .15s ease,background .15s ease}
.essay-index .ei-row:last-child{border-bottom:none}
.essay-index .ei-row:hover{color:var(--ink);background:var(--paper-warm)}
.essay-index .ei-row.is-current{color:var(--accent)}
.essay-index .ei-row--sub{padding-left:38px;font-size:.84rem}
.essay-index .ei-row-n{font-family:var(--mono);font-size:.58rem;letter-spacing:.1em;color:var(--ink-faint);min-width:1.6em;flex-shrink:0}
.essay-index .ei-row.is-current .ei-row-n{color:var(--accent)}
@media (max-width:680px){.essay-index .ei-inner{padding:0 12px}.essay-index .ei-panel{left:12px;right:12px}.essay-index .ei-current{max-width:32%}}
@media (prefers-reduced-motion:reduce){.essay-index,.essay-index .ei-panel,.essay-index .ei-seg-fill{transition:none}}
"""


# Static shell; the script populates segments + the panel list from headings.
INDEX_MARKUP = """
<div class="essay-index" data-essay-index aria-label="Reading progress and contents">
  <div class="ei-inner">
    <div class="ei-panel"><div class="ei-panel-head">Contents</div></div>
    <div class="ei-bar" role="button" tabindex="0" aria-label="Table of contents">
      <span class="ei-current">Opening</span>
      <div class="ei-track"></div>
      <span class="ei-pct">0%</span>
    </div>
  </div>
</div>
"""

INDEX_SCRIPT = """
<script>
(function(){
  function init(){
    var prose=document.querySelector('.essay-body .prose');
    var idx=document.querySelector('[data-essay-index]');
    if(!prose||!idx) return;
    var foot=document.querySelector('.essay-foot');
    var heads=[].slice.call(prose.querySelectorAll('h2, h3'));
    var sections=[{el:prose,name:'Opening',level:1}];
    heads.forEach(function(h,i){
      if(!h.id){ h.id='sec-'+(i+1)+'-'+((h.textContent||'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,40)); }
      sections.push({el:h,name:(h.textContent||'').trim(),level:h.tagName==='H3'?2:1});
    });
    var track=idx.querySelector('.ei-track'), panel=idx.querySelector('.ei-panel');
    var curLabel=idx.querySelector('.ei-current'), pct=idx.querySelector('.ei-pct');
    function jump(s){ var y=s.el.getBoundingClientRect().top+window.scrollY-92; window.scrollTo({top:Math.max(0,y),behavior:'smooth'}); }
    sections.forEach(function(s,i){
      var seg=document.createElement('div'); seg.className='ei-seg'; var fill=document.createElement('i'); fill.className='ei-seg-fill'; seg.appendChild(fill);
      seg.addEventListener('click',function(e){e.stopPropagation();jump(s);}); track.appendChild(seg); s.seg=seg; s.fill=fill;
      var row=document.createElement('button'); row.type='button'; row.className='ei-row'+(s.level===2?' ei-row--sub':'');
      row.innerHTML='<span class="ei-row-n">'+(i===0?'\\u2022':(''+i).padStart(2,'0'))+'</span><span class="ei-row-name"></span>';
      row.querySelector('.ei-row-name').textContent=s.name;
      row.addEventListener('click',function(){jump(s);}); panel.appendChild(row); s.row=row;
    });
    function tops(){ return sections.map(function(s){return s.el.getBoundingClientRect().top+window.scrollY;}); }
    function update(){
      var vh=window.innerHeight, y=window.scrollY, t=tops();
      var startY=t[0], endY=(foot?foot.getBoundingClientRect().top+y:document.body.scrollHeight)-vh*0.5;
      if(endY<=startY) endY=startY+1;
      pct.textContent=Math.round(Math.max(0,Math.min(1,(y+120-startY)/(endY-startY)))*100)+'%';
      var cur=0; for(var i=0;i<sections.length;i++){ if(t[i]-120<=y) cur=i; }
      sections.forEach(function(s,i){
        var f=0;
        if(i<cur) f=1;
        else if(i===cur){ var next=(i+1<t.length)?t[i+1]:endY+vh; f=Math.max(0,Math.min(1,(y+120-t[i])/Math.max(1,next-t[i]))); }
        s.fill.style.transform='scaleX('+f.toFixed(3)+')';
        s.seg.classList.toggle('is-current',i===cur);
        s.row.classList.toggle('is-current',i===cur);
      });
      curLabel.textContent=sections[cur].name;
      var nearFoot=foot && foot.getBoundingClientRect().top<vh*0.55;
      idx.toggleAttribute('data-shown', y>320 && !nearFoot);
    }
    var bar=idx.querySelector('.ei-bar');
    function togglePin(){ idx.toggleAttribute('data-open'); }
    bar.addEventListener('click',function(e){ if(e.target.closest('.ei-track'))return; togglePin(); });
    bar.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){e.preventDefault();togglePin();} });
    window.addEventListener('scroll',update,{passive:true});
    window.addEventListener('resize',update);
    update();
  }
  if(document.readyState!=='loading') init(); else document.addEventListener('DOMContentLoaded',init);
})();
</script>
"""


def demo_margin_notes(html_str):
    """Illustrative margin furniture for the showcase essay: drops a Lexicon term
    gloss, a source note, and a stat callout into the gutter so the apparatus is
    visible on real content. In production the CMS authors these inline; this is
    keyed to known paragraphs of the Sky essay only."""
    notes = [
        ("The coronal mass ejection is something else",
         '<span class="tw-note tw-note--term"><span class="twn-term">Coronal Mass Ejection</span>'
         '<span class="twn-def">A billion-ton eruption of magnetized plasma from the sun&rsquo;s corona '
         '&mdash; the slow, heavy sibling of a solar flare, and the part that actually hits the grid.</span>'
         '<a class="twn-link" href="/lexicon/">In the Lexicon &rarr;</a></span>'),
        ("On March 13, 1989, a geomagnetic storm",
         '<span class="tw-note">March 13, 1989 &mdash; a sub-Carrington storm collapsed the Hydro-Qu&eacute;bec '
         'grid in 92 seconds, six million people dark. (NASA/NOAA)</span>'),
        ("A 12% probability per decade",
         '<span class="tw-note tw-note--stat"><span class="twn-num">~12%</span>'
         '<span class="twn-cap">odds of a Carrington-class storm, per decade &middot; Riley, Space Weather 2012</span></span>'),
    ]
    for prefix, note in notes:
        pat = re.compile(r'(<p\b[^>]*>)(\s*' + re.escape(prefix) + r')', re.IGNORECASE)
        html_str = pat.sub(lambda m, n=note: m.group(1) + n + m.group(2), html_str, count=1)
    return html_str


# ============================================================
# SITE COLOPHON — the dark "of-record" footer
# A three-tier sandwich: (1) pitch + slim subscribe, (2) pill links + popular
# tags, (3) sign-off + colophon bar, all over a ghost-outlined "Token Wisdom"
# watermark. Always dark (its own palette), full-bleed. Shared by the static
# site (generate_site imports it) and the standalone template.
# ============================================================

COLOPHON_CSS = """
.tw-colophon{--cg:oklch(0.195 0.055 31);--ci:#f1ead9;--ci2:#bcb3a0;--cm:#8b8270;--cf:#5f5848;--cr:rgba(241,234,217,.11);--cr2:rgba(241,234,217,.06);--cpanel:rgba(241,234,217,.025);--cacc:#d98a4e;position:relative;background:var(--cg);color:var(--ci);overflow:hidden;border-top:1px solid var(--cr);font-family:var(--sans)}
.tw-colophon .col-inner{position:relative;max-width:1240px;margin:0 auto;padding:0 52px}
.tw-colophon .col-ghost-wrap{position:absolute;left:0;top:0;bottom:0;z-index:0;display:flex;align-items:center;pointer-events:none}
.tw-colophon .col-ghost{font-family:var(--display);font-weight:400;font-size:clamp(200px,32vw,440px);line-height:.82;letter-spacing:-.04em;white-space:nowrap;color:transparent;-webkit-text-stroke:1px rgba(241,234,217,.055)}
.tw-colophon .col-t1{position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:space-between;gap:48px;padding:64px 0 52px}
.tw-colophon .col-pitch{max-width:600px}
.tw-colophon .col-eyebrow{display:flex;align-items:center;gap:12px;margin-bottom:22px}
.tw-colophon .col-eyebrow img{height:26px;width:auto;opacity:.92}
.tw-colophon .col-eyebrow span{font-family:var(--mono);font-size:10px;letter-spacing:.26em;text-transform:uppercase;color:var(--cacc)}
.tw-colophon .col-h2{font-family:var(--display);font-weight:400;font-size:clamp(32px,4.4vw,54px);line-height:1.02;letter-spacing:-.022em;color:var(--ci);margin:0;max-width:14ch}
.tw-colophon .col-sub{width:340px;max-width:100%;flex-shrink:0}
.tw-colophon .col-sub-label{font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--cm);margin-bottom:14px}
.tw-colophon .col-subform{display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--cr);padding-bottom:12px;transition:border-color .2s ease}
.tw-colophon .col-subform:focus-within{border-color:var(--cacc)}
.tw-colophon .col-subform input{flex:1;min-width:0;background:transparent;border:none;outline:none;color:var(--ci);font-family:var(--mono);font-size:13px;letter-spacing:.04em;padding:4px 0}
.tw-colophon .col-subform input::placeholder{color:var(--cf)}
.tw-colophon .col-subform button{flex-shrink:0;background:none;border:none;cursor:pointer;font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--cacc);transition:opacity .2s ease}
.tw-colophon .col-subform button:hover{opacity:.65}
.tw-colophon .col-t2{position:relative;z-index:1;padding:30px 0}
.tw-colophon .col-links{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}
.tw-colophon .col-links a{font-family:var(--sans);font-size:14px;white-space:nowrap;color:var(--ci2);border:1px solid var(--cr);border-radius:7px;padding:9px 17px;background:var(--cpanel);transition:color .18s ease,border-color .18s ease,background .18s ease}
.tw-colophon .col-links a:hover{color:var(--ci);border-color:var(--cacc);background:rgba(217,138,78,.06)}
.tw-colophon .col-meta{display:flex;flex-wrap:wrap;gap:10px}
.tw-colophon .col-meta a{font-family:var(--sans);font-size:14px;white-space:nowrap;color:var(--cm);border:1px solid var(--cr);border-radius:7px;padding:9px 17px;transition:color .18s ease,border-color .18s ease}
.tw-colophon .col-meta a:hover{color:var(--ci);border-color:var(--cr)}
.tw-colophon .col-tags{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin-top:22px}
.tw-colophon .col-tags-label{font-family:var(--mono);font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--cf);margin-right:6px}
.tw-colophon .col-tags a{font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;white-space:nowrap;color:var(--cm);border:1px solid var(--cr2);border-radius:999px;padding:5px 13px;transition:color .18s ease,border-color .18s ease}
.tw-colophon .col-tags a:hover{color:var(--cacc);border-color:var(--cacc)}
.tw-colophon .col-t3{position:relative;z-index:1;display:flex;flex-direction:column;gap:24px;padding:50px 0 56px}
.tw-colophon .col-signoff{position:relative;z-index:2;font-family:var(--serif);font-style:italic;font-size:15px;line-height:1.5;color:var(--ci2);margin:0;max-width:30ch}
.tw-colophon .col-bar{position:relative;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}
.tw-colophon .col-bar-l{display:flex;align-items:center;gap:18px;flex-wrap:wrap;font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--cf)}
.tw-colophon .col-bar-l .col-strong{color:var(--ci2)}
.tw-colophon .col-dot{width:3px;height:3px;border-radius:50%;background:var(--cf)}
.tw-colophon .col-chosen{display:inline-flex;align-items:center;gap:6px}
.tw-colophon .col-chosen .col-dia{color:var(--cacc)}
.tw-colophon .col-bar-r{display:flex;align-items:center;gap:20px;font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--cm)}
.tw-colophon .col-bar-r a{color:var(--cm)}
.tw-colophon .col-bar-r a:hover{color:var(--cacc)}
.tw-colophon .col-bar-r .col-vr{width:1px;height:12px;background:var(--cr)}
.tw-colophon .col-bar-r .col-handle{color:var(--ci2)}
@media(max-width:860px){
  .tw-colophon .col-t1{flex-direction:column;align-items:flex-start;gap:34px}
  .tw-colophon .col-bar{flex-direction:column;align-items:flex-start;gap:18px}
  .tw-colophon .col-ghost{font-size:23vw}
  .tw-colophon .col-inner{padding:0 24px}
}
"""


def render_colophon(*, prefix="", mark_url=None, primary=None, meta=None, tags=None,
                    signoff="", stats="", copyright="© 2013–2026 Token Wisdom",
                    subscribe_url="#", socials=None, handle="@iamkhayyam",
                    eyebrow="The Newsletter of Record · Est. 2013",
                    headline="A field guide to the future of now.",
                    sub_label="One weekly transmission · Humanly chosen"):
    """Render the dark site colophon. Data-driven so the static site and the CMS
    both feed it real links/tags/counts."""
    mark_url = mark_url if mark_url is not None else (prefix + "assets/crystal-ball.svg")
    primary, meta, tags, socials = primary or [], meta or [], tags or [], socials or []

    def _a(it, cls=""):
        ext = ' target="_blank" rel="noopener"' if it.get("external") else ""
        return f'<a href="{esc(it["href"])}"{ext}>{esc(it["label"])}</a>'

    primary_html = "".join(_a(i) for i in primary)
    meta_html = "".join(_a(i) for i in meta)
    tags_html = "".join(f'<a href="{esc(t["href"])}">{esc(t["name"])}</a>' for t in tags)
    social_html = "".join(f'<a href="{esc(s["href"])}" target="_blank" rel="noopener">{esc(s["label"])}</a>' for s in socials)
    tags_block = (f'<div class="col-tags"><span class="col-tags-label">Popular tags</span>{tags_html}</div>'
                  if tags else "")
    return f"""
<footer class="tw-colophon">
  <div class="col-inner">
    <div class="col-ghost-wrap"><div class="col-ghost">Token Wisdom</div></div>

    <div class="col-t1">
      <div class="col-pitch">
        <div class="col-eyebrow"><img src="{esc(mark_url)}" alt=""><span>{esc(eyebrow)}</span></div>
        <h2 class="col-h2">{esc(headline)}</h2>
      </div>
      <div class="col-sub">
        <div class="col-sub-label">{esc(sub_label)}</div>
        <form class="col-subform" action="{esc(subscribe_url)}" method="get" onsubmit="window.location.href='{esc(subscribe_url)}';return false">
          <input type="email" name="email" placeholder="you@future.now" aria-label="Email address">
          <button type="submit">Subscribe &rarr;</button>
        </form>
      </div>
    </div>

    <div class="col-t2">
      <div class="col-links">{primary_html}</div>
      <div class="col-meta">{meta_html}</div>
      {tags_block}
    </div>

    <div class="col-t3">
      <p class="col-signoff">{esc(signoff)}</p>
      <div class="col-bar">
        <div class="col-bar-l">
          <span class="col-strong">{esc(copyright)}</span>
          <span class="col-dot"></span><span>{esc(stats)}</span>
          <span class="col-dot"></span><span class="col-chosen"><span class="col-dia">◆</span>100% Humanly Chosen</span>
        </div>
        <div class="col-bar-r">
          {social_html}
          <span class="col-vr"></span><span class="col-handle">{esc(handle)}</span>
        </div>
      </div>
    </div>
  </div>
</footer>"""

_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900'
    '&family=Libre+Caslon+Display&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;'
    '0,8..60,500;0,8..60,600;1,8..60,300;1,8..60,400&display=swap" rel="stylesheet">'
)


# ============================================================
# RENDERER
# ============================================================

def esc(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def _kicker(doc: EssayDoc) -> str:
    parts = [doc.section]
    if doc.week is not None:
        parts.append(f"Week {int(doc.week):02d}")
    if doc.topic:
        parts.append(doc.topic)
    return " · ".join(p for p in parts if p)


def render_essay_inner(doc: EssayDoc) -> str:
    """The essay markup (toggle + top bar + article). No <html>/<head>; embed
    this inside a host page, or call render_essay() for a full document."""

    # cover
    cover = ""
    if doc.cover_image:
        cover = (f'\n  <figure class="essay-cover">'
                 f'<img src="{esc(doc.cover_image)}" alt="{esc(doc.cover_alt or doc.title)}" loading="eager">'
                 f'<figcaption>{esc(doc.cover_caption)}</figcaption></figure>')

    dek = f'\n    <p class="essay-deck">{esc(doc.dek)}</p>' if doc.dek else ""

    byline_bits = [f'<span class="by">By {esc(doc.author)}</span>']
    if doc.reading_time:
        byline_bits += ['<span class="sep">·</span>', f"<span>{esc(doc.reading_time)}</span>"]
    if doc.date:
        byline_bits += ['<span class="sep">·</span>', f"<span>{esc(doc.date)}</span>"]
    byline = "".join(byline_bits)

    epigraph = ""
    if doc.epigraph_quote:
        cite = f'<cite>{esc(doc.epigraph_cite)}</cite>' if doc.epigraph_cite else ""
        epigraph = (f'\n  <div class="essay-epigraph essay-col">'
                    f'<p>&ldquo;{esc(doc.epigraph_quote)}&rdquo;</p>{cite}</div>')

    body = mark_lede(sanitize_body(doc.body_html))

    # footer
    if doc.edition_number:
        ed_bits = [f"No. {doc.edition_number}"]
        if doc.edition_week:
            ed_bits.append(f"Week {int(doc.edition_week):02d}")
        edition_line = "🔮 " + doc.brand + " · " + " · ".join(ed_bits)
        back_href = doc.edition_url or "#"
        back_label = "Back to this week's edition →"
    else:
        edition_line = "🔮 " + doc.brand + " · " + doc.section
        back_href = doc.edition_url or "#"
        back_label = "Back to the edition →"
    footer = (f'\n  <footer class="essay-foot essay-col">'
              f'<span class="ef-edition">{esc(edition_line)}</span>'
              f'<a class="ef-back" href="{esc(back_href)}">{back_label}</a></footer>')

    # top bar
    topbar = ""
    if doc.brand or doc.back_label:
        mark = (f'<img src="{esc(doc.brand_mark_url)}" alt="">'
                if doc.brand_mark_url else "")
        back = ""
        if doc.back_label:
            back = (f'<span class="sep">/</span>'
                    f'<a class="back" href="{esc(doc.back_url or "#")}">{esc(doc.back_label)}</a>')
        topbar = (f'\n<div class="essay-topbar"><div class="essay-topbar-inner">'
                  f'<a class="brand" href="{esc(doc.back_url or "#")}">{mark}'
                  f'<span class="brand-name">{esc(doc.brand)}</span></a>{back}</div></div>')

    toggle = ('<button class="theme-toggle" onclick="window.__twToggleTheme()" '
              'aria-label="Toggle dark mode"><span class="tt-glyph">☾</span>'
              '<span class="tt-label">Dark</span></button>')

    return f"""{_THEME_SCRIPT}{toggle}{topbar}
<article class="essay-frame">{cover}
  <header class="essay-head essay-col">
    <div class="essay-eyebrow">{esc(_kicker(doc))}</div>
    <h1 class="essay-title">{esc(doc.title)}</h1>{dek}
    <div class="essay-byline">{byline}</div>
  </header>{epigraph}
  <div class="essay-body">
    <div class="prose">
      {body}
    </div>
  </div>{footer}
</article>{INDEX_MARKUP}{INDEX_SCRIPT}{_sample_colophon(doc)}"""


def _sample_colophon(doc: EssayDoc) -> str:
    """Illustrative site colophon for the standalone CMS reference page."""
    nav = ["Home", "Archive", "All Topics", "The Lexicon", "Essays", "Newsletters", "Podcast"]
    meta = ["About", "Links", "Corpus Report", "Ghost", "GitHub Archive"]
    tags = ["Deep Tech", "Creative \\ Design", "Cyber \\ Security", "Culture Club",
            "Content Creation", "Economic ≠"]
    return render_colophon(
        mark_url=doc.brand_mark_url,
        primary=[{"label": n, "href": "#"} for n in nav],
        meta=[{"label": m, "href": "#"} for m in meta],
        tags=[{"name": t, "href": "#"} for t in tags],
        signoff="Until next time: stay smart, and kind, and definitely stay weird.",
        stats="267 Posts · 85 Tags",
        copyright="© 2013–2026 Token Wisdom",
        subscribe_url="#",
        socials=[{"label": "X", "href": "#"}, {"label": "LinkedIn", "href": "#"},
                 {"label": "RSS", "href": "#"}],
        handle="@iamkhayyam",
    )


def render_essay(doc: EssayDoc) -> str:
    """Full standalone HTML document for the essay (CMS-ready)."""
    inner = render_essay_inner(doc)
    if not doc.standalone:
        return inner
    theme_attr = f' data-theme="{esc(doc.theme)}"' if doc.theme and doc.theme != "light" else ""
    canonical = (f'<link rel="canonical" href="{esc(doc.canonical_url)}">'
                 if doc.canonical_url else "")
    return f"""<!DOCTYPE html>
<html lang="en"{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(doc.title)} — {esc(doc.brand)}</title>
{canonical}
{_FONT_LINK}
<style>{_css(doc.font_dir)}</style>
{doc.extra_head}
</head>
<body>
{inner}
{doc.extra_body_end}
</body>
</html>"""


# ============================================================
# WORKED EXAMPLE — `python3 essay_template.py`
# ============================================================

def _sample_doc() -> EssayDoc:
    """Build the canonical example from the real Sky essay body, so the example
    page also demonstrates the captivate-embed repair on actual broken content."""
    content_path = ROOT / "posts" / "the-sky-has-been-warning-us-since-1859" / "content.html"
    body = content_path.read_text() if content_path.exists() else "<p>Body goes here.</p>"
    body = demo_margin_notes(body)  # showcase the margin apparatus on real content
    return EssayDoc(
        title="The Sky Has Been Warning Us Since 1859",
        body_html=body,
        week=13,
        topic="Infrastructure",
        cover_image="https://tokenwisdom.ghost.io/content/images/2026/03/ideogram-prompt-new-yorker-cover-illustr_CCxDPWrHTWCD3IyQ2thcNw_wwIrcdfyRmiLefFLP85_0w_sd.jpeg",
        cover_caption="Sept. 1, 1859 — the operator stays at his key as the line runs hot. Illustration · Token Wisdom",
        dek=("The sun fired a warning shot in 1859. We had 165 years. We wrote reports, "
             "introduced legislation, held hearings — and kept building a bigger antenna."),
        author="🌶️ @iamkhayyam",
        date="March 26, 2026",
        reading_time="9 min read",
        epigraph_quote="Whatever can happen will happen if we make trials enough.",
        epigraph_cite="Augustus De Morgan · A Budget of Paradoxes, 1872",
        edition_number=153,
        edition_week=23,
        edition_url="issues/153/",
        issue_code="ACL.153 · W13 · Mar 26, 2026",
        back_label="← Back to Issue 153",
        back_url="issues/153/",
    )


def main():
    doc = _sample_doc()
    out = ROOT / "docs" / "essay-template.html"
    out.write_text(render_essay(doc))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

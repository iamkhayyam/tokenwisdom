#!/usr/bin/env python3
"""
render_issue.py — render an Issue object into the canonical of-record web page.

One render of the Issue object (data/issues/*.json, see issue.schema.json).
Email, social, and feed are separate renders of the SAME json — this is the
web one: docs/issues/{number}/index.html, the permanent "of record" page.

Reuses tw_theme (masthead/footer/tokens) and generate_links' card() so the
link rails are identical to the Reading Room.

Usage:
  python3 render_issue.py data/issues/2026-W23.json
"""

import json
import sys
from datetime import date
from pathlib import Path

from tw_theme import page
from generate_links import LINKS_CSS, card, esc

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


ISSUE_CSS = """
.issue-head{border-bottom:2px solid var(--ink);padding:2.6rem 0 1.6rem;margin-bottom:.4rem}
.issue-kicker{font-family:var(--mono);font-weight:300;font-size:.66rem;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:1rem}
.issue-head-grid{display:grid;grid-template-columns:auto 1fr;gap:1.8rem;align-items:start}
.issue-no{font-family:var(--display);font-weight:400;font-size:clamp(3.4rem,11vw,7rem);line-height:.82;letter-spacing:-.03em;color:var(--ink)}
.issue-no small{display:block;font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-faint);margin-top:.6rem}
.issue-title{font-family:var(--display);font-weight:400;font-size:clamp(1.7rem,4.2vw,2.8rem);line-height:1.02;letter-spacing:-.02em;color:var(--ink)}
.issue-dek{font-family:var(--serif);font-optical-sizing:none;font-variation-settings:'opsz' 18;font-size:1.12rem;line-height:1.5;color:var(--ink-muted);margin-top:.8rem;max-width:54ch}
.issue-date{font-family:var(--mono);font-weight:300;font-size:.64rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);margin-top:1rem}
@media(max-width:620px){.issue-head-grid{grid-template-columns:1fr;gap:.9rem}}

/* Essay feature */
.issue-essay{display:grid;grid-template-columns:1.1fr 1fr;gap:2rem;align-items:center;margin:2.6rem 0;padding:0 0 2.4rem;border-bottom:1px solid var(--rule)}
.issue-essay-media{display:block;width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:5px;background:var(--rule)}
.issue-essay-kicker{font-family:var(--mono);font-weight:300;font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin-bottom:.7rem}
.issue-essay-title{font-family:var(--display);font-weight:400;font-size:clamp(1.6rem,3.6vw,2.4rem);line-height:1.04;letter-spacing:-.02em;color:var(--ink)}
.issue-essay-title a{color:var(--ink)} .issue-essay-title a:hover{color:var(--accent)}
.issue-essay-excerpt{font-family:var(--serif);font-optical-sizing:none;font-variation-settings:'opsz' 18;font-size:1rem;line-height:1.55;color:var(--ink-muted);margin-top:.8rem}
.issue-essay-cta{display:inline-block;margin-top:1.1rem;font-family:var(--mono);font-weight:300;font-size:.66rem;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);border:.5px solid var(--accent);border-radius:3px;padding:.55rem 1rem}
.issue-essay-cta:hover{background:var(--accent);color:var(--surface)}
@media(max-width:680px){.issue-essay{grid-template-columns:1fr;gap:1.1rem}}

/* Terms in motion */
.terms-wrap{margin:2.6rem 0;padding-bottom:2.2rem;border-bottom:1px solid var(--rule)}
.terms-row{display:flex;flex-wrap:wrap;gap:.7rem;margin-top:1.3rem}
.term-chip{flex:1 1 220px;min-width:200px;display:block;color:var(--ink);border:1px solid var(--rule);border-left:3px solid var(--accent);border-radius:3px;padding:.8rem .95rem;background:var(--surface);transition:border-color .2s,transform .2s}
.term-chip:hover{transform:translateY(-2px);color:var(--ink)}
.term-chip-top{display:flex;align-items:baseline;justify-content:space-between;gap:.6rem}
.term-chip-name{font-family:var(--display);font-weight:400;font-size:1.15rem;color:var(--ink)}
.term-chip-mentions{font-family:var(--mono);font-weight:300;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);white-space:nowrap}
.term-chip-meta{font-family:var(--mono);font-weight:300;font-size:.56rem;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:.35rem 0 .45rem}
.term-chip-def{font-family:var(--serif);font-size:.82rem;line-height:1.4;color:var(--ink-muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

/* From the record */
.record{display:flex;gap:1.1rem;align-items:flex-start;margin:2.4rem 0;padding:1.3rem 1.4rem;background:var(--surface);border:1px solid var(--rule);border-radius:4px}
.record-ed{font-family:var(--display);font-weight:400;font-size:2rem;line-height:.9;color:var(--accent);white-space:nowrap}
.record-ed small{display:block;font-family:var(--mono);font-weight:300;font-size:.52rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-faint);margin-top:.3rem}
.record-reason{font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:.3rem}
.record-title{font-family:var(--serif);font-size:1.05rem;line-height:1.35;color:var(--ink)}
.record-title a{color:var(--ink)} .record-title a:hover{color:var(--accent)}

.section-head{display:flex;align-items:baseline;gap:1rem;border-top:2px solid var(--ink);padding-top:.8rem;margin:2.4rem 0 1.3rem}
.section-head h2{font-family:var(--display);font-weight:400;font-size:1.5rem;color:var(--ink)}
.section-head .badge{margin-left:auto;font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
"""


def fmt_date(iso):
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return f"{MONTHS[m]} {d}, {y}"
    except Exception:
        return iso or ""


def render_report(issue):
    cells = "".join(
        f'<div><div class="rr-stat-num">{esc(str(r["value"]))}</div>'
        f'<div class="rr-stat-lbl">{esc(r["label"])}</div></div>'
        for r in issue.get("report", [])
    )
    return f'<div class="rr-stats">{cells}</div>' if cells else ""


def render_essay(essay):
    if not essay:
        return ""
    media = (f'<img class="issue-essay-media" src="{esc(essay["feature_image"])}" alt="" loading="lazy">'
             if essay.get("feature_image") else '<div class="issue-essay-media"></div>')
    excerpt = (f'<p class="issue-essay-excerpt">{esc(essay["excerpt"])}</p>'
               if essay.get("excerpt") else "")
    return f"""
<section class="issue-essay">
  <a href="{esc(essay['url'])}">{media}</a>
  <div>
    <div class="issue-essay-kicker">The closer look</div>
    <h2 class="issue-essay-title"><a href="{esc(essay['url'])}">{esc(essay['title'])}</a></h2>
    {excerpt}
    <a class="issue-essay-cta" href="{esc(essay['url'])}">Read the essay &rarr;</a>
  </div>
</section>"""


def render_rail(label, badge, items):
    if not items:
        return ""
    cards = "".join(card(i, "tnl" if label == "The Newest Latest" else "tws") for i in items)
    return f"""
<div class="section-head">
  <h2>{esc(label)}</h2>
  <span class="badge">{esc(badge)}</span>
</div>
<div class="rr-grid">{cards}</div>"""


def render_terms(terms):
    if not terms:
        return ""
    chips = ""
    for t in terms:
        color = t.get("color") or "accent"
        accent = f"var(--{color})" if color in ("teal", "gold", "accent") else "var(--accent)"
        role = t.get("role") or "Term"
        meta = f"{role} · {t.get('edition_count', 0)} editions"
        chips += f"""
<a class="term-chip" href="{esc(t['url'])}" style="border-left-color:{accent}">
  <div class="term-chip-top">
    <span class="term-chip-name">{esc(t['name'])}</span>
    <span class="term-chip-mentions">{t.get('mentions', 0)}&times; this week</span>
  </div>
  <div class="term-chip-meta" style="color:{accent}">{esc(meta)}</div>
  <div class="term-chip-def">{esc(t.get('definition', ''))}</div>
</a>"""
    return f"""
<section class="terms-wrap">
  <div class="section-head"><h2>Terms in motion</h2>
    <span class="badge">From the Lexicon</span></div>
  <div class="terms-row">{chips}</div>
</section>"""


def render_record(rec):
    if not rec:
        return ""
    ed = rec.get("edition")
    ed_block = (f'<div class="record-ed">{ed}<small>edition</small></div>'
                if ed else "")
    title = esc(rec.get("title", ""))
    if rec.get("url"):
        title = f'<a href="{esc(rec["url"])}">{title}</a>'
    return f"""
<section class="record">
  {ed_block}
  <div>
    <div class="record-reason">{esc(rec.get('reason', 'From the record'))}</div>
    <div class="record-title">{title}</div>
  </div>
</section>"""


def build(issue_path):
    issue = json.loads(Path(issue_path).read_text())
    number = issue.get("number")
    slug = str(number) if number else issue["id"]

    title = issue.get("title") or f"Token Wisdom · {issue['id']}"
    essay = issue.get("essay") or {}
    head_title = (essay.get("title") or title) if essay else title
    badge = f"{issue['year']} · W{issue['week']:02d}"

    body = f"""
<style>{LINKS_CSS}{ISSUE_CSS}</style>
<div class="wrap" style="padding-bottom:4rem">
  <header class="issue-head">
    <div class="issue-kicker">The Record · Token Wisdom</div>
    <div class="issue-head-grid">
      <div class="issue-no">{('No. ' + str(number)) if number else badge}
        <small>{badge}</small></div>
      <div>
        <h1 class="issue-title">{esc(head_title)}</h1>
        {('<p class="issue-dek">' + esc(issue['dek']) + '</p>') if issue.get('dek') else ''}
        <div class="issue-date">{fmt_date(issue.get('date',''))}</div>
      </div>
    </div>
  </header>

  {render_report(issue)}
  {render_essay(essay)}
  {render_rail("The Newest Latest", badge, issue['sections'].get('newest_latest', []))}
  {render_rail("Time Well Spent", badge, issue['sections'].get('time_well_spent', []))}
  {render_terms(issue.get('terms_in_motion', []))}
  {render_record(issue.get('from_the_record'))}
</div>"""

    out_dir = DOCS / "issues" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    # /issues/{slug}/ is two levels deep → prefix "../../"
    html = page(f"{title} — Token Wisdom", body, prefix="../../", active="")
    (out_dir / "index.html").write_text(html)
    return out_dir / "index.html"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: python3 render_issue.py data/issues/2026-W23.json")
        sys.exit(1)
    out = build(args[0])
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

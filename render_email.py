#!/usr/bin/env python3
"""
render_email.py — render an Issue object into a sendable HTML email.

The email render of the Issue object (data/issues/*.json). Same source as the
web page (render_issue.py); different surface. Email-safe: table layout, inline
styles, web-safe font fallbacks, hosted images, vertical lists (no horizontal
scroll), bulletproof button, hidden preheader, CAN-SPAM footer.

Hand to Resend as the `html` of a broadcast/email. Unsubscribe uses Resend's
merge tag {{{unsubscribe_url}}} (managed list) — leave as-is when sending.

Usage:
  python3 render_email.py data/issues/2026-W23.json
  python3 render_email.py data/issues/2026-W23.json --per-rail 6
"""

import argparse
import json
from pathlib import Path

from generate_links import esc
from tw_theme import GHOST_URL

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
SITE = "https://tokenwisdom.org"

# Brand palette, converted from tw_theme's OKLCH tokens to email-safe hex.
C = {
    "bg": "#FEFCFA", "surface": "#F8F5F2", "ink": "#221D18",
    "ink_muted": "#6A635E", "ink_faint": "#97918C", "rule": "#E2DFDB",
    "accent": "#C35812", "accent_deep": "#993A00",
    "teal": "#2F7675", "gold": "#BA9A56",
}
SERIF = "Georgia, 'Times New Roman', serif"          # display + body serif
SANS = "Arial, Helvetica, sans-serif"
MONO = "'Courier New', Courier, monospace"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

HEAD_STYLE = """
<style>
  body,table,td{margin:0;padding:0;}
  img{border:0;line-height:100%;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic;}
  a{text-decoration:none;}
  @media only screen and (max-width:600px){
    .container{width:100%!important;}
    .px{padding-left:20px!important;padding-right:20px!important;}
    .stack{display:block!important;width:100%!important;}
    .thumb{width:100%!important;height:auto!important;}
    .hero{height:auto!important;}
  }
  @media (prefers-color-scheme:dark){
    .bg{background:#1B1611!important;}
    .card{background:#221D18!important;}
    .ink{color:#F3EFEA!important;}
    .muted{color:#B6AFA8!important;}
    .rule{border-color:#3A332D!important;}
  }
</style>
"""


def fmt_date(iso):
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return f"{MONTHS[m]} {d}, {y}"
    except Exception:
        return iso or ""


def button(text, url):
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
  <td bgcolor="{C['accent']}" style="border-radius:4px;">
    <a href="{esc(url)}" style="display:inline-block;padding:12px 22px;font-family:{MONO};
       font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:#ffffff;">{text}</a>
  </td>
</tr></table>"""


def kicker(text, color=None):
    return (f'<div style="font-family:{MONO};font-size:11px;letter-spacing:2px;'
            f'text-transform:uppercase;color:{color or C["accent"]};">{esc(text)}</div>')


def section_head(label, badge):
    return f"""
<tr><td class="px" style="padding:28px 40px 8px;border-top:2px solid {C['ink']};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="font-family:{SERIF};font-size:22px;color:{C['ink']};" class="ink">{esc(label)}</td>
    <td align="right" style="font-family:{MONO};font-size:11px;letter-spacing:1.5px;
        text-transform:uppercase;color:{C['accent']};">{esc(badge)}</td>
  </tr></table>
</td></tr>"""


def link_row(item):
    cover = item.get("cover")
    thumb = (f'<img class="thumb" src="{esc(cover)}" width="120" alt="" '
             f'style="display:block;width:120px;border-radius:3px;">'
             if cover else
             f'<div class="thumb" style="width:120px;height:72px;background:{C["rule"]};border-radius:3px;"></div>')
    src = esc(item.get("source", ""))
    kind = "Video" if item.get("kind") == "video" else "Article"
    excerpt = esc((item.get("excerpt") or "")[:140])
    excerpt_html = (f'<div class="muted" style="font-family:{SERIF};font-size:13px;line-height:1.45;'
                    f'color:{C["ink_muted"]};margin-top:4px;">{excerpt}</div>' if excerpt else "")
    return f"""
<tr><td class="px" style="padding:14px 40px;border-bottom:1px solid {C['rule']};" class="rule">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td class="stack" width="120" valign="top" style="padding-right:14px;">
      <a href="{esc(item['url'])}">{thumb}</a>
    </td>
    <td class="stack" valign="top">
      <div style="font-family:{MONO};font-size:10px;letter-spacing:1.5px;text-transform:uppercase;
          color:{C['ink_faint']};margin-bottom:3px;">{kind} &middot; {src}</div>
      <a href="{esc(item['url'])}" class="ink" style="font-family:{SANS};font-size:15px;font-weight:bold;
         line-height:1.3;color:{C['ink']};">{esc(item['title'])}</a>
      {excerpt_html}
    </td>
  </tr></table>
</td></tr>"""


def rail(label, badge, items, per_rail, reading_room=True):
    if not items:
        return ""
    shown = items[:per_rail]
    rows = "".join(link_row(i) for i in shown)
    more = ""
    if reading_room and len(items) > per_rail:
        more = f"""
<tr><td class="px" style="padding:12px 40px 0;">
  <a href="{SITE}/links/" style="font-family:{MONO};font-size:11px;letter-spacing:1px;
     text-transform:uppercase;color:{C['accent']};">+ {len(items)-per_rail} more in the Reading Room &rarr;</a>
</td></tr>"""
    return section_head(label, badge) + rows + more


def term_row(t):
    color = {"teal": C["teal"], "gold": C["gold"], "accent": C["accent"]}.get(t.get("color"), C["accent"])
    meta = f"{t.get('role') or 'Term'} &middot; {t.get('edition_count', 0)} editions &middot; {t.get('mentions', 0)}&times; this week"
    defn = esc((t.get("definition") or "")[:120])
    return f"""
<tr><td class="px" style="padding:0 40px 10px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         class="card" style="background:{C['surface']};border-radius:4px;"><tr>
    <td width="4" style="background:{color};border-radius:4px 0 0 4px;">&nbsp;</td>
    <td style="padding:12px 16px;">
      <a href="{esc(t['url'])}" class="ink" style="font-family:{SERIF};font-size:18px;color:{C['ink']};">{esc(t['name'])}</a>
      <div style="font-family:{MONO};font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{color};margin:4px 0 5px;">{meta}</div>
      <div class="muted" style="font-family:{SERIF};font-size:13px;line-height:1.4;color:{C['ink_muted']};">{defn}</div>
    </td>
  </tr></table>
</td></tr>"""


def render_terms(terms):
    if not terms:
        return ""
    return section_head("Terms in motion", "From the Lexicon") + \
        '<tr><td style="height:14px;line-height:14px;">&nbsp;</td></tr>' + \
        "".join(term_row(t) for t in terms)


def render_record(rec):
    if not rec:
        return ""
    ed = rec.get("edition")
    ed_cell = (f'<td width="64" valign="top" style="font-family:{SERIF};font-size:34px;'
               f'color:{C["accent"]};line-height:1;">{ed}</td>' if ed else "")
    title = esc(rec.get("title", ""))
    if rec.get("url"):
        title = f'<a href="{esc(rec["url"])}" class="ink" style="color:{C["ink"]};">{title}</a>'
    return f"""
<tr><td class="px" style="padding:24px 40px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="card"
         style="background:{C['surface']};border-radius:4px;"><tr>
    <td style="padding:18px 20px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
        {ed_cell}
        <td valign="top">
          <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;text-transform:uppercase;
              color:{C['ink_muted']};margin-bottom:4px;">{esc(rec.get('reason','From the record'))}</div>
          <div style="font-family:{SERIF};font-size:16px;line-height:1.35;color:{C['ink']};" class="ink">{title}</div>
        </td>
      </tr></table>
    </td>
  </tr></table>
</td></tr>"""


def render_essay(essay):
    if not essay:
        return ""
    hero = (f'<a href="{esc(essay["url"])}"><img class="hero" src="{esc(essay["feature_image"])}" '
            f'width="520" alt="{esc(essay.get("title",""))}" '
            f'style="display:block;width:100%;max-width:520px;border-radius:5px;"></a>'
            if essay.get("feature_image") else "")
    excerpt = esc((essay.get("excerpt") or "")[:240])
    excerpt_html = (f'<p class="muted" style="font-family:{SERIF};font-size:15px;line-height:1.55;'
                    f'color:{C["ink_muted"]};margin:10px 0 16px;">{excerpt}</p>' if excerpt else "")
    return f"""
<tr><td class="px" style="padding:26px 40px 6px;">{hero}</td></tr>
<tr><td class="px" style="padding:16px 40px 26px;border-bottom:1px solid {C['rule']};" class="rule">
  {kicker('The closer look')}
  <h2 class="ink" style="font-family:{SERIF};font-size:26px;line-height:1.1;color:{C['ink']};margin:8px 0 0;font-weight:normal;">
    <a href="{esc(essay['url'])}" class="ink" style="color:{C['ink']};">{esc(essay['title'])}</a></h2>
  {excerpt_html}
  {button('Read the essay &rarr;', essay['url'])}
</td></tr>"""


def render_report(issue):
    cells = ""
    for r in issue.get("report", [])[:4]:
        cells += f"""
<td class="stack" valign="top" style="padding-right:24px;">
  <div style="font-family:{SERIF};font-size:24px;color:{C['ink']};" class="ink">{esc(str(r['value']))}</div>
  <div style="font-family:{MONO};font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{C['ink_faint']};margin-top:3px;">{esc(r['label'])}</div>
</td>"""
    if not cells:
        return ""
    return f"""
<tr><td class="px" style="padding:18px 40px;border-bottom:1px solid {C['rule']};" class="rule">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>{cells}</tr></table>
</td></tr>"""


def build(issue_path, per_rail=6):
    issue = json.loads(Path(issue_path).read_text())
    number = issue.get("number")
    slug = str(number) if number else issue["id"]
    badge = f"{issue['year']} · W{issue['week']:02d}"
    essay = issue.get("essay") or {}
    issue_url = issue.get("url") or f"{SITE}/issues/{slug}"
    preheader = issue.get("dek") or essay.get("excerpt") or "The Newsletter of Record for the Future of Now."
    headline = "No. " + str(number) if number else f"Token Wisdom · {badge}"

    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{esc(headline)} — Token Wisdom</title>
{HEAD_STYLE}
</head>
<body class="bg" style="margin:0;padding:0;background:{C['bg']};">
<span style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;mso-hide:all;">{esc(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="bg" style="background:{C['bg']};"><tr>
<td align="center" style="padding:24px 0;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" class="container card"
       style="width:600px;max-width:600px;background:{C['bg']};">

  <tr><td class="px" align="center" style="padding:8px 40px 0;">
    <a href="{issue_url}" style="font-family:{MONO};font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:{C['ink_faint']};">View in browser</a>
  </td></tr>

  <tr><td class="px" style="padding:14px 40px 18px;border-bottom:2px solid {C['ink']};">
    {kicker('The Record · Token Wisdom')}
    <div class="ink" style="font-family:{SERIF};font-size:46px;letter-spacing:-1px;color:{C['ink']};margin-top:8px;">{esc(headline)}</div>
    <div style="font-family:{MONO};font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{C['ink_faint']};margin-top:8px;">{badge} &middot; {fmt_date(issue.get('date',''))}</div>
  </td></tr>

  {render_report(issue)}
  {render_essay(essay)}
  {rail('The Newest Latest', badge, issue['sections'].get('newest_latest', []), per_rail)}
  {rail('Time Well Spent', badge, issue['sections'].get('time_well_spent', []), per_rail)}
  {render_terms(issue.get('terms_in_motion', []))}
  {render_record(issue.get('from_the_record'))}

  <tr><td class="px" align="center" style="padding:30px 40px;border-top:2px solid {C['ink']};">
    <div class="ink" style="font-family:{SERIF};font-size:20px;color:{C['ink']};">Token Wisdom</div>
    <div class="muted" style="font-family:{SERIF};font-size:13px;color:{C['ink_muted']};margin-top:6px;">The Newsletter of Record for the Future of Now</div>
    <div style="margin-top:14px;">{button('Subscribe', GHOST_URL + '/subscribe')}</div>
    <div style="font-family:{MONO};font-size:10px;letter-spacing:.5px;color:{C['ink_faint']};margin-top:20px;line-height:1.6;">
      Token Wisdom · [mailing address] · You received this because you subscribed.<br>
      <a href="{{{{{{unsubscribe_url}}}}}}" style="color:{C['ink_faint']};text-decoration:underline;">Unsubscribe</a>
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""

    out_dir = DOCS / "issues" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "email.html"
    out.write_text(body)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("issue")
    ap.add_argument("--per-rail", type=int, default=6)
    a = ap.parse_args()
    out = build(a.issue, a.per_rail)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

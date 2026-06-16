#!/usr/bin/env python3
"""
render_email.py — render an Issue object into a sendable HTML email.

Implements the Claude Design "Token Wisdom - Email Issue 153" handoff: a fully
editorial, inbox-safe layout (600px tables, Georgia/Helvetica/Courier, single
column) driven by the real Issue object (data/issues/*.json, see issue.schema).

Sections: masthead · epigraph · editor's note · Newest/Latest (numbered) ·
A Closer Look (dark essay card) · Time Well Spent (numbered) · Knowledge,
Transmuted · The Less You Know (category-tiered Lexicon) · colophon.

Hand to Resend as the `html` of a broadcast. Unsubscribe uses Resend's merge
tag {{{unsubscribe_url}}} — leave as-is when sending.

Usage:
  python3 render_email.py data/issues/2026-W23.json
"""

import argparse
import json
import textwrap
from pathlib import Path

from generate_links import esc
from tw_theme import GHOST_URL

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
SITE = "https://tokenwisdom.org"

# Palette from the design (warm paper editorial).
BG = "#cfccc4"          # outer
PAPER = "#f7f4ee"       # email body
RULE = "#ddd7cc"        # hairline
INK = "#1e1a15"         # darkest / headings
INK2 = "#2a251e"        # body ink
MUTED = "#5d564b"       # notes / defs
FAINT = "#8e857a"       # labels
FAINT2 = "#a89f90"      # colophon faint
NUM = "#c4bdb0"         # big numerals
ACCENT = "#8f3d14"      # rust
# dark "Closer Look" card
DARK = "#1e1a15"
DARK_ACCENT = "#d98a4e"
DARK_TITLE = "#f1ece2"
DARK_PULL = "#cbb9a6"
DARK_DEK = "#b8ab9c"

SERIF = "Georgia,'Times New Roman',serif"
SANS = "Helvetica,Arial,sans-serif"
MONO = "'Courier New',Courier,monospace"

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
CAT_ORDER = ["Technologies", "Concepts", "Technical Terms", "Acronyms", "People & Works"]

HEAD = """
<style>
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  img{border:0;outline:none;display:block}
  a{text-decoration:none}
  @media only screen and (max-width:600px){
    .container{width:100%!important}
    .px{padding-left:24px!important;padding-right:24px!important}
  }
</style>
"""


def fmt_date(iso):
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return f"{MONTHS[m]} {d}, {y}"
    except Exception:
        return iso or ""


def rule_table(inner):
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'border="0" width="100%">{inner}</table>')


def section_title(label, badge=None):
    badge_cell = (f'<td align="right" style="font-family:{MONO};font-size:10px;'
                  f'letter-spacing:1.5px;text-transform:uppercase;color:{ACCENT};'
                  f'text-align:right;vertical-align:bottom">{esc(badge)}</td>' if badge else "")
    return f"""
<tr><td style="padding:34px 0 4px;border-top:3px solid {INK}">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
    <td style="font-family:{SERIF};font-size:30px;letter-spacing:-1px;color:{INK}">{esc(label)}</td>
    {badge_cell}
  </tr></table>
</td></tr>"""


def numbered_item(i, item, verb):
    num = f"{i + 1:02d}"
    note = esc(item.get("excerpt") or "")
    note_html = (f'<div style="font-family:{SERIF};font-size:15px;line-height:1.5;'
                 f'color:{MUTED};margin-bottom:11px">{note}</div>' if note else "")
    play = "▶ " if verb == "Watch" else ""
    src = esc(item.get("source", ""))
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-top:1px solid {RULE}">
  <tr>
    <td width="50" style="width:50px;vertical-align:top;padding:20px 16px 20px 0;font-family:{SERIF};font-size:30px;line-height:1;color:{NUM}">{num}</td>
    <td style="vertical-align:top;padding:20px 0">
      <a href="{esc(item['url'])}" style="font-family:{SANS};font-weight:bold;font-size:19px;line-height:1.22;color:{INK};display:block;margin-bottom:7px">{esc(item['title'])}</a>
      {note_html}
      <div style="font-family:{MONO};font-size:10.5px;letter-spacing:1.5px;text-transform:uppercase;color:{ACCENT}">{play}{src} &nbsp;—&nbsp; <a href="{esc(item['url'])}" style="color:{ACCENT}">{verb} →</a></div>
    </td>
  </tr>
</table>"""


def render_rail(label, items, verb, badge):
    if not items:
        return ""
    rows = "".join(numbered_item(i, it, verb) for i, it in enumerate(items))
    return rule_table(section_title(label, badge)) + rows


def render_epigraph(ep):
    if not ep or not ep.get("text"):
        return ""
    who = (f'<div style="font-family:{MONO};font-size:10px;letter-spacing:2px;'
           f'text-transform:uppercase;color:{ACCENT};padding-top:14px">{esc(ep.get("attribution",""))}</div>'
           if ep.get("attribution") else "")
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr><td align="center" style="padding:32px 10px 30px;border-bottom:1px solid {RULE};text-align:center">
    <div style="font-family:{SERIF};font-style:italic;font-size:21px;line-height:1.4;color:{INK2}">&ldquo;{esc(ep['text'])}&rdquo;</div>
    {who}
  </td></tr>
</table>"""


def render_editor_note(note, issue_url):
    if not note:
        return ""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr><td style="padding:30px 0 28px;border-bottom:1px solid {RULE}">
    <div style="font-family:{MONO};font-size:10px;letter-spacing:2px;text-transform:uppercase;color:{FAINT};padding-bottom:10px">Editor's Note</div>
    <div style="font-family:{SERIF};font-size:17px;line-height:1.6;color:{INK2}">{esc(note)}</div>
    <div style="padding-top:14px"><a href="{esc(issue_url)}" style="font-family:{MONO};font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:{ACCENT}">▶ Listen — NotebookLM reads this edition</a></div>
  </td></tr>
</table>"""


def render_closer_look(essay):
    if not essay:
        return ""
    topic = esc(essay.get("topic") or "Essay")
    pull = esc(essay.get("pull") or "")
    pull_html = (f'<div style="font-family:{SERIF};font-style:italic;font-size:18px;line-height:1.42;'
                 f'color:{DARK_PULL};border-left:2px solid {DARK_ACCENT};padding-left:14px;margin-bottom:16px">&ldquo;{pull}&rdquo;</div>'
                 if pull else "")
    dek = esc(essay.get("excerpt") or "")
    dek_html = (f'<div style="font-family:{SERIF};font-size:15px;line-height:1.55;'
                f'color:{DARK_DEK};margin-bottom:20px">{dek}</div>' if dek else "")
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr><td style="padding:34px 0 18px;border-top:3px solid {INK}">
    <div style="font-family:{SERIF};font-size:30px;letter-spacing:-1px;color:{INK}">A Closer Look</div>
  </td></tr>
  <tr><td style="background:{DARK};padding:34px 32px">
    <div style="font-family:{MONO};font-size:10px;letter-spacing:2px;text-transform:uppercase;color:{DARK_ACCENT};padding-bottom:14px">Essay · {topic}</div>
    <a href="{esc(essay['url'])}" style="font-family:{SERIF};font-size:33px;line-height:1.04;letter-spacing:-1px;color:{DARK_TITLE};display:block;margin-bottom:16px">{esc(essay['title'])}</a>
    {pull_html}
    {dek_html}
    <a href="{esc(essay['url'])}" style="font-family:{MONO};font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{DARK_TITLE};border-bottom:1px solid {DARK_ACCENT};padding-bottom:4px">Read the Essay →</a>
  </td></tr>
</table>"""


def render_recap(recap):
    if not recap:
        return ""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr><td style="padding:34px 0 30px;border-top:3px solid {INK};border-bottom:1px solid {RULE}">
    <div style="font-family:{SERIF};font-size:26px;letter-spacing:-.5px;color:{INK};padding-bottom:12px">✶ Knowledge, Transmuted</div>
    <div style="font-family:{SERIF};font-size:17px;line-height:1.62;color:{INK2}">{esc(recap)}</div>
  </td></tr>
</table>"""


def render_lexicon(terms):
    if not terms:
        return ""
    groups = {}
    for t in terms:
        groups.setdefault(t.get("category") or "Concepts", []).append(t)
    cats = [c for c in CAT_ORDER if c in groups] + [c for c in groups if c not in CAT_ORDER]

    head = f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr><td style="padding:32px 0 6px">
    <div style="font-family:{SERIF};font-size:30px;letter-spacing:-1px;color:{INK}">The Less You Know</div>
    <div style="font-family:{MONO};font-size:10px;letter-spacing:2px;text-transform:uppercase;color:{FAINT};padding-top:5px">The More You Learn</div>
  </td></tr>
</table>"""

    body = ""
    for cat in cats:
        body += f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
  <tr><td style="padding:18px 0 2px;border-top:2px solid {INK}">
    <div style="font-family:{MONO};font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{ACCENT}">{esc(cat)}</div>
  </td></tr>
</table>"""
        for t in groups[cat]:
            body += f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-top:1px solid {RULE}">
  <tr>
    <td width="170" style="width:170px;vertical-align:top;padding:12px 16px 12px 0;font-family:{SANS};font-weight:bold;font-size:14px;line-height:1.3;color:{INK}"><a href="{esc(t['url'])}" style="color:{INK}">{esc(t['name'])}</a></td>
    <td style="vertical-align:top;padding:12px 0;font-family:{SERIF};font-size:14.5px;line-height:1.5;color:{MUTED}">{esc(t.get('definition',''))}</td>
  </tr>
</table>"""
    return head + body


# ── plain-text render (deliverability + required `text` part for Resend) ─────────
HR = "─" * 60
HR2 = "═" * 60


def _w(text, indent=""):
    text = " ".join((text or "").split())
    if not text:
        return ""
    return textwrap.fill(text, width=72, initial_indent=indent, subsequent_indent=indent)


def render_text(issue):
    number = issue.get("number")
    no = f"No. {number}" if number else issue["id"]
    essay = issue.get("essay") or {}
    issue_url = issue.get("url") or f"{SITE}/issues/{number or issue['id']}"
    L = [
        "TOKEN WISDOM",
        "The Newsletter of Record for the Future of Now",
        f"{no} · Week {issue['week']} of 52 · {fmt_date(issue.get('date',''))}",
        "",
    ]

    ep = issue.get("epigraph")
    if ep and ep.get("text"):
        L += [HR, "", _w(f'"{ep["text"]}"')]
        if ep.get("attribution"):
            L.append(f"— {ep['attribution']}")
        L.append("")

    if issue.get("editor_note"):
        L += [HR, "", "EDITOR'S NOTE", "", _w(issue["editor_note"]), "",
              "Listen — NotebookLM reads this edition:", issue_url, ""]

    def rail(title, items, noun):
        if not items:
            return
        L.extend([HR2, f"{title.upper()} — {len(items)} {noun}", HR2, ""])
        for i, it in enumerate(items):
            L.append(f"{i + 1:02d}. {it['title']}")
            if it.get("excerpt"):
                L.append(_w(it["excerpt"], indent="    "))
            L.extend([f"    {it.get('source','')} → {it['url']}", ""])

    rail("Newest / Latest", issue["sections"].get("newest_latest", []), "Dispatches")

    if essay:
        L += [HR2, "A CLOSER LOOK", HR2, "",
              f"ESSAY · {(essay.get('topic') or 'Essay').upper()}", "",
              _w(essay.get("title", "")), ""]
        if essay.get("pull"):
            L += [_w(f'"{essay["pull"]}"'), ""]
        if essay.get("excerpt"):
            L += [_w(essay["excerpt"]), ""]
        L += [f"Read the essay → {essay.get('url','')}", ""]

    rail("Time Well Spent", issue["sections"].get("time_well_spent", []), "to Watch")

    if issue.get("recap"):
        L += [HR2, "* KNOWLEDGE, TRANSMUTED", HR2, "", _w(issue["recap"]), ""]

    terms = issue.get("terms_in_motion", [])
    if terms:
        L += [HR2, "THE LESS YOU KNOW — The More You Learn", HR2, ""]
        groups = {}
        for t in terms:
            groups.setdefault(t.get("category") or "Concepts", []).append(t)
        cats = [c for c in CAT_ORDER if c in groups] + [c for c in groups if c not in CAT_ORDER]
        for cat in cats:
            L += [cat.upper(), ""]
            for t in groups[cat]:
                L += [f"  {t['name']}", _w(t.get("definition", ""), indent="    "), ""]

    L += [HR, "", "TOKEN WISDOM", "Knowware is measured in lifetimes.",
          "By @iamkhayyam · ARC Institute of Knowware",
          "This edition was curated by a human.", "",
          f"Read online: {issue_url}",
          f"Subscribe:   {GHOST_URL}/subscribe",
          "Unsubscribe: {{{unsubscribe_url}}}", ""]
    return "\n".join(L)


def build(issue_path):
    issue = json.loads(Path(issue_path).read_text())
    number = issue.get("number")
    slug = str(number) if number else issue["id"]
    essay = issue.get("essay") or {}
    issue_url = issue.get("url") or f"{SITE}/issues/{slug}"
    headline = "Token Wisdom"
    no = f"No. {number}" if number else issue["id"]
    week_line = f"{no} &nbsp;·&nbsp; Week {issue['week']} of 52 &nbsp;·&nbsp; {fmt_date(issue.get('date',''))}"
    preheader = issue.get("dek") or essay.get("excerpt") or "The Newsletter of Record for the Future of Now."

    tnl = issue["sections"].get("newest_latest", [])
    tws = issue["sections"].get("time_well_spent", [])

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{esc(no)} — Token Wisdom</title>
{HEAD}
</head>
<body style="margin:0;padding:0;background:{BG}">
<span style="display:none!important;visibility:hidden;opacity:0;color:{BG};font-size:1px;line-height:1px;max-height:0;overflow:hidden">{esc(preheader)}</span>
<div style="background:{BG};padding:40px 16px 70px;font-family:{SANS}">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" align="center" class="container" style="width:600px;max-width:600px;margin:0 auto;background:{PAPER};border:1px solid {RULE};box-shadow:0 24px 60px -30px rgba(40,30,20,.5)">
  <tr><td class="px" style="padding:0 40px">

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr><td align="center" style="padding:40px 0 22px;border-bottom:1px solid {RULE};text-align:center">
        <div style="font-family:{SERIF};font-size:48px;letter-spacing:-1px;line-height:.9;color:{INK};font-weight:normal">Token Wisdom</div>
        <div style="font-family:{MONO};font-size:10px;letter-spacing:3px;text-transform:uppercase;color:{ACCENT};padding-top:16px">The Newsletter of Record for the Future of Now</div>
        <div style="font-family:{MONO};font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{FAINT};padding-top:11px">{week_line}</div>
      </td></tr>
    </table>

    {render_epigraph(issue.get('epigraph'))}
    {render_editor_note(issue.get('editor_note'), issue_url)}
    {render_rail('Newest / Latest', tnl, 'Read', f'{len(tnl)} Dispatches')}
    {render_closer_look(essay)}
    {render_rail('Time Well Spent', tws, 'Watch', f'{len(tws)} to Watch')}
    {render_recap(issue.get('recap'))}
    {render_lexicon(issue.get('terms_in_motion', []))}

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr><td align="center" style="padding:34px 0 40px;border-top:3px solid {INK};text-align:center">
        <div style="font-family:{SERIF};font-size:22px;letter-spacing:-.5px;color:{INK};padding-bottom:8px">Token Wisdom</div>
        <div style="font-family:{SERIF};font-style:italic;font-size:14px;color:{MUTED};padding-bottom:16px">Knowware is measured in lifetimes.</div>
        <div style="font-family:{MONO};font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{FAINT};line-height:1.9">By @iamkhayyam · ARC Institute of Knowware<br>This edition was curated by a human.</div>
        <div style="font-family:{MONO};font-size:10px;letter-spacing:1px;text-transform:uppercase;color:{FAINT2};padding-top:16px"><a href="{issue_url}" style="color:{ACCENT}">Read online</a> &nbsp;·&nbsp; <a href="{GHOST_URL}/subscribe" style="color:{ACCENT}">Subscribe</a> &nbsp;·&nbsp; <a href="{{{{{{unsubscribe_url}}}}}}" style="color:{FAINT2}">Unsubscribe</a></div>
      </td></tr>
    </table>

  </td></tr>
</table>
</div>
</body></html>"""

    out_dir = DOCS / "issues" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "email.html").write_text(html)
    (out_dir / "email.txt").write_text(render_text(issue))
    return out_dir / "email.html", out_dir / "email.txt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("issue")
    a = ap.parse_args()
    for p in build(a.issue):
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()

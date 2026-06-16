#!/usr/bin/env python3
"""
build_issue.py — assemble one weekly Issue object (the record).

The keystone of the redesign: build ONE canonical issue JSON, then render it
many ways (web /issues/N, email via Resend, social via Zernio, RSS/JSON feed).

Inputs that already exist:
  data/links/{YY}.W.{WW}.TNL.csv   The Newest Latest (articles)  — from Raindrop
  data/links/{YY}.W.{WW}.TWS.csv   Time Well Spent (videos)      — from Raindrop
  data/lexicon.json                the corpus (for "terms in motion")
  posts/*/post.json                the essay (referenced, not re-authored)

Optional editorial overlay (Knowware CMS / Payload), applied after the CSV
build when PAYLOAD_URL + PAYLOAD_API_KEY are set (see payload_overlay.py):
  editors' edit.* title/blurb overrides + curated rail order flow back in.
  Fail-safe: unreachable/absent CMS leaves the CSV build untouched.

Output:
  data/issues/{YYYY}-W{WW}.json    validated against data/issue.schema.json

Usage:
  python3 build_issue.py --week 23 --year 2026
  python3 build_issue.py --week 23 --essay the-token-reckoning --number 153
"""

import argparse
import csv
import glob
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from payload_overlay import overlay_sections

ROOT = Path(__file__).parent
LINKS_DIR = ROOT / "data" / "links"
ISSUES_DIR = ROOT / "data" / "issues"
LEXICON = ROOT / "data" / "lexicon.json"
POSTS = ROOT / "posts"
SITE = "https://tokenwisdom.org"
BUILDER_VERSION = "0.1.0"

# Term names too short/noisy to trust as standalone matches in v0 heuristic.
TERM_STOPLIST = {"3D", "AR", "VR", "ID", "OS", "UI", "UX", "PC", "TV"}


def find_csv(year, week, section):
    """Tolerate the naming variants build_links_db.py already handles."""
    yy = year % 100
    pats = [
        f"{yy}.W{week:02d}.{section}.csv",
        f"{yy}.W.{week:02d}.{section}.csv",
        f"{yy}.W.{week}.{section}.csv",
        f"{yy}.W{week}.{section}.csv",
    ]
    for p in pats:
        hit = LINKS_DIR / p
        if hit.exists():
            return hit
    # last resort: glob
    g = sorted(glob.glob(str(LINKS_DIR / f"{yy}.W*{week}*.{section}.csv")))
    return Path(g[0]) if g else None


def display_source(url, kind):
    host = (urlparse(url).hostname or "").lower().replace("www.", "")
    if kind == "video" or "youtu" in host:
        return "YouTube"
    return host


def load_links(year, week, section, kind):
    path = find_csv(year, week, section)
    if not path:
        return [], None
    items = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = (row.get("url") or "").strip()
            if not url:
                continue
            tags = [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]
            items.append({
                "id": (row.get("id") or "").strip(),
                "title": (row.get("title") or "").strip(),
                "url": url,
                "excerpt": (row.get("excerpt") or "").strip(),
                "cover": (row.get("cover") or "").strip(),
                "source": display_source(url, kind),
                "kind": kind,
                "added": (row.get("created") or "").strip(),
                "tags": tags,
            })
    return items, path.name


def is_edition(d):
    """The numbered weekly roundups ('153rd Edition ... Week 13') are NOT essays —
    the closer-look essay is a standalone titled piece published that week."""
    slug = (d.get("slug") or "").lower()
    title = (d.get("title") or "").lower()
    return "edition" in slug or "edition" in title


def pick_essay(slug_override):
    """Reference the week's closer-look essay. Default: most recent standalone
    essay (skipping the numbered editions / roundups)."""
    best = None
    for pj in POSTS.glob("*/post.json"):
        try:
            d = json.load(open(pj))
        except Exception:
            continue
        if slug_override:
            if d.get("slug") == slug_override:
                best = d
                break
            continue
        if is_edition(d):
            continue
        if best is None or (d.get("published_at", "") > best.get("published_at", "")):
            best = d
    if not best:
        return None
    return {
        "slug": best.get("slug", ""),
        "title": best.get("title", ""),
        "url": f"{SITE}/posts/{best.get('slug','')}.html",
        "excerpt": best.get("custom_excerpt") or "",
        "feature_image": best.get("feature_image") or "",
        "published_at": best.get("published_at", ""),
    }


def _count(name, text, text_lower):
    """Acronyms (short, all-caps) match case-sensitively so the term 'IT' doesn't
    catch the pronoun 'it'; everything else matches case-insensitively."""
    if name.isupper() and len(name) <= 4:
        return len(re.findall(r"\b" + re.escape(name) + r"\b", text))
    return len(re.findall(r"\b" + re.escape(name.lower()) + r"\b", text_lower))


def terms_in_motion(week_text, top_n=12):
    """v0 of the corpus hook: score lexicon terms by appearance in the week's text."""
    data = json.load(open(LEXICON))
    terms = data["terms"] if isinstance(data, dict) else data
    if isinstance(terms, dict):
        terms = list(terms.values())
    text, text_lower = week_text, week_text.lower()
    scored = []
    for t in terms:
        name = t.get("name", "")
        if len(name) < 2 or name.upper() in TERM_STOPLIST:
            continue
        hits = _count(name, text, text_lower)
        if hits:
            scored.append((hits, t.get("edition_count", 0), t))
    # rank by mentions, then corpus weight (keystones win ties)
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    out = []
    for hits, _, t in scored:
        if len(out) >= top_n:
            break
        defn = " ".join((t.get("definition") or "").split())  # collapse whitespace
        low = defn.lower()
        # Skip terms whose source definition is polluted (scraped boilerplate/URLs).
        if "http" in low or "youtube.com" in low or len(defn) > 300:
            continue
        if len(defn) > 220:
            defn = defn[:217].rstrip() + "…"
        out.append({
            "name": t.get("name"),
            "slug": t.get("slug"),
            "color": t.get("color"),
            "category": t.get("category"),
            "role": t.get("role") or None,
            "edition_count": t.get("edition_count", 0),
            "definition": defn,
            "url": f"{SITE}/lexicon/{t.get('slug','')}.html",
            "mentions": hits,
        })
    return out, terms


def from_the_record(top_terms, all_terms):
    """Surface one evergreen pull: the first appearance of this week's lead term."""
    if not top_terms:
        return None
    lead = top_terms[0]["slug"]
    term = next((t for t in all_terms if t.get("slug") == lead), None)
    if not term:
        return None
    first = term.get("first") or {}
    if not first:
        return None
    return {
        "edition": first.get("edition"),
        "slug": first.get("slug", ""),
        "title": first.get("title") or first.get("slug", ""),
        "url": f"{SITE}/posts/{first.get('slug','')}.html" if first.get("slug") else "",
        "date": first.get("date", ""),
        "reason": f"First appearance of “{term.get('name')}” in the record.",
    }


def build(year, week, essay_slug, number, use_payload=True):
    tnl, tnl_csv = load_links(year, week, "TNL", "article")
    tws, tws_csv = load_links(year, week, "TWS", "video")

    # Overlay the editorial layer curated in Payload (text overrides + rail order)
    # BEFORE anything downstream, so terms, counts and the report all derive from
    # the curated truth. Fail-safe: no env / unreachable CMS → CSV build untouched.
    issue_id = f"{year}-W{week:02d}"
    overlay = {"applied": False, "reason": "disabled (--no-payload)"}
    base, key = os.environ.get("PAYLOAD_URL"), os.environ.get("PAYLOAD_API_KEY")
    if use_payload and base and key:
        tnl, tws, overlay = overlay_sections(
            issue_id, tnl, tws, base_url=base, api_key=key,
            mode=os.environ.get("PAYLOAD_OVERLAY_MODE", "reorder"),
        )
    elif use_payload:
        overlay = {"applied": False, "reason": "PAYLOAD_URL/PAYLOAD_API_KEY not set"}

    essay = pick_essay(essay_slug)

    week_text = " ".join(
        f"{i['title']} {i['excerpt']} {' '.join(i['tags'])}" for i in (tnl + tws)
    )
    if essay:
        week_text += " " + essay.get("title", "") + " " + essay.get("excerpt", "")

    tim, all_terms = terms_in_motion(week_text)
    record = from_the_record(tim, all_terms)

    report = [
        {"label": "Items this week", "value": len(tnl) + len(tws), "delta": None},
        {"label": "Terms in the corpus", "value": len(all_terms), "delta": None},
        {"label": "Newest / Latest", "value": len(tnl), "delta": None},
        {"label": "Time Well Spent", "value": len(tws), "delta": None},
    ]

    issue = {
        "$schema": "./issue.schema.json",
        "schema_version": "1.0",
        "id": issue_id,
        "number": number,
        "year": year,
        "week": week,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "status": "draft",
        "title": f"Token Wisdom · {year} · Week {week}",
        "dek": "",
        # Human-authored editorial fields — populated from the editorial sidecar
        # (data/issues/{id}.editorial.json) if present. The builder can't write prose.
        "epigraph": None,
        "editor_note": None,
        "recap": None,
        "url": f"{SITE}/issues/{number}" if number else "",
        "hero": {"image": essay.get("feature_image", "") if essay else "", "alt": ""},
        "essay": essay,
        "sections": {"newest_latest": tnl, "time_well_spent": tws},
        "terms_in_motion": tim,
        # Community-layer hooks: structure is real; population is the next iteration
        # (highlights are PRIVATE — only aggregate counts + public responses surface).
        "reader_marks": {"most_highlighted": None, "responses": []},
        "from_the_record": record,
        "report": report,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "builder_version": BUILDER_VERSION,
            "source_csvs": [c for c in (tnl_csv, tws_csv) if c],
            "counts": {"newest_latest": len(tnl), "time_well_spent": len(tws),
                       "terms_in_motion": len(tim)},
            "payload_overlay": overlay,
        },
    }

    # Merge the editorial sidecar (human-authored prose) if present.
    sidecar = ISSUES_DIR / f"{issue['id']}.editorial.json"
    if sidecar.exists():
        ed = json.loads(sidecar.read_text())
        for k in ("epigraph", "editor_note", "recap", "dek"):
            if ed.get(k) is not None:
                issue[k] = ed[k]
        if essay:
            if ed.get("essay_pull"):
                essay["pull"] = ed["essay_pull"]
            if ed.get("essay_topic"):
                essay["topic"] = ed["essay_topic"]

    ISSUES_DIR.mkdir(parents=True, exist_ok=True)
    out = ISSUES_DIR / f"{year}-W{week:02d}.json"
    out.write_text(json.dumps(issue, indent=2, ensure_ascii=False))
    return out, issue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--week", type=int, default=23)
    ap.add_argument("--essay", default=None, help="essay slug to feature (default: latest)")
    ap.add_argument("--number", type=int, default=None, help="edition number for the masthead")
    ap.add_argument("--no-payload", action="store_true",
                    help="skip the Payload editorial overlay (build from CSV only)")
    a = ap.parse_args()

    out, issue = build(a.year, a.week, a.essay, a.number, use_payload=not a.no_payload)
    print(f"Wrote {out}")
    ov = issue["meta"]["payload_overlay"]
    if ov.get("applied"):
        print(f"  payload overlay:  {ov['edits']} text override(s), "
              f"mode={ov['mode']}, reordered={ov['reordered']}, dropped={ov['dropped']}")
    elif ov.get("error"):
        print(f"  payload overlay:  skipped — {ov['error']} (CSV build used)")
    else:
        print(f"  payload overlay:  not applied — {ov.get('reason')}")
    print(f"  essay:            {issue['essay']['slug'] if issue['essay'] else '(none)'}")
    print(f"  newest/latest:    {issue['meta']['counts']['newest_latest']}")
    print(f"  time well spent:  {issue['meta']['counts']['time_well_spent']}")
    print(f"  terms in motion:  " +
          ", ".join(f"{t['name']}({t['mentions']})" for t in issue["terms_in_motion"]))
    if issue["from_the_record"]:
        print(f"  from the record:  {issue['from_the_record']['reason']}")


if __name__ == "__main__":
    main()

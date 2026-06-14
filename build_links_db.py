#!/usr/bin/env python3
"""
Parse all data/links/*.csv files into data/links.json.

Handles naming variants:
  25.W01.TNL.csv        — 2025, week 1
  26.W.09.TNL.csv       — 2026, week 9
  26.W.13-TNL.csv       — 2026, week 13 (dash separator)
  w-18.TNL.csv          — 2026, week 18 (legacy, no year prefix)
  w.21.TNL.csv          — 2026, week 21 (legacy)

Sections: TNL = The Newest Latest (articles), TWS = Time Well Spent (videos)

Run: python build_links_db.py
"""

import csv
import json
import re
from pathlib import Path

LINKS_DIR = Path(__file__).parent / "data" / "links"
OUT       = Path(__file__).parent / "data" / "links.json"


def parse_stem(stem):
    """Return (year, week, section) or raise ValueError."""
    stem = stem.strip()

    # 25.W01.TNL  /  26.W.09.TNL
    m = re.match(r"(\d{2})\.W\.?(\d{1,2})[.\-](TNL|TWS)$", stem, re.I)
    if m:
        return 2000 + int(m.group(1)), int(m.group(2)), m.group(3).upper()

    # w-18.TNL  /  w.21.TNL  (legacy, treated as 2026)
    m = re.match(r"w[-.](\d{1,2})\.(TNL|TWS)$", stem, re.I)
    if m:
        return 2026, int(m.group(1)), m.group(2).upper()

    raise ValueError(f"Unrecognised filename stem: {stem!r}")


def parse_csv(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = row.get("title", "").strip()
            url   = row.get("url", "").strip()
            if not title or not url:
                continue
            rows.append({
                "id":      row.get("id", "").strip(),
                "title":   title,
                "note":    row.get("note", "").strip(),
                "excerpt": row.get("excerpt", "").strip(),
                "url":     url,
                "tags":    [t.strip() for t in row.get("tags", "").split(",") if t.strip()],
                "created": row.get("created", "").strip(),
                "cover":   row.get("cover", "").strip(),
                "favorite": row.get("favorite", "").strip().lower() == "true",
            })
    return rows


def build():
    # Collect into {(year, week): {"tnl": [...], "tws": [...]}}
    buckets = {}
    skipped = []

    for csv_path in sorted(LINKS_DIR.glob("*.csv")):
        try:
            year, week, section = parse_stem(csv_path.stem)
        except ValueError as e:
            skipped.append(str(e))
            continue

        key = (year, week)
        if key not in buckets:
            buckets[key] = {"year": year, "week": week, "tnl": [], "tws": []}
        items = parse_csv(csv_path)
        buckets[key]["tnl" if section == "TNL" else "tws"].extend(items)

    sorted_weeks = sorted(buckets.values(), key=lambda w: (w["year"], w["week"]))

    # Annotate every item with its week/year/section for the flat list
    all_links = []
    for w in sorted_weeks:
        for item in w["tnl"]:
            all_links.append({**item, "year": w["year"], "week": w["week"], "section": "tnl"})
        for item in w["tws"]:
            all_links.append({**item, "year": w["year"], "week": w["week"], "section": "tws"})

    latest = sorted_weeks[-1] if sorted_weeks else {}
    db = {
        "current_year":  latest.get("year"),
        "current_week":  latest.get("week"),
        "total_weeks":   len(sorted_weeks),
        "total_tnl":     sum(len(w["tnl"]) for w in sorted_weeks),
        "total_tws":     sum(len(w["tws"]) for w in sorted_weeks),
        "weeks":         sorted_weeks,
        "all_links":     all_links,
    }

    OUT.write_text(json.dumps(db, indent=2, ensure_ascii=False))

    print(f"Wrote {OUT}")
    print(f"  Years:      {sorted({w['year'] for w in sorted_weeks})}")
    print(f"  Weeks:      {len(sorted_weeks)}")
    print(f"  TNL items:  {db['total_tnl']}")
    print(f"  TWS items:  {db['total_tws']}")
    print(f"  Total:      {len(all_links)}")
    print(f"  Current:    {latest.get('year')} W{latest.get('week'):02d}")
    if skipped:
        print(f"  Skipped:    {skipped}")
    return db


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""One-time surgical scrub of the already-built data/lexicon.json + /lexicon/ pages.

Why surgical (not a full `python3 lexicon.py` rebuild): the graph fields
(related / centrality / keystone / role) are computed from `Counter.most_common`
with ties broken by set-iteration order, so they are NOT deterministic across
processes — a blind rebuild rewrites all ~1941 of them with noise unrelated to
the pollution fix. This script instead PRESERVES the committed graph sample and
changes only what the cleanup requires:

  · drops parser-artifact terms (names like "Subscribe", "CE)", "Latest Edition")
  · prunes `related` references that pointed at dropped terms (no dangling links)
  · recomputes centrality/keystone/role consistently from the pruned graph
  · cleans polluted definitions (sanitize + hand-written overrides)
  · re-renders index, constellation, category pages, and every term page from
    the cleaned data (isolated from the WIP generate_site.py via a date shim)

Re-running lexicon.render_*() over the committed JSON reproduces the committed
pages byte-for-byte, so the resulting page diff touches only affected terms.
"""

import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import lexicon
import lexicon_clean as clean
import lexicon_sources as src

DATA = Path("data/lexicon.json")
LEX_DIR = Path("docs/lexicon")


class GS:
    """Minimal stand-in for generate_site (date helpers only) — keeps the WIP
    generate_site.py out of the regenerated pages."""
    @staticmethod
    def fmt_date(iso, fmt="%B %-d, %Y"):
        if not iso:
            return ""
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime(fmt)
        except Exception:
            return iso[:10]

    @staticmethod
    def fmt_date_short(iso):
        return GS.fmt_date(iso, "%b %-d, %Y")


def clean_history(term):
    """Sanitize each definition-history entry; drop ones that don't survive.
    For a manual-override term, collapse history to the override text."""
    slug = term["slug"]
    hist = term.get("definition_history", [])
    if slug in clean.MANUAL_DEFS:
        last = hist[-1] if hist else {"edition": term["latest"].get("edition"),
                                      "date": term["latest"].get("date"),
                                      "slug": term["latest"].get("slug")}
        return [{"text": clean.MANUAL_DEFS[slug], "edition": last.get("edition"),
                 "date": last.get("date"), "slug": last.get("slug")}]
    out = []
    for h in hist:
        txt = h.get("text", "")
        s = clean.sanitize(txt) if clean.is_polluted(txt) else txt
        if s:
            out.append({**h, "text": s})
    return out


def main():
    data = json.load(open(DATA))
    terms = data["terms"]
    before = len(terms)

    # 1. Identify artifact terms to drop.
    dropped = {t["slug"] for t in terms if clean.is_artifact_name(t["name"])}
    print(f"Dropping {len(dropped)} artifact terms: {sorted(dropped)}")

    kept = [t for t in terms if t["slug"] not in dropped]

    # 2. Prune related refs to dropped terms.
    pruned_refs = 0
    for t in kept:
        rel = t.get("related", [])
        new = [r for r in rel if r.get("slug") not in dropped]
        pruned_refs += len(rel) - len(new)
        t["related"] = new
    print(f"Pruned {pruned_refs} related refs pointing at dropped terms")

    # 3. Recompute centrality / keystone / role from the pruned graph.
    indeg = defaultdict(int)
    for t in kept:
        for r in t["related"]:
            indeg[r["slug"]] += 1
    cent_changed = 0
    for t in kept:
        c = indeg.get(t["slug"], 0)
        if t.get("centrality") != c:
            cent_changed += 1
        t["centrality"] = c
        t["keystone"] = round(t["edition_count"] + lexicon.KEYSTONE_W * c, 1)
        t["role"] = lexicon._role(t["edition_count"], c)
    print(f"Recomputed centrality (changed for {cent_changed} terms)")

    # 4. Clean definitions.
    def_changed = 0
    for t in kept:
        slug, defn = t["slug"], t.get("definition", "")
        new = defn
        if slug in clean.MANUAL_DEFS:
            new = clean.MANUAL_DEFS[slug]
        elif clean.is_polluted(defn):
            new = clean.pick_clean(t.get("definition_history", []),
                                   fallback=clean.sanitize(defn))
        if new != defn:
            def_changed += 1
            t["definition"] = new
        t["definition_history"] = clean_history(t)
    print(f"Cleaned {def_changed} polluted definitions")

    # 5. Sanity: no pollution left.
    leftover = [t["slug"] for t in kept if clean.is_polluted(t["definition"])]
    assert not leftover, f"pollution remains: {leftover}"

    data["terms"] = kept
    json.dump(data, open(DATA, "w"), indent=2, ensure_ascii=False)
    print(f"Wrote {DATA}: {before} -> {len(kept)} terms")

    # 6. Re-render every derived page from the cleaned data.
    gs = GS()
    qkeys = data.get("quarters", [])
    ctx = {"edition_count": data.get("edition_count"), "now": data.get("generated", "")}

    # delete pages for dropped terms
    for slug in dropped:
        p = LEX_DIR / f"{slug}.html"
        if p.exists():
            p.unlink()

    (LEX_DIR / "index.html").write_text(lexicon.render_index(kept, qkeys, gs, ctx))
    (LEX_DIR / "constellation.html").write_text(lexicon.render_constellation(kept, gs, ctx))

    by_cat = defaultdict(list)
    for t in kept:
        by_cat[t["category"]].append(t)
    for c in src.CATEGORY_ORDER:
        if by_cat.get(c):
            (LEX_DIR / lexicon.cat_file(c)).write_text(
                lexicon.render_category(c, by_cat[c], gs, ctx))

    for t in kept:
        (LEX_DIR / f"{t['slug']}.html").write_text(lexicon.render_term(t, gs, ctx))

    print(f"Re-rendered index + constellation + category pages + {len(kept)} term pages")


if __name__ == "__main__":
    main()

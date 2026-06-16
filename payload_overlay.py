#!/usr/bin/env python3
"""
payload_overlay.py — close the two-way loop with Knowware CMS (Payload).

build_issue.py builds each weekly Issue from the Raindrop CSVs (the raw,
pipeline-owned layer). Editors then curate that issue inside Payload: they may
rewrite an item's title/blurb (the `edit.*` fields) and reorder — or, in
`replace` mode, prune — the TNL / TWS rails. This module pulls that editorial
layer back out and overlays it onto the freshly-built sections, so the rendered
newsletter reflects the curation.

Field ownership (mirror of scripts/ingest-issues.mjs in knowware-cms):
  - The pipeline owns `raw.*`. We never read it back — the CSV is already truth.
  - Editors own `edit.*` + rail order + `curated`. That is ALL we read here.

Fail-safe by design: any missing env / network error / absent issue returns the
sections unchanged. A down CMS must never break the newsletter build.

Env consumed by the caller:
  PAYLOAD_URL           e.g. https://cms.tokenwisdom.org   (no /api suffix)
  PAYLOAD_API_KEY       api-clients key
  PAYLOAD_OVERLAY_MODE  'reorder' (default, never drops) | 'replace' (Payload's
                        rail set is authoritative — items it omits are dropped)
"""

import json
import urllib.parse
import urllib.request


def _fetch_issue_doc(issue_id, base_url, api_key, timeout=10):
    """GET the one Payload issue with its rails populated (depth=2 → item docs)."""
    params = urllib.parse.urlencode({
        "where[issueId][equals]": issue_id,
        "depth": 2,
        "limit": 1,
    })
    url = f"{base_url.rstrip('/')}/api/issues?{params}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"api-clients API-Key {api_key}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    docs = data.get("docs") or []
    return docs[0] if docs else None


def _overrides_from_doc(doc):
    """Pull editor text overrides (keyed by Raindrop id) + the curated rail order."""
    edits = {}
    orders = {"tnl": [], "tws": []}
    for key in ("tnl", "tws"):
        for it in (doc.get(key) or []):
            if not isinstance(it, dict):
                continue  # unpopulated relationship (bare id) — no edits available
            rid = str(it.get("raindropId") or "").strip()
            if not rid:
                continue
            orders[key].append(rid)
            ed = it.get("edit") or {}
            edits[rid] = {
                "title": (ed.get("title") or "").strip(),
                "excerpt": (ed.get("excerpt") or "").strip(),
            }
    return edits, orders


def _merge(items, order_ids, edits, mode):
    """Apply text overrides, then reorder (mode 'reorder' appends unlisted local
    items; 'replace' keeps only what Payload lists). Pure — no I/O."""
    n_edits = 0
    for it in items:
        ov = edits.get(str(it.get("id") or ""))
        if ov:
            if ov["title"]:
                it["title"] = ov["title"]; n_edits += 1
            if ov["excerpt"]:
                it["excerpt"] = ov["excerpt"]; n_edits += 1

    by_id = {str(it.get("id") or ""): it for it in items}
    ordered, seen = [], set()
    for rid in order_ids:
        it = by_id.get(rid)
        if it is not None and rid not in seen:
            ordered.append(it)
            seen.add(rid)
    leftovers = [it for it in items if str(it.get("id") or "") not in seen]

    new_items = ordered if mode == "replace" else ordered + leftovers
    reordered = list(map(id, new_items)) != list(map(id, items))
    dropped = len(items) - len(new_items)
    return new_items, n_edits, reordered, dropped


def overlay_sections(issue_id, tnl, tws, *, base_url, api_key,
                     mode="reorder", timeout=10):
    """Overlay Payload's editorial layer onto (tnl, tws). Returns the (possibly
    new) lists plus a summary dict for meta/observability. Never raises."""
    summary = {
        "applied": False, "mode": mode, "edits": 0,
        "reordered": {"tnl": False, "tws": False},
        "dropped": {"tnl": 0, "tws": 0},
        "error": None, "reason": None,
    }
    try:
        doc = _fetch_issue_doc(issue_id, base_url, api_key, timeout)
    except Exception as e:  # network, auth, timeout, bad JSON — all non-fatal
        summary["error"] = f"{type(e).__name__}: {e}"
        return tnl, tws, summary

    if not doc:
        summary["reason"] = "issue not yet in Payload"
        return tnl, tws, summary

    edits, orders = _overrides_from_doc(doc)
    tnl2, e1, r1, d1 = _merge(tnl, orders["tnl"], edits, mode)
    tws2, e2, r2, d2 = _merge(tws, orders["tws"], edits, mode)
    summary.update(
        applied=True, edits=e1 + e2,
        reordered={"tnl": r1, "tws": r2},
        dropped={"tnl": d1, "tws": d2},
    )
    return tnl2, tws2, summary

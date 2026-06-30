"""
Token Wisdom × Algolia — Search Indexer
========================================

The on-site complement to Zernio. Where Zernio fans the corpus *out* to surfaces
LLMs crawl, Algolia gives readers already on tokenwisdom.org a real search box —
"find every edition that mentions FLOPs", "show me the People & Works terms" —
across 1,900+ Lexicon entries and 260+ editions/essays.

Two indices, both built from the same JSON the rest of the build reads:

  tokenwisdom_lexicon  ← data/lexicon.json   (name, definition, related terms,
                                              category, centrality, edition_count)
  tokenwisdom_posts    ← data/all_posts.json (title, excerpt, tags, published_at,
                                              feature_image, slug)
                         public posts only — members/paid are skipped.

Strategy: idempotent upsert by objectID = slug, plus a sidecar state file
(data/.algolia_state.json) so the next run can delete objectIDs that vanished
from source. No new pip dependency — uses stdlib urllib against Algolia's REST
API. Mirrors the Zernio safety pattern: dry-runs cleanly without credentials,
hooked into generate_site.py inside try/except so the indexer never breaks the
build.

Setup:
  1. Sign up at algolia.com (free tier covers our volume comfortably).
  2. Create two indices: tokenwisdom_lexicon, tokenwisdom_posts.
  3. Export env vars:
       ALGOLIA_APP_ID=...        # 10-char app id from Algolia dashboard
       ALGOLIA_ADMIN_API_KEY=... # admin key — write-side, NEVER ship to frontend
  4. Run `python algolia_index.py` (or it'll run from generate_site).
  5. For the search UI, expose the SEARCH-ONLY key (not admin) in the frontend.

Searchable + ranking configuration (one-time, in Algolia dashboard):
  Lexicon — searchable: name (ordered), definition, related.name, category
            custom ranking desc: centrality, edition_count
  Posts   — searchable: title (ordered), excerpt, tags.name
            custom ranking desc: published_at_ts
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Iterable

# ── Config ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

LEXICON_FILE = DATA / "lexicon.json"
POSTS_FILE = DATA / "all_posts.json"
STATE_FILE = DATA / ".algolia_state.json"

LEXICON_INDEX = os.environ.get("ALGOLIA_LEXICON_INDEX", "tokenwisdom_lexicon")
POSTS_INDEX = os.environ.get("ALGOLIA_POSTS_INDEX", "tokenwisdom_posts")

# Each Algolia record is capped at 10KB by default. Definitions stay short, but
# we still trim long fields defensively so a runaway essay excerpt can't fail
# the whole batch.
MAX_EXCERPT_CHARS = 1200
BATCH_SIZE = 1000  # Algolia caps individual /batch requests at ~10MB


def app_id() -> str | None:
    return os.environ.get("ALGOLIA_APP_ID") or None


def admin_key() -> str | None:
    return os.environ.get("ALGOLIA_ADMIN_API_KEY") or None


def is_live() -> bool:
    return bool(app_id() and admin_key())


# ── Record builders ─────────────────────────────────────────────────────────


def _trim(text: str | None, limit: int = MAX_EXCERPT_CHARS) -> str:
    if not text:
        return ""
    text = " ".join(text.split())  # collapse whitespace
    return text if len(text) <= limit else text[: limit - 1] + "…"


def lexicon_records(lexicon: dict) -> list[dict]:
    """One record per term. objectID = slug."""
    out = []
    for term in lexicon.get("terms", []):
        slug = term.get("slug")
        if not slug:
            continue
        related = term.get("related") or []
        # Cap related to top 12 by `shared` (already sorted desc in source).
        related_top = related[:12]
        out.append({
            "objectID": slug,
            "kind": "term",
            "name": term.get("name", ""),
            "slug": slug,
            "url": f"/lexicon/{slug}.html",
            "category": term.get("category", ""),
            "color": term.get("color", ""),
            "definition": _trim(term.get("definition", "")),
            "edition_count": term.get("edition_count", 0),
            "centrality": term.get("centrality", 0),
            "keystone": term.get("keystone", 0),
            "role": term.get("role", ""),
            "first_edition": (term.get("first") or {}).get("edition"),
            "latest_edition": (term.get("latest") or {}).get("edition"),
            "related": [{"name": r.get("name"), "slug": r.get("slug")} for r in related_top],
            "related_names": [r.get("name", "") for r in related_top],
        })
    return out


def post_records(posts: list[dict]) -> list[dict]:
    """One record per PUBLIC post. members/paid are skipped — search must not
    expose gated content."""
    out = []
    for p in posts:
        if p.get("visibility") != "public":
            continue
        slug = p.get("slug")
        if not slug:
            continue
        published = p.get("published_at")
        try:
            ts = int(datetime.fromisoformat(published.replace("Z", "+00:00")).timestamp()) if published else 0
        except (ValueError, AttributeError):
            ts = 0
        tags = [{"name": t.get("name", ""), "slug": t.get("slug", "")}
                for t in (p.get("tags") or []) if t.get("visibility") == "public"]
        out.append({
            "objectID": slug,
            "kind": "post",
            "title": p.get("title", ""),
            "slug": slug,
            "url": f"/{slug}.html",
            "excerpt": _trim(p.get("custom_excerpt") or p.get("excerpt") or ""),
            "tags": tags,
            "tag_names": [t["name"] for t in tags],
            "feature_image": p.get("feature_image") or "",
            "published_at": published or "",
            "published_at_ts": ts,
            "reading_time": p.get("reading_time", 0),
        })
    return out


# ── State (for deletes) ─────────────────────────────────────────────────────


def load_state() -> dict[str, list[str]]:
    if not STATE_FILE.exists():
        return {LEXICON_INDEX: [], POSTS_INDEX: []}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {LEXICON_INDEX: [], POSTS_INDEX: []}


def save_state(state: dict[str, list[str]]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


# ── Algolia REST client (stdlib) ────────────────────────────────────────────


def _req(method: str, path: str, body: dict | None = None) -> dict:
    """Issue a write request to Algolia. Reads admin key from env."""
    aid = app_id()
    key = admin_key()
    if not (aid and key):
        raise RuntimeError("ALGOLIA_APP_ID and ALGOLIA_ADMIN_API_KEY must be set")
    url = f"https://{aid}.algolia.net{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Algolia-Application-Id", aid)
    req.add_header("X-Algolia-API-Key", key)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode() or "{}")


def _push_batch(index: str, records: list[dict], action: str) -> None:
    """addObject upserts by objectID; deleteObject by {objectID}."""
    for i in range(0, len(records), BATCH_SIZE):
        chunk = records[i : i + BATCH_SIZE]
        requests = [{"action": action, "body": r} for r in chunk]
        _req("POST", f"/1/indexes/{index}/batch", {"requests": requests})
        time.sleep(0.1)  # be polite


def push_index(index: str, records: list[dict], previous_ids: list[str]) -> list[str]:
    """Upsert all records, then delete any objectIDs that disappeared from source.
    Returns the new objectID list for state persistence."""
    current_ids = [r["objectID"] for r in records]
    print(f"  [{index}] upsert {len(current_ids):,} records…")
    _push_batch(index, records, "addObject")
    stale = sorted(set(previous_ids) - set(current_ids))
    if stale:
        print(f"  [{index}] delete {len(stale)} stale records…")
        _push_batch(index, [{"objectID": oid} for oid in stale], "deleteObject")
    return current_ids


# ── Entry point ─────────────────────────────────────────────────────────────


def main() -> int:
    if not LEXICON_FILE.exists():
        print(f"[algolia] {LEXICON_FILE} missing — skipping.")
        return 0
    if not POSTS_FILE.exists():
        print(f"[algolia] {POSTS_FILE} missing — skipping.")
        return 0

    lexicon = json.loads(LEXICON_FILE.read_text())
    posts = json.loads(POSTS_FILE.read_text())

    lex_records = lexicon_records(lexicon)
    post_records_list = post_records(posts)

    if not is_live():
        print("[algolia] DRY RUN — ALGOLIA_APP_ID / ALGOLIA_ADMIN_API_KEY not set.")
        print(f"  would push {len(lex_records):,} lexicon records → {LEXICON_INDEX}")
        print(f"  would push {len(post_records_list):,} post records  → {POSTS_INDEX}")
        if lex_records:
            print("\n  sample lexicon record:")
            print("  " + json.dumps(lex_records[0], indent=2)[:600].replace("\n", "\n  ") + "…")
        if post_records_list:
            print("\n  sample post record:")
            print("  " + json.dumps(post_records_list[0], indent=2)[:600].replace("\n", "\n  ") + "…")
        return 0

    state = load_state()
    print(f"[algolia] pushing to app {app_id()}…")
    try:
        new_lex_ids = push_index(LEXICON_INDEX, lex_records, state.get(LEXICON_INDEX, []))
        new_post_ids = push_index(POSTS_INDEX, post_records_list, state.get(POSTS_INDEX, []))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        print(f"[algolia] HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"[algolia] network error: {e}", file=sys.stderr)
        return 1

    save_state({LEXICON_INDEX: new_lex_ids, POSTS_INDEX: new_post_ids})
    print(f"[algolia] done. {len(new_lex_ids):,} terms + {len(new_post_ids):,} posts indexed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

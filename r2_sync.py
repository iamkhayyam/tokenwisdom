"""
Token Wisdom — social card sync to Cloudflare R2
================================================

The rendered social cards do not belong in git. They are generated output
(make_social_cards.py, headless Chrome), they are large — 804 PNGs, 2.8 GB —
and putting them in the repo caused every problem this file exists to end:

  · generate_site.py's rmtree wiped them on every build, because they lived
    under docs/;
  · post_social_card_url() resolved each post's og:image by stat-ing the PNG on
    disk, so when the wipe removed them all 795 card references silently fell
    back to og-default.png;
  · 2.75 GB exceeds GitHub's per-push limit, which fails as an opaque HTTP 500.

R2 is the right home: object storage, 2.8 GB sits inside the free tier, and
egress is free. Git keeps only the *manifest* — data/social_cards.json, roughly
64 KB — which is what lets a CI build emit correct og:image URLs without ever
having the images on disk. That is the whole point of the split: the repo
records which cards exist, R2 holds the bytes.

Setup (once, from your account — none of this can be done from here):

  1. wrangler r2 bucket create tokenwisdom-social
  2. Bind a public custom domain to the bucket (Cloudflare dashboard →
     R2 → tokenwisdom-social → Settings → Public access → Custom domain).
     Use cdn.tokenwisdom.org. The pub-*.r2.dev URL works but Cloudflare rate
     limits it and advises against production use.
  3. Create an R2 API token (Object Read & Write) and add to .env:
       R2_ACCOUNT_ID=...
       R2_ACCESS_KEY_ID=...
       R2_SECRET_ACCESS_KEY=...
       R2_PUBLIC_BASE=https://cdn.tokenwisdom.org
  4. python3 r2_sync.py            # first run uploads everything

Follows the same safety pattern as the rest of the build: dry-runs cleanly with
no credentials, and never raises into the build.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CARDS_DIR = ROOT / "docs" / "social" / "posts"
MANIFEST = ROOT / "data" / "social_cards.json"

BUCKET = os.environ.get("R2_BUCKET", "tokenwisdom-social")
PREFIX = "posts"                      # object key prefix inside the bucket
PUBLIC_BASE = os.environ.get("R2_PUBLIC_BASE", "https://cdn.tokenwisdom.org")
MAX_WORKERS = 8


def _load_env():
    """Mirror the .env loading the rest of the build does, without a dep."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text()).get("cards", {})
        except (ValueError, OSError):
            return {}
    return {}


def public_url(name: str) -> str:
    """Public URL for a card file name (e.g. 'the-stupidity-subsidy.png')."""
    return f"{PUBLIC_BASE.rstrip('/')}/{PREFIX}/{name}"


def _client():
    """S3-compatible client pointed at R2. Returns None if unconfigured, which
    is the normal state until the bucket and token exist."""
    acct = os.environ.get("R2_ACCOUNT_ID")
    key = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not (acct and key and secret):
        return None
    try:
        import boto3
    except ImportError:
        print("  [WARN] boto3 not installed — cannot sync (pip install boto3)")
        return None
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=f"https://{acct}.r2.cloudflarestorage.com",
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name="auto",
        config=Config(retries={"max_attempts": 5, "mode": "standard"},
                      max_pool_connections=MAX_WORKERS * 2),
    )


def sync(cards_dir: Path = CARDS_DIR, quiet: bool = False) -> dict:
    """Upload changed cards, rewrite the manifest. Safe to call repeatedly.

    Change detection is by content hash, so a re-render that produces identical
    bytes costs nothing, and the 2.8 GB first upload only ever happens once.
    """
    _load_env()
    if not cards_dir.exists():
        if not quiet:
            print(f"  no cards at {cards_dir} — nothing to sync")
        return {"uploaded": 0, "skipped": 0, "total": 0, "dry_run": True}

    local = sorted(p for p in cards_dir.glob("*.png"))
    prev = load_manifest()
    digests = {p.name: _md5(p) for p in local}

    changed = [p for p in local if prev.get(p.name, {}).get("md5") != digests[p.name]]
    client = _client()

    if client is None:
        if not quiet:
            size = sum(p.stat().st_size for p in changed) / 1048576
            print(f"  [dry-run] {len(local)} cards, {len(changed)} would upload "
                  f"({size:.0f} MB) — set R2_* in .env to go live")
        return {"uploaded": 0, "skipped": len(local) - len(changed),
                "total": len(local), "dry_run": True}

    def put(p: Path):
        client.upload_file(
            str(p), BUCKET, f"{PREFIX}/{p.name}",
            ExtraArgs={"ContentType": "image/png",
                       # Cards are immutable per slug-render; if art changes the
                       # bytes change and so does the manifest entry.
                       "CacheControl": "public, max-age=31536000, immutable"},
        )
        return p.name

    uploaded, errors = 0, []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(put, p): p for p in changed}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                fut.result()
                uploaded += 1
            except Exception as e:  # noqa: BLE001 — report, don't abort the batch
                errors.append(f"{futs[fut].name}: {e}")
            if not quiet and i % 50 == 0:
                print(f"    {i}/{len(changed)} uploaded…", flush=True)

    # Manifest records every card present locally, not just the uploaded ones,
    # so a fresh clone that never renders anything still resolves every URL.
    cards = {p.name: {"md5": digests[p.name], "size": p.stat().st_size}
             for p in local}
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(
        {"base": PUBLIC_BASE, "prefix": PREFIX, "bucket": BUCKET, "cards": cards},
        indent=1, sort_keys=True))

    if not quiet:
        print(f"  {uploaded} uploaded, {len(local) - len(changed)} unchanged, "
              f"{len(local)} in manifest")
        for e in errors[:5]:
            print(f"  [WARN] {e}")
    return {"uploaded": uploaded, "skipped": len(local) - len(changed),
            "total": len(local), "errors": errors, "dry_run": False}


if __name__ == "__main__":
    print("Syncing social cards to R2…")
    r = sync()
    sys.exit(1 if r.get("errors") else 0)

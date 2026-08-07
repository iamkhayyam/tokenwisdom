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
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CARDS_DIR = ROOT / "docs" / "social" / "posts"
MANIFEST = ROOT / "data" / "social_cards.json"

PREFIX = "posts"                      # object key prefix inside the bucket
MAX_WORKERS = 8

DEFAULT_BUCKET = "tokenwisdom-social"
DEFAULT_PUBLIC_BASE = "https://cdn.tokenwisdom.org"


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


# Read AFTER .env is loaded, not at import time. As module-level constants these
# silently fell back to their defaults whenever the values lived only in .env —
# harmless while the defaults happened to match, and a wrong-bucket upload the
# moment they didn't.
def _bucket() -> str:
    return os.environ.get("R2_BUCKET") or DEFAULT_BUCKET


def _public_base() -> str:
    return os.environ.get("R2_PUBLIC_BASE") or DEFAULT_PUBLIC_BASE


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
    return f"{_public_base().rstrip('/')}/{PREFIX}/{name}"


def _creds():
    """(account, key, secret) from the environment, or None if unconfigured —
    the normal state until the bucket and token exist."""
    needed = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    missing = [k for k in needed if not os.environ.get(k)]
    if missing:
        # Name them. "set R2_* in .env" sends you hunting through five keys to
        # find the two that are actually blank.
        print(f"  missing/empty in .env: {', '.join(missing)}")
        return None
    return tuple(os.environ[k] for k in needed)


# ── AWS SigV4, stdlib only ──────────────────────────────────────────────────
#
# R2 speaks the S3 API, so uploads are signed PUTs. Deliberately not boto3:
# this repo already talks to REST APIs with urllib (see algolia_index.py), and
# on the machine this was written for, boto3 1.35 was paired with botocore 1.34
# inside Anaconda and segfaulted on import-and-connect. Signing by hand is ~40
# lines, adds no dependency, and cannot be broken by someone else's pip state.

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _put_object(acct: str, key_id: str, secret: str, bucket: str,
                obj_key: str, body: bytes, content_type: str,
                cache_control: str, timeout: int = 120):
    host = f"{acct}.r2.cloudflarestorage.com"
    region, service = "auto", "s3"
    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_uri = "/" + urllib.parse.quote(f"{bucket}/{obj_key}", safe="/~")

    # Header order matters: canonical_headers must be sorted by lowercased name,
    # and signed_headers must list exactly those names in the same order.
    headers = {
        "cache-control": cache_control,
        "content-type": content_type,
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amzdate,
    }
    signed_headers = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canonical_request = (f"PUT\n{canonical_uri}\n\n{canonical_headers}\n"
                         f"{signed_headers}\n{payload_hash}")

    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = ("AWS4-HMAC-SHA256\n"
                      f"{amzdate}\n{scope}\n"
                      f"{hashlib.sha256(canonical_request.encode()).hexdigest()}")

    k_date = _sign(f"AWS4{secret}".encode(), datestamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(),
                         hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        f"https://{host}{canonical_uri}", data=body, method="PUT")
    for k, v in headers.items():
        if k != "host":
            req.add_header(k, v)
    req.add_header("Authorization",
                   f"AWS4-HMAC-SHA256 Credential={key_id}/{scope}, "
                   f"SignedHeaders={signed_headers}, Signature={signature}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


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
    creds = _creds()

    if creds is None:
        if not quiet:
            size = sum(p.stat().st_size for p in changed) / 1048576
            print(f"  [dry-run] {len(local)} cards, {len(changed)} would upload "
                  f"({size:.0f} MB) — set R2_* in .env to go live")
        return {"uploaded": 0, "skipped": len(local) - len(changed),
                "total": len(local), "dry_run": True}

    acct, key_id, secret = creds

    def put(p: Path):
        body = p.read_bytes()
        last = None
        for attempt in range(4):  # transient 5xx / connection resets
            try:
                return _put_object(
                    acct, key_id, secret, _bucket(), f"{PREFIX}/{p.name}", body,
                    "image/png",
                    # Cards are immutable per slug-render; if the art changes the
                    # bytes change and so does the manifest entry.
                    "public, max-age=31536000, immutable")
            except urllib.error.HTTPError as e:
                # 4xx is our bug (bad signature, wrong bucket) — don't retry it.
                if e.code < 500:
                    raise RuntimeError(f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}")
                last = e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
            time.sleep(2 ** attempt)
        raise RuntimeError(str(last))

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
        {"base": _public_base(), "prefix": PREFIX, "bucket": _bucket(), "cards": cards},
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

#!/usr/bin/env python3
"""
send_issue.py — send an already-rendered issue email to every active
Token Wisdom subscriber, via the better-letter Cloudflare Worker's
/broadcasts/{customerId} endpoint.

Does NOT render the email itself — run render_email.py first. This only
reads what it already wrote (docs/issues/{slug}/email.html + email.txt)
and hands it off. Kept as a separate step, and separate script, on
purpose: rendering is safe to run any number of times; sending is not.

Dry-run by default. Sending real email to real subscribers is
irreversible, so this never fires without an explicit --send flag, and
is never called from generate_site.py or any other automatic build step.

Env:
  BETTER_LETTER_WORKER_URL   e.g. https://better-letter-agents.<acct>.workers.dev
                             (no default — this repo doesn't know the
                             Worker's deployed URL; must be set explicitly)
  BL_ADMIN_KEY               shared secret, same X-BL-Admin-Key the Worker's
                             other creator-only routes already require

Usage:
  python3 send_issue.py data/issues/2026-W23.json            # dry run
  python3 send_issue.py data/issues/2026-W23.json --send      # sends for real
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
CUSTOMER_ID = "token-wisdom"


def _issue_slug(issue):
    """Same derivation render_email.py uses — must match to find its output."""
    number = issue.get("number")
    return str(number) if number else issue["id"]


def _load_rendered(slug):
    out_dir = DOCS / "issues" / slug
    html_path = out_dir / "email.html"
    text_path = out_dir / "email.txt"
    if not html_path.exists() or not text_path.exists():
        print(f"ERROR: {html_path} and/or {text_path} not found.")
        print(f"  Run this first:  python3 render_email.py data/issues/{slug}.json")
        sys.exit(1)
    return html_path.read_text(), text_path.read_text()


def _send(subject, html, text, worker_url, admin_key):
    url = f"{worker_url.rstrip('/')}/broadcasts/{CUSTOMER_ID}"
    body = json.dumps({"subject": subject, "html": html, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "X-BL-Admin-Key": admin_key,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")), r.status
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode("utf-8")[:500]}, e.code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("issue", help="path to data/issues/{slug}.json")
    ap.add_argument("--send", action="store_true", help="actually send (default: dry run)")
    a = ap.parse_args()

    issue = json.loads(Path(a.issue).read_text())
    slug = _issue_slug(issue)
    subject = issue.get("title") or f"Token Wisdom · Week {issue.get('week')}"
    html, text = _load_rendered(slug)

    print(f"Issue:    {slug}")
    print(f"Subject:  {subject}")
    print(f"HTML:     {len(html):,} chars")
    print(f"Text:     {len(text):,} chars")
    print(f"Customer: {CUSTOMER_ID}")

    if not a.send:
        print("\n[DRY RUN] Nothing was sent. Re-run with --send to actually broadcast.")
        return

    worker_url = os.environ.get("BETTER_LETTER_WORKER_URL")
    admin_key = os.environ.get("BL_ADMIN_KEY")
    if not worker_url:
        print("\nERROR: BETTER_LETTER_WORKER_URL is not set.")
        sys.exit(1)
    if not admin_key:
        print("\nERROR: BL_ADMIN_KEY is not set.")
        sys.exit(1)

    print(f"\nSending to {worker_url} ...")
    result, status = _send(subject, html, text, worker_url, admin_key)
    if status == 200:
        print(f"Sent: {result.get('sent')}  Errors: {result.get('errors')}  "
              f"Recipients: {result.get('recipientCount')}")
    else:
        print(f"FAILED (HTTP {status}): {result.get('error', result)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

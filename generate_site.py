#!/usr/bin/env python3
"""
Token Wisdom static site generator.

Builds two consistent post templates — the essay (A Closer Look) and the
newsletter (Pearls of Wisdom / Token Wisdom Week) — plus a homepage,
tag pages, archive, and tags index, all sharing one editorial design system
(Playfair Display / Source Serif 4 / DM Sans / DM Mono).
"""

import json
import html
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

BACKUP_DIR = Path(__file__).parent
DATA_DIR = BACKUP_DIR / "data"
DOCS_DIR = BACKUP_DIR / "docs"

SITE_NAME = "Token Wisdom"
SITE_TAGLINE = "The Newsletter of Record for the Future of Now"
SITE_SIGN_OFF_LINES = [
    "Until next time:",
    "stay smart, and kind,",
    "and definitely stay weird!",
]
SITE_URL = "https://iamkhayyam.github.io/tokenwisdom"
GHOST_URL = "https://tokenwisdom.ghost.io"

# Section tag slugs — these are treated as "section" markers and hidden from the
# normal eyebrow/pill display on post pages (they move into the top-bar issue code).
SECTION_TAGS = {
    "a-closer-look": ("ACL", "A Closer Look"),
    "worthafortune": ("POW", "Pearls of Wisdom"),
    "newest-latest": ("NNL", "Newest / Latest"),
    "time-well-spent": ("TWS", "Time Well Spent"),
    "worthawarning": ("WAW", "Worth a Warning"),
    "ask-me-anything": ("AMA", "Ask Me Anything"),
}
NEWSLETTER_TAG_SLUG = "worthafortune"
ESSAY_TAG_SLUG = "a-closer-look"


# ============================================================
# DATA
# ============================================================

def load_data():
    with open(DATA_DIR / "all_posts.json") as f:
        posts = json.load(f)
    with open(DATA_DIR / "all_tags.json") as f:
        tags = json.load(f)
    with open(DATA_DIR / "all_authors.json") as f:
        authors = json.load(f)
    with open(DATA_DIR / "all_pages.json") as f:
        pages = json.load(f)
    return posts, tags, authors, pages


# ============================================================
# HELPERS
# ============================================================

def esc(text):
    return html.escape(str(text or ""))


def fmt_date(iso_str, fmt="%B %-d, %Y"):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except Exception:
        return iso_str[:10]


def fmt_date_short(iso_str):
    return fmt_date(iso_str, "%b %-d, %Y")


def fmt_week(iso_str):
    """Return '(Mon Mar 3 – Sun Mar 9)' style range for the week containing the date."""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("Week %W · %Y")
    except Exception:
        return ""


def reading_time(post):
    rt = post.get("reading_time")
    if rt:
        return f"{rt} min read"
    text = post.get("plaintext") or post.get("html") or ""
    words = len(re.findall(r"\w+", text))
    mins = max(1, words // 230)
    return f"{mins} min read"


def excerpt(post, max_len=220):
    ex = post.get("custom_excerpt") or post.get("excerpt") or ""
    if not ex and post.get("plaintext"):
        ex = post["plaintext"]
    ex = re.sub(r"\s+", " ", ex).strip()
    if len(ex) > max_len:
        ex = ex[:max_len].rsplit(" ", 1)[0] + "…"
    return esc(ex)


def primary_tag(post):
    tags = post.get("tags", []) or []
    for t in tags:
        name = t.get("name", "") or ""
        if t.get("visibility") == "public" and not name.startswith("#"):
            return t
    return tags[0] if tags else None


def author_name(post):
    authors = post.get("authors", []) or []
    return authors[0]["name"] if authors else "@iamkhayyam"


def is_newsletter(post):
    """Detect whether a post is a Token Wisdom weekly newsletter edition."""
    slug = (post.get("slug") or "").lower()
    title = (post.get("title") or "").lower()
    tags = [t.get("slug", "") for t in (post.get("tags") or [])]

    if NEWSLETTER_TAG_SLUG in tags:
        return True
    if "pearls-of-wisdom" in slug or "token-wisdom-week" in slug:
        return True
    if re.search(r"pearls of wisdom", title):
        return True
    if re.search(r"token wisdom\s*[\\/]\s*week", title):
        return True
    if re.search(r"\d+(st|nd|rd|th)\s+edition", title):
        return True
    return False


def section_code(post):
    """
    Return ('ACL', 'A Closer Look') style section marker based on the post's
    primary section tag. Used for the top-bar issue code ('ACL.164 · W14 · …').
    Essays default to ACL, newsletters default to POW.
    """
    tag_slugs = [t.get("slug", "") for t in (post.get("tags") or [])]
    for slug in tag_slugs:
        if slug in SECTION_TAGS:
            return SECTION_TAGS[slug]
    # Fallbacks by detection
    if is_newsletter(post):
        return SECTION_TAGS.get(NEWSLETTER_TAG_SLUG, ("POW", "Pearls of Wisdom"))
    return SECTION_TAGS.get(ESSAY_TAG_SLUG, ("ACL", "A Closer Look"))


def issue_number_map(posts):
    """
    Build a per-post issue number dict keyed by slug.
    Numbering is per-section, chronological (earliest = 1).
    For newsletters we prefer the explicit 'Nth Edition' number from the title
    when present; otherwise fall back to chronological index.
    """
    # Group posts by their section code
    by_section = defaultdict(list)
    for p in posts:
        code, _ = section_code(p)
        by_section[code].append(p)

    numbers = {}
    for code, group in by_section.items():
        # Sort chronologically (oldest first)
        group_sorted = sorted(
            group,
            key=lambda p: p.get("published_at") or p.get("created_at") or "",
        )
        for i, p in enumerate(group_sorted, start=1):
            # Prefer explicit edition number from title if it exists
            title = p.get("title") or ""
            m = EDITION_RX.search(title)
            if m:
                try:
                    numbers[p["slug"]] = int(m.group(1))
                    continue
                except ValueError:
                    pass
            numbers[p["slug"]] = i
    return numbers


def issue_code_string(post, number):
    """Return 'ACL.164 · W14 · Mar 26, 2026' style string."""
    code, _ = section_code(post)
    parts = [f"{code}.{number:03d}"]
    # Week number from title if available
    title = post.get("title") or ""
    slug = post.get("slug") or ""
    wk = WEEK_RX.search(title) or WEEK_RX.search(slug)
    if wk:
        parts.append(f"W{int(wk.group(1)):02d}")
    elif post.get("published_at"):
        try:
            dt = datetime.fromisoformat(post["published_at"].replace("Z", "+00:00"))
            parts.append(f"W{dt.isocalendar()[1]:02d}")
        except Exception:
            pass
    if post.get("published_at"):
        parts.append(fmt_date_short(post["published_at"]))
    return " · ".join(parts)


EDITION_RX = re.compile(r"(\d+)(st|nd|rd|th)\s+edition", re.IGNORECASE)
WEEK_RX = re.compile(r"week\s*[-_/\\\s]*0?(\d{1,2})", re.IGNORECASE)


def edition_meta(post):
    """Extract '154th Edition · Week 14' style metadata from title/slug."""
    title = post.get("title", "") or ""
    slug = post.get("slug", "") or ""

    edition = ""
    m = EDITION_RX.search(title) or EDITION_RX.search(slug)
    if m:
        edition = f"{m.group(1)}{m.group(2).lower()} Edition"

    week = ""
    m = WEEK_RX.search(title) or WEEK_RX.search(slug)
    if m:
        week = f"Week {int(m.group(1)):02d}"

    parts = [p for p in [edition, week] if p]
    return " · ".join(parts)


def clean_title(post):
    """Strip edition/week noise from a newsletter title to just the name."""
    t = post.get("title", "") or ""
    t = EDITION_RX.sub("", t)
    t = re.sub(r"🔮", "", t)
    t = re.sub(r"token wisdom\s*[\\/]\s*week\s*\d*", "Token Wisdom", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip(" -·\\/")
    return t or (post.get("title") or "")


def post_href(post, from_dir="root"):
    prefix = "" if from_dir == "root" else "../"
    return f"{prefix}posts/{post['slug']}.html"


def tag_href(tag, from_dir="root"):
    prefix = "" if from_dir == "root" else "../"
    return f"{prefix}tags/{tag['slug']}.html"


# ============================================================
# STYLESHEET — unified design system for essay + newsletter
# ============================================================

CSS = r"""
:root {
  --ink: #1a1814;
  --ink-muted: #6b6760;
  --ink-faint: #b0aca6;
  --paper: #faf8f4;
  --paper-warm: #f4f1ea;
  --paper-rule: #e6e2d9;
  --accent: #c8521a;
  --accent-muted: #e8c4ae;
  --accent-deep: #8a3610;
  --teal: #1a6b5c;
  --teal-light: #d4ede8;
  --gold: #b8860b;
  --gold-light: #f5e9c4;

  --serif: 'Source Serif 4', Georgia, serif;
  --display: 'Playfair Display', Georgia, serif;
  --sans: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono: 'DM Mono', 'SFMono-Regular', Consolas, monospace;

  --max-read: 680px;
  --max-wide: 1080px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }

body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 18px;
  line-height: 1.75;
}

a { color: var(--ink); text-decoration: none; transition: color .2s ease; }
a:hover { color: var(--accent); }
img { max-width: 100%; height: auto; }

/* ---------- POST TOP-BAR (article masthead strip) ---------- */
.post-top-bar {
  border-bottom: 2px solid var(--ink);
  background: var(--paper);
  padding: 1.1rem 1.5rem;
  display: flex;
  align-items: baseline;
  gap: 1.2rem;
  flex-wrap: wrap;
  max-width: var(--max-wide);
  margin: 0 auto;
}
.post-top-bar .ptb-brand {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.post-top-bar .ptb-brand strong {
  font-weight: 500;
  color: var(--ink);
}
.post-top-bar .ptb-issue {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .15em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.post-top-bar .ptb-issue .ptb-num {
  color: var(--accent);
  font-weight: 500;
}

/* ---------- SITE CHROME ---------- */
.site-top {
  border-bottom: 0.5px solid var(--paper-rule);
  background: var(--paper);
  position: sticky; top: 0; z-index: 80;
  backdrop-filter: blur(6px);
}
.site-top-inner {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.site-top-wordmark {
  font-family: var(--display);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  text-transform: none;
  color: var(--ink);
}
.site-top-nav {
  margin-left: auto;
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}
.site-top-nav a { color: var(--ink-muted); }
.site-top-nav a:hover { color: var(--accent); }
.site-top-date { color: var(--ink-faint); }

/* ---------- SHARED TYPOGRAPHY ---------- */
.prose { font-family: var(--serif); font-size: 18px; line-height: 1.75; color: var(--ink); }
.prose p { margin-bottom: 1.35rem; }
.prose h2 {
  font-family: var(--display);
  font-size: 1.55rem;
  font-weight: 700;
  font-style: italic;
  color: var(--ink);
  margin: 2.6rem 0 1rem;
  line-height: 1.2;
}
.prose h3 {
  font-family: var(--display);
  font-size: 1.25rem;
  font-weight: 700;
  margin: 2rem 0 .8rem;
}
.prose h4 {
  font-family: var(--mono);
  font-size: .7rem;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin: 2rem 0 .6rem;
}
.prose a { color: var(--accent); border-bottom: 1px solid var(--accent-muted); }
.prose a:hover { color: var(--accent-deep); border-color: var(--accent-deep); }
.prose strong { font-weight: 600; }
.prose em { font-style: italic; }
.prose ul, .prose ol { margin: 1.2rem 0 1.4rem 1.4rem; }
.prose li { margin-bottom: .55rem; }
.prose blockquote {
  margin: 2rem 0;
  padding: 1.2rem 1.4rem;
  background: var(--paper-warm);
  border-left: 3px solid var(--accent);
  font-family: var(--display);
  font-style: italic;
  font-size: 1.12rem;
  line-height: 1.55;
  color: var(--ink);
}
.prose blockquote p { margin-bottom: .6rem; }
.prose blockquote p:last-child { margin-bottom: 0; }
.prose img, .prose figure { margin: 2rem 0; }
.prose figure img { display: block; margin: 0 auto; }
.prose figcaption {
  font-family: var(--mono);
  font-size: .68rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ink-muted);
  text-align: center;
  margin-top: .6rem;
}
.prose hr {
  border: none;
  border-top: 0.5px solid var(--paper-rule);
  margin: 2.5rem 0;
}
.prose code {
  font-family: var(--mono);
  font-size: .88em;
  background: var(--paper-warm);
  border: 0.5px solid var(--paper-rule);
  padding: 0.1em 0.35em;
  border-radius: 2px;
}
.prose pre {
  font-family: var(--mono);
  background: var(--ink);
  color: #d4d0c8;
  padding: 1.2rem 1.4rem;
  margin: 1.8rem 0;
  overflow-x: auto;
  font-size: .82rem;
  line-height: 1.6;
}
.prose pre code {
  background: none;
  border: none;
  padding: 0;
  color: inherit;
  font-size: inherit;
}
.prose table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.8rem 0;
  font-size: .92rem;
}
.prose th, .prose td {
  padding: .55rem .8rem;
  border-bottom: 0.5px solid var(--paper-rule);
  text-align: left;
  vertical-align: top;
}
.prose th {
  font-family: var(--mono);
  font-size: .65rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.prose .kg-bookmark-card,
.prose .kg-card {
  background: var(--paper-warm);
  border: 0.5px solid var(--paper-rule);
  padding: 1rem 1.2rem;
  margin: 1.6rem 0;
  border-radius: 2px;
}
.prose .kg-bookmark-container {
  display: flex; gap: 1rem; text-decoration: none; color: var(--ink);
}
.prose .kg-bookmark-content { flex: 1; }
.prose .kg-bookmark-title { font-family: var(--display); font-weight: 700; font-size: 1.05rem; margin-bottom: .3rem; }
.prose .kg-bookmark-description { font-size: .88rem; color: var(--ink-muted); }
.prose .kg-bookmark-metadata {
  font-family: var(--mono); font-size: .65rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--ink-faint); margin-top: .5rem;
}
.prose .kg-bookmark-thumbnail { width: 120px; flex-shrink: 0; }
.prose .kg-bookmark-thumbnail img { width: 100%; object-fit: cover; }

/* ---------- ESSAY TEMPLATE ---------- */
.essay-wrap {
  max-width: var(--max-read);
  margin: 0 auto;
  padding: 3.5rem 1.5rem 5rem;
}
.essay-eyebrow {
  font-family: var(--mono);
  font-size: .62rem;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 1.3rem;
}
.essay-eyebrow a { color: var(--accent); }
.essay-title {
  font-family: var(--display);
  font-size: clamp(2.2rem, 5vw, 3.2rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -.02em;
  color: var(--ink);
  margin-bottom: .8rem;
}
.essay-deck {
  font-family: var(--serif);
  font-size: 1.08rem;
  font-weight: 300;
  color: #4a4038;
  line-height: 1.65;
  margin: 0 0 1.6rem;
  padding-bottom: 1.6rem;
  border-bottom: 0.5px solid var(--paper-rule);
}
.essay-byline {
  font-family: var(--mono);
  font-size: .62rem;
  letter-spacing: .15em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 2.4rem;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.essay-byline .sep { color: var(--ink-faint); }
.essay-feature {
  width: calc(100% + 3rem);
  margin: 0 -1.5rem 2.4rem;
  max-height: 460px;
  object-fit: cover;
}

/* ---------- NEWSLETTER TEMPLATE ---------- */
.nl-wrap {
  max-width: var(--max-read);
  margin: 0 auto;
  padding: 2.5rem 1.5rem 5rem;
  font-family: var(--sans);
}
.nl-masthead {
  border-bottom: 2px solid var(--ink);
  padding: 2rem 0 1.2rem;
  margin-bottom: 1.4rem;
}
.nl-masthead-eyebrow {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 8px;
}
.nl-masthead-eyebrow a { color: var(--ink-muted); }
.nl-masthead-title {
  font-family: var(--display);
  font-size: clamp(2.4rem, 7vw, 3.4rem);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -.02em;
  color: var(--ink);
  margin-bottom: 4px;
}
.nl-masthead-subtitle {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .12em;
  color: var(--ink-muted);
  border-top: 0.5px solid var(--paper-rule);
  padding-top: 10px;
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}
.nl-body {
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink);
}
.nl-body p { margin-bottom: 1.2rem; }
.nl-body h2 {
  font-family: var(--display);
  font-size: 1.35rem;
  font-weight: 700;
  margin: 2.3rem 0 .9rem;
  border-top: 1.5px solid var(--ink);
  padding-top: .9rem;
}
.nl-body h3 {
  font-family: var(--display);
  font-size: 1.1rem;
  font-weight: 700;
  margin: 1.8rem 0 .6rem;
}
.nl-body a { color: var(--accent); border-bottom: 0.5px solid var(--accent-muted); }
.nl-body blockquote {
  border-left: 3px solid var(--accent);
  padding: 1.1rem 1.3rem;
  margin: 1.8rem 0;
  background: var(--paper-warm);
  font-family: var(--display);
  font-style: italic;
  font-size: 1.1rem;
  line-height: 1.5;
  color: var(--ink);
}
.nl-body img, .nl-body figure { margin: 1.5rem 0; }
.nl-body ul, .nl-body ol { margin: 1rem 0 1.2rem 1.2rem; }
.nl-body li { margin-bottom: .5rem; }

/* ---------- POST META + TAGS ---------- */
.post-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 2.4rem 0 1.2rem;
}
.post-tag {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .1em;
  padding: 4px 10px;
  border: 0.5px solid var(--paper-rule);
  border-radius: 2px;
  color: var(--ink-muted);
  background: var(--paper-warm);
}
.post-tag:hover {
  color: var(--accent);
  border-color: var(--accent-muted);
}

/* ---------- POST NAV (prev / next) ---------- */
.post-nav {
  max-width: var(--max-read);
  margin: 3rem auto 0;
  padding: 1.6rem 1.5rem 0;
  border-top: 0.5px solid var(--paper-rule);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  font-family: var(--mono);
  font-size: .68rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.post-nav .pn-label { display: block; margin-bottom: 4px; color: var(--ink-faint); }
.post-nav a { color: var(--ink); font-family: var(--display); font-size: .95rem; font-weight: 600; letter-spacing: -.01em; text-transform: none; line-height: 1.3; display: block; }
.post-nav a:hover { color: var(--accent); }
.post-nav .pn-next { text-align: right; }

/* ---------- COLOPHON FOOTER ---------- */
.colophon {
  border-top: 2px solid var(--ink);
  background: var(--paper-warm);
  margin-top: 4rem;
  padding: 2.2rem 24px;
}
.colophon-inner {
  max-width: var(--max-wide);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr 1fr;
  gap: 2rem;
}
.colophon h4 {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: .8rem;
}
.colophon p, .colophon li {
  font-size: .88rem;
  color: var(--ink-muted);
  line-height: 1.6;
  font-family: var(--sans);
}
.colophon ul { list-style: none; }
.colophon li { margin-bottom: .35rem; }
.colophon a { color: var(--ink-muted); }
.colophon a:hover { color: var(--accent); }
.colophon .wordmark {
  font-family: var(--display);
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: .4rem;
  letter-spacing: -.01em;
}
.colophon .tagline {
  font-family: var(--display);
  font-style: italic;
  font-size: .95rem;
  color: var(--ink);
  margin: .5rem 0;
}
.colophon-bottom {
  max-width: var(--max-wide);
  margin: 1.8rem auto 0;
  padding-top: 1.2rem;
  border-top: 0.5px solid var(--paper-rule);
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--ink-faint);
}
.colophon-sign-off {
  font-family: var(--display);
  font-style: italic;
  font-size: .85rem;
  color: var(--ink-muted);
  text-align: right;
  text-transform: none;
  letter-spacing: 0;
  line-height: 1.4;
}

/* ---------- HOMEPAGE ---------- */
.home-wrap {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 3rem 24px 4rem;
}
.home-masthead {
  border-bottom: 2px solid var(--ink);
  padding-bottom: 1.6rem;
  margin-bottom: 2.8rem;
}
.home-masthead-eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-bottom: 10px;
}
.home-masthead-title {
  font-family: var(--display);
  font-size: clamp(3.4rem, 9vw, 6rem);
  font-weight: 700;
  line-height: .95;
  letter-spacing: -.025em;
  color: var(--ink);
}
.home-masthead-sub {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .14em;
  color: var(--ink-muted);
  border-top: 0.5px solid var(--paper-rule);
  padding-top: 12px;
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.home-grid {
  display: grid;
  grid-template-columns: 1.7fr 1fr;
  gap: 3rem;
}

.section-header {
  border-top: 1.5px solid var(--ink);
  padding: 14px 0 10px;
  margin: 2.5rem 0 1.4rem;
  display: flex;
  align-items: baseline;
  gap: 14px;
}
.section-header:first-child { margin-top: 0; }
.section-label {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.section-title {
  font-family: var(--display);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--ink);
}
.section-note {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--ink-faint);
}

/* Hero (latest newsletter) */
.hero-card {
  background: var(--ink);
  color: var(--paper);
  padding: 2.2rem 2rem 2rem;
  margin-bottom: 2.2rem;
  border-radius: 2px;
}
.hero-eyebrow {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--accent-muted);
  margin-bottom: 12px;
}
.hero-title {
  font-family: var(--display);
  font-size: clamp(1.9rem, 4vw, 2.6rem);
  font-weight: 700;
  line-height: 1.15;
  color: var(--paper);
  margin-bottom: 14px;
}
.hero-title a { color: var(--paper); }
.hero-title a:hover { color: var(--accent-muted); }
.hero-meta {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .12em;
  color: #a29c91;
  text-transform: uppercase;
  margin-bottom: 16px;
}
.hero-excerpt {
  font-family: var(--sans);
  font-size: 14.5px;
  line-height: 1.7;
  color: #d4d0c8;
  margin-bottom: 18px;
}
.hero-cta {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--accent-muted);
  border-bottom: 0.5px solid var(--accent-muted);
  padding-bottom: 2px;
}
.hero-cta:hover { color: var(--paper); }

/* Essay list items (main column) */
.essay-row {
  border-bottom: 0.5px solid var(--paper-rule);
  padding: 1.6rem 0;
}
.essay-row:first-child { border-top: 0.5px solid var(--paper-rule); }
.essay-row-eyebrow {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 6px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.essay-row-eyebrow .cat { color: var(--accent); }
.essay-row h3 {
  font-family: var(--display);
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.2;
  color: var(--ink);
  margin-bottom: 6px;
}
.essay-row h3 a:hover { color: var(--accent); }
.essay-row p {
  font-family: var(--sans);
  font-size: 14.5px;
  color: var(--ink-muted);
  line-height: 1.6;
}

/* Sidebar (newsletter index, tag cloud) */
.sidebar-block {
  background: var(--paper-warm);
  border: 0.5px solid var(--paper-rule);
  padding: 1.4rem 1.4rem 1.2rem;
  margin-bottom: 1.6rem;
  border-radius: 2px;
}
.sidebar-block h4 {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 1rem;
  padding-bottom: .5rem;
  border-bottom: 0.5px solid var(--accent-muted);
}
.sidebar-item {
  padding: .65rem 0;
  border-bottom: 0.5px solid var(--paper-rule);
}
.sidebar-item:last-child { border-bottom: none; padding-bottom: 0; }
.sidebar-item .edition {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 2px;
}
.sidebar-item h5 {
  font-family: var(--display);
  font-size: .98rem;
  font-weight: 700;
  line-height: 1.25;
  color: var(--ink);
}
.sidebar-item h5 a:hover { color: var(--accent); }

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag-cloud a {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .08em;
  padding: 4px 9px;
  border: 0.5px solid var(--paper-rule);
  border-radius: 2px;
  color: var(--ink-muted);
  background: var(--paper);
}
.tag-cloud a:hover {
  color: var(--accent);
  border-color: var(--accent-muted);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--paper-rule);
  border: 0.5px solid var(--paper-rule);
  margin-bottom: 1.6rem;
}
.stat {
  background: var(--paper-warm);
  padding: 1rem .8rem;
  text-align: center;
}
.stat .num {
  font-family: var(--display);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
}
.stat .label {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--ink-muted);
  margin-top: 4px;
}

/* ---------- TAG PAGE HEADER (magnified GIF background) ---------- */
.tag-hero {
  position: relative;
  overflow: hidden;
  border-bottom: 2px solid var(--ink);
  isolation: isolate;
  padding: 4.5rem 1.5rem 3.5rem;
  text-align: center;
  min-height: 380px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.tag-hero::before {
  content: '';
  position: absolute;
  inset: -8%;
  background-image: var(--tag-bg);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  filter: blur(36px) saturate(1.15) brightness(.82);
  transform: scale(1.25);
  z-index: -2;
}
.tag-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg,
    rgba(250,248,244,.55) 0%,
    rgba(250,248,244,.45) 50%,
    rgba(250,248,244,.82) 100%);
  z-index: -1;
}
.tag-hero-inner {
  max-width: var(--max-wide);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.2rem;
}
.tag-hero-eyebrow {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--paper);
  padding: 6px 14px;
  border: 0.5px solid var(--accent-muted);
  border-radius: 2px;
}
.tag-hero-gif {
  width: clamp(180px, 22vw, 260px);
  aspect-ratio: 1;
  object-fit: cover;
  border: 3px solid var(--ink);
  border-radius: 8px;
  box-shadow: 0 24px 60px -20px rgba(26, 24, 20, .4);
  background: var(--paper);
}
.tag-hero h1 {
  font-family: var(--display);
  font-size: clamp(2.4rem, 6vw, 3.8rem);
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -.02em;
  color: var(--ink);
  margin: 0;
  text-shadow: 0 2px 20px rgba(250,248,244,.9);
}
.tag-hero .desc {
  font-family: var(--display);
  font-style: italic;
  font-size: clamp(1.05rem, 2vw, 1.3rem);
  color: var(--ink);
  max-width: var(--max-read);
  line-height: 1.5;
  margin: 0;
}
.tag-hero .meta {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--ink-muted);
  background: var(--paper);
  padding: 5px 12px;
  border: 0.5px solid var(--paper-rule);
  border-radius: 2px;
}
.tag-list {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 3rem 24px 3rem;
}
.tag-list > .tag-list-heading {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--ink-muted);
  border-top: 1.5px solid var(--ink);
  padding: 14px 0 10px;
  margin-bottom: 1.4rem;
}

/* Simple reused .tag-header for Archive / Tags-index (no GIF background) */
.tag-header {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 3.5rem 24px 2rem;
  border-bottom: 2px solid var(--ink);
  margin-bottom: 2rem;
}
.tag-header .eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 10px;
}
.tag-header h1 {
  font-family: var(--display);
  font-size: clamp(2.4rem, 6vw, 3.6rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -.02em;
  color: var(--ink);
  margin-bottom: .6rem;
}
.tag-header .desc {
  font-family: var(--serif);
  font-size: 1.1rem;
  color: var(--ink-muted);
  max-width: var(--max-read);
  line-height: 1.65;
  margin-bottom: 1rem;
}
.tag-header .meta {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--ink-faint);
}

/* ---------- TOPICS INDEX (billboard grid) ---------- */
.topics-wrap {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 2.5rem 24px 4rem;
}
.topics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.6rem;
}
.topic-card {
  display: block;
  position: relative;
  background: var(--paper-warm);
  border: 1px solid var(--paper-rule);
  border-radius: 4px;
  overflow: hidden;
  color: var(--ink);
  transition: transform .25s ease, border-color .25s ease, box-shadow .25s ease;
}
.topic-card:hover {
  transform: translateY(-3px);
  border-color: var(--accent);
  box-shadow: 0 18px 40px -20px rgba(26, 24, 20, .35);
  color: var(--ink);
}
.topic-card .gif-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  background: var(--ink);
}
.topic-card .gif-frame img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform .4s ease;
}
.topic-card:hover .gif-frame img { transform: scale(1.04); }
.topic-card .gif-frame::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg,
    rgba(26, 24, 20, 0) 45%,
    rgba(26, 24, 20, .75) 100%);
}
.topic-card .label {
  position: absolute;
  top: 14px;
  left: 14px;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--paper);
  background: rgba(26, 24, 20, .72);
  padding: 5px 10px;
  border-radius: 2px;
  z-index: 2;
}
.topic-card .name {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 14px;
  font-family: var(--display);
  font-size: 1.55rem;
  font-weight: 700;
  line-height: 1.15;
  color: var(--paper);
  letter-spacing: -.01em;
  text-shadow: 0 2px 16px rgba(0,0,0,.5);
  z-index: 2;
}
.topic-card .desc {
  padding: 1rem 1.1rem 1.1rem;
  font-family: var(--sans);
  font-size: .88rem;
  line-height: 1.55;
  color: var(--ink-muted);
  border-top: 1px solid var(--paper-rule);
  min-height: 4.5em;
}
.topic-card .desc:empty { display: none; }

/* Featured topic billboards (first two) take full width */
.topic-card.is-featured {
  grid-column: span 3;
}
.topic-card.is-featured .gif-frame {
  aspect-ratio: 21 / 9;
}
.topic-card.is-featured .name {
  font-size: 2.6rem;
  max-width: 70%;
}
@media (max-width: 1024px) {
  .topics-grid { grid-template-columns: repeat(2, 1fr); }
  .topic-card.is-featured { grid-column: span 2; }
}
@media (max-width: 640px) {
  .topics-grid { grid-template-columns: 1fr; gap: 1.2rem; }
  .topic-card.is-featured { grid-column: span 1; }
  .topic-card.is-featured .gif-frame { aspect-ratio: 16 / 10; }
  .topic-card.is-featured .name { font-size: 1.6rem; max-width: 100%; }
}

/* ---------- ARCHIVE ---------- */
.archive-wrap {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 3rem 24px 4rem;
}
.archive-year {
  font-family: var(--display);
  font-size: 2.2rem;
  font-weight: 700;
  color: var(--ink);
  border-top: 2px solid var(--ink);
  padding-top: 14px;
  margin: 2.4rem 0 1rem;
  letter-spacing: -.01em;
}
.archive-year:first-child { margin-top: 0; }
.archive-item {
  display: grid;
  grid-template-columns: 110px 1fr auto;
  gap: 1.2rem;
  padding: .85rem 0;
  border-bottom: 0.5px solid var(--paper-rule);
  align-items: baseline;
}
.archive-item .when {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ink-faint);
}
.archive-item h3 {
  font-family: var(--display);
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--ink);
}
.archive-item h3 a:hover { color: var(--accent); }
.archive-item .tag {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--accent);
  white-space: nowrap;
}

/* ---------- TAGS INDEX ---------- */
.tags-index-wrap {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 3rem 24px 4rem;
}
.tags-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
  margin-top: 2rem;
}
.tag-card {
  background: var(--paper-warm);
  border: 0.5px solid var(--paper-rule);
  padding: 1.2rem 1.2rem 1rem;
  border-radius: 2px;
  display: block;
  color: var(--ink);
  transition: border-color .2s ease, transform .2s ease;
}
.tag-card:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
  color: var(--ink);
}
.tag-card .name {
  font-family: var(--display);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 4px;
  line-height: 1.25;
}
.tag-card .count {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 6px;
}
.tag-card .desc {
  font-family: var(--sans);
  font-size: .85rem;
  color: var(--ink-muted);
  line-height: 1.55;
}

/* ---------- RESPONSIVE ---------- */
@media (max-width: 900px) {
  .home-grid { grid-template-columns: 1fr; gap: 2rem; }
  .colophon-inner { grid-template-columns: 1fr 1fr; }
  .archive-item { grid-template-columns: 90px 1fr; }
  .archive-item .tag { grid-column: 2; justify-self: start; margin-top: 2px; }
}
@media (max-width: 600px) {
  body { font-size: 17px; }
  .site-top-inner { padding: 10px 16px; gap: 12px; font-size: 9px; }
  .site-top-nav { gap: 12px; }
  .colophon-inner { grid-template-columns: 1fr; gap: 1.4rem; }
  .colophon-bottom { flex-direction: column; }
  .colophon-sign-off { text-align: left; }
  .essay-wrap, .nl-wrap { padding-left: 1rem; padding-right: 1rem; }
  .post-nav { grid-template-columns: 1fr; }
  .post-nav .pn-next { text-align: left; }
  .home-masthead-title { letter-spacing: -.03em; }
}
"""


# ============================================================
# FRAGMENT BUILDERS
# ============================================================

def head_tag(title):
    fonts = (
        "https://fonts.googleapis.com/css2?"
        "family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400;1,700&"
        "family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,300;1,8..60,400&"
        "family=DM+Sans:wght@300;400;500;600&"
        "family=DM+Mono:wght@400;500&display=swap"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)} — {SITE_NAME}</title>
<meta name="description" content="{esc(SITE_TAGLINE)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<link rel="stylesheet" href="{{css_path}}">
</head>
<body>
"""


def site_top(from_dir="root"):
    prefix = "" if from_dir == "root" else "../"
    today = datetime.now().strftime("%a · %b %-d, %Y").upper()
    return f"""
<div class="site-top">
  <div class="site-top-inner">
    <a href="{prefix}index.html" class="site-top-wordmark">🔮 Token Wisdom</a>
    <nav class="site-top-nav">
      <a href="{prefix}index.html">Home</a>
      <a href="{prefix}archive.html">Archive</a>
      <a href="{prefix}tags/index.html">Topics</a>
      <a href="{prefix}tags/a-closer-look.html">Essays</a>
      <a href="{prefix}tags/worthafortune.html">Newsletters</a>
    </nav>
    <span class="site-top-date">{today}</span>
  </div>
</div>
"""


def colophon(posts_count, tags_count, years_span, top_tags, from_dir="root"):
    prefix = "" if from_dir == "root" else "../"
    tag_links = "\n".join(
        f'      <li><a href="{prefix}tags/{t["slug"]}.html">{esc(t["name"])}</a></li>'
        for t in top_tags[:6]
    )
    sign_off = "<br>".join(esc(line) for line in SITE_SIGN_OFF_LINES)
    return f"""
<footer class="colophon">
  <div class="colophon-inner">
    <div>
      <div class="wordmark">Token Wisdom</div>
      <p>{esc(SITE_TAGLINE)}</p>
      <p class="tagline">Knowware is measured in lifetimes</p>
      <p style="margin-top:.6rem;">By <strong>@iamkhayyam</strong> · ARC Institute of Knowware</p>
    </div>
    <div>
      <h4>Sections</h4>
      <ul>
        <li><a href="{prefix}index.html">Home</a></li>
        <li><a href="{prefix}archive.html">Archive</a></li>
        <li><a href="{prefix}tags/index.html">All Tags</a></li>
        <li><a href="{prefix}tags/a-closer-look.html">Essays</a></li>
      </ul>
    </div>
    <div>
      <h4>Popular Tags</h4>
      <ul>
{tag_links}
      </ul>
    </div>
    <div>
      <h4>Elsewhere</h4>
      <ul>
        <li><a href="{GHOST_URL}" target="_blank" rel="noopener">tokenwisdom.ghost.io</a></li>
        <li><a href="https://github.com/iamkhayyam/tokenwisdom" target="_blank" rel="noopener">GitHub Archive</a></li>
      </ul>
    </div>
  </div>
  <div class="colophon-bottom">
    <span>🔮 Token Wisdom · {posts_count} Posts · {tags_count} Tags · {years_span} · 100% Authentic Humanly Chosen</span>
    <span class="colophon-sign-off">{sign_off}</span>
  </div>
</footer>
</body>
</html>
"""


def page_shell(title, body, css_path, from_dir="root"):
    head = head_tag(title).format(css_path=css_path)
    return head + site_top(from_dir) + body


# ============================================================
# POST PAGES
# ============================================================

def render_post_top_bar(post, issue_num):
    """Top-bar masthead strip: 'Token Wisdom · by @iamkhayyam'  |  'ACL.164 · W14 · Mar 26, 2026'"""
    issue = issue_code_string(post, issue_num)
    code, label = section_code(post)
    return f"""
<div class="post-top-bar">
  <span class="ptb-brand"><strong>Token Wisdom</strong> · by @iamkhayyam</span>
  <span class="ptb-issue"><span class="ptb-num">{esc(issue)}</span></span>
</div>
"""


def secondary_eyebrow_tags(post):
    """
    Return up to 3 non-section tags as a descriptive eyebrow string
    ('Mathematics · Origin Story · Constitutional Forcing'). Section tags
    like A Closer Look / Pearls of Wisdom are filtered out because they
    now live in the top-bar issue code.
    """
    out = []
    for t in post.get("tags") or []:
        slug = t.get("slug", "")
        name = t.get("name", "") or ""
        if slug in SECTION_TAGS:
            continue
        if name.startswith("#"):
            continue
        out.append(name)
        if len(out) >= 3:
            break
    return " · ".join(out)


def render_essay_post(post, prev_post, next_post, posts_count, tags_count, years_span, top_tags, issue_num):
    tags = post.get("tags") or []

    eyebrow_text = secondary_eyebrow_tags(post)
    tag_eyebrow = ""
    if eyebrow_text:
        tag_eyebrow = f'<div class="essay-eyebrow">{esc(eyebrow_text)}</div>'

    deck = ""
    custom = post.get("custom_excerpt") or post.get("excerpt") or ""
    if custom:
        deck = f'<p class="essay-deck">{esc(custom.strip())}</p>'

    tag_pills = ""
    if tags:
        pills = "".join(
            f'<a class="post-tag" href="../tags/{t["slug"]}.html">{esc(t.get("name", ""))}</a>'
            for t in tags
            if not (t.get("name", "") or "").startswith("#")
            and t.get("slug", "") not in SECTION_TAGS
        )
        tag_pills = f'<div class="post-tags">{pills}</div>' if pills else ""

    content = post.get("html") or f"<p>{esc(post.get('plaintext') or '')}</p>"

    nav_prev = ""
    nav_next = ""
    if prev_post:
        nav_prev = f"""
    <div class="pn-prev">
      <span class="pn-label">← Previous</span>
      <a href="{prev_post['slug']}.html">{esc(prev_post.get('title', ''))}</a>
    </div>"""
    else:
        nav_prev = '<div></div>'
    if next_post:
        nav_next = f"""
    <div class="pn-next">
      <span class="pn-label">Next →</span>
      <a href="{next_post['slug']}.html">{esc(next_post.get('title', ''))}</a>
    </div>"""
    else:
        nav_next = '<div></div>'

    body = render_post_top_bar(post, issue_num) + f"""
<article class="essay-wrap">
  {tag_eyebrow}
  <h1 class="essay-title">{esc(post.get('title', ''))}</h1>
  {deck}
  <div class="essay-byline">
    <span>By {esc(author_name(post))}</span>
    <span class="sep">·</span>
    <span>{fmt_date(post.get('published_at'))}</span>
    <span class="sep">·</span>
    <span>{reading_time(post)}</span>
  </div>
  <div class="prose">
    {content}
  </div>
  {tag_pills}
</article>
<nav class="post-nav">
  {nav_prev}
  {nav_next}
</nav>
"""
    page = page_shell(post.get("title", ""), body, "../style.css", from_dir="sub")
    page += colophon(posts_count, tags_count, years_span, top_tags, from_dir="sub")
    return page


def render_newsletter_post(post, prev_post, next_post, posts_count, tags_count, years_span, top_tags, issue_num):
    tags = post.get("tags") or []
    meta = edition_meta(post)
    nice_title = clean_title(post).strip() or post.get("title", "")

    # Subtitle row: left = edition meta, right = week range / badge
    left_parts = []
    if meta:
        left_parts.append(esc(meta))
    left_parts.append(esc(fmt_date(post.get("published_at"))))
    left_html = " · ".join(left_parts)
    subtitle_html = (
        f'<span>{left_html}</span>'
        f'<span>🔮 100% Authentic Humanly Chosen</span>'
    )

    tag_pills = ""
    if tags:
        pills = "".join(
            f'<a class="post-tag" href="../tags/{t["slug"]}.html">{esc(t.get("name", ""))}</a>'
            for t in tags
            if not (t.get("name", "") or "").startswith("#")
            and t.get("slug", "") not in SECTION_TAGS
        )
        tag_pills = f'<div class="post-tags">{pills}</div>' if pills else ""

    content = post.get("html") or f"<p>{esc(post.get('plaintext') or '')}</p>"

    nav_prev = ""
    nav_next = ""
    if prev_post:
        nav_prev = f"""
    <div class="pn-prev">
      <span class="pn-label">← Previous Edition</span>
      <a href="{prev_post['slug']}.html">{esc(clean_title(prev_post) or prev_post.get('title', ''))}</a>
    </div>"""
    else:
        nav_prev = '<div></div>'
    if next_post:
        nav_next = f"""
    <div class="pn-next">
      <span class="pn-label">Next Edition →</span>
      <a href="{next_post['slug']}.html">{esc(clean_title(next_post) or next_post.get('title', ''))}</a>
    </div>"""
    else:
        nav_next = '<div></div>'

    body = render_post_top_bar(post, issue_num) + f"""
<article class="nl-wrap">
  <header class="nl-masthead">
    <div class="nl-masthead-eyebrow">{esc(SITE_TAGLINE)}</div>
    <div class="nl-masthead-title">{esc(nice_title)}</div>
    <div class="nl-masthead-subtitle">
      {subtitle_html}
    </div>
  </header>
  <div class="nl-body prose">
    {content}
  </div>
  {tag_pills}
</article>
<nav class="post-nav">
  {nav_prev}
  {nav_next}
</nav>
"""
    page = page_shell(post.get("title", ""), body, "../style.css", from_dir="sub")
    page += colophon(posts_count, tags_count, years_span, top_tags, from_dir="sub")
    return page


# ============================================================
# HOMEPAGE
# ============================================================

def render_homepage(posts, tags_by_slug, tag_to_posts, top_tags, years_span):
    sorted_posts = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"], reverse=True,
    )

    newsletters = [p for p in sorted_posts if is_newsletter(p)]
    essays = [p for p in sorted_posts if not is_newsletter(p)]

    hero = newsletters[0] if newsletters else sorted_posts[0]
    hero_is_nl = is_newsletter(hero)
    hero_meta = edition_meta(hero)
    hero_title = clean_title(hero) if hero_is_nl else hero.get("title", "")
    hero_meta_line = " · ".join(filter(None, [hero_meta, fmt_date(hero.get("published_at"))]))
    if not hero_meta_line:
        hero_meta_line = fmt_date(hero.get("published_at"))

    # Main column: recent essays
    essay_rows = ""
    for p in essays[:14]:
        tag = primary_tag(p)
        cat = ""
        if tag:
            cat = f'<span class="cat">{esc(tag["name"])}</span><span>·</span>'
        essay_rows += f"""
  <article class="essay-row">
    <div class="essay-row-eyebrow">
      {cat}
      <span>{fmt_date_short(p.get('published_at'))}</span>
      <span>·</span>
      <span>{reading_time(p)}</span>
    </div>
    <h3><a href="posts/{p['slug']}.html">{esc(p.get('title', ''))}</a></h3>
    <p>{excerpt(p, 200)}</p>
  </article>"""

    # Sidebar: recent newsletters
    nl_items = ""
    for p in newsletters[1:11]:
        meta = edition_meta(p) or fmt_date_short(p.get("published_at"))
        nl_items += f"""
    <div class="sidebar-item">
      <div class="edition">{esc(meta)}</div>
      <h5><a href="posts/{p['slug']}.html">{esc(clean_title(p) or p.get('title', ''))}</a></h5>
    </div>"""

    # Tag cloud
    cloud_links = "".join(
        f'<a href="tags/{t["slug"]}.html">{esc(t["name"])} <span style="color:var(--ink-faint);">{len(tag_to_posts.get(t["slug"], []))}</span></a>'
        for t in top_tags[:20]
    )

    stats = f"""
  <div class="stats-row">
    <div class="stat"><div class="num">{len(posts)}</div><div class="label">Posts</div></div>
    <div class="stat"><div class="num">{len(newsletters)}</div><div class="label">Editions</div></div>
    <div class="stat"><div class="num">{len(tags_by_slug)}</div><div class="label">Tags</div></div>
  </div>
"""

    today_sub = datetime.now().strftime("%B %-d, %Y")
    body = f"""
<div class="home-wrap">

  <header class="home-masthead">
    <div class="home-masthead-eyebrow">{esc(SITE_TAGLINE)}</div>
    <h1 class="home-masthead-title">Token Wisdom</h1>
    <div class="home-masthead-sub">
      <span>{len(newsletters)} Editions · {len(essays)} Essays · {years_span}</span>
      <span>{esc(today_sub)}</span>
      <span>🔮 100% Authentic Humanly Chosen</span>
    </div>
  </header>

  <div class="home-grid">
    <div>
      <div class="section-header">
        <span class="section-label">§ 01</span>
        <span class="section-title">This Week</span>
        <span class="section-note">Latest Edition</span>
      </div>

      <article class="hero-card">
        <div class="hero-eyebrow">🔮 {esc(hero_meta or 'Token Wisdom')}</div>
        <h2 class="hero-title"><a href="posts/{hero['slug']}.html">{esc(hero_title)}</a></h2>
        <div class="hero-meta">{esc(hero_meta_line)} · {reading_time(hero)}</div>
        <p class="hero-excerpt">{excerpt(hero, 280)}</p>
        <a class="hero-cta" href="posts/{hero['slug']}.html">Read the issue →</a>
      </article>

      <div class="section-header">
        <span class="section-label">§ 02</span>
        <span class="section-title">A Closer Look</span>
        <span class="section-note">Essays</span>
      </div>
      <div class="essay-list">
        {essay_rows}
      </div>

      <div style="text-align:center; margin-top: 2rem;">
        <a href="archive.html" style="font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); border: 0.5px solid var(--accent-muted); padding: 10px 18px; display: inline-block;">View Full Archive →</a>
      </div>
    </div>

    <aside>
      {stats}
      <div class="sidebar-block">
        <h4>🔮 Recent Editions</h4>
        {nl_items}
        <div style="margin-top: 1rem; text-align: right;">
          <a href="tags/worthafortune.html" style="font-family: var(--mono); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--accent);">All editions →</a>
        </div>
      </div>
      <div class="sidebar-block">
        <h4>Topics</h4>
        <div class="tag-cloud">
          {cloud_links}
        </div>
        <div style="margin-top: 1rem; text-align: right;">
          <a href="tags/index.html" style="font-family: var(--mono); font-size: 10px; letter-spacing: .1em; text-transform: uppercase; color: var(--accent);">All tags →</a>
        </div>
      </div>
    </aside>
  </div>
</div>
"""
    page = page_shell(SITE_NAME, body, "style.css", from_dir="root")
    page += colophon(len(posts), len(tags_by_slug), years_span, top_tags, from_dir="root")
    return page


# ============================================================
# TAG PAGE
# ============================================================

def render_tag_page(tag, posts_for_tag, posts_count, tags_count, years_span, top_tags):
    sorted_posts = sorted(
        posts_for_tag,
        key=lambda p: p.get("published_at", ""),
        reverse=True,
    )

    rows = ""
    for p in sorted_posts:
        tg = primary_tag(p)
        cat = ""
        if tg and tg.get("slug") != tag.get("slug"):
            cat = f'<span class="cat">{esc(tg["name"])}</span><span>·</span>'
        meta = edition_meta(p) if is_newsletter(p) else ""
        if meta:
            cat = f'<span class="cat">{esc(meta)}</span><span>·</span>'
        rows += f"""
  <article class="essay-row">
    <div class="essay-row-eyebrow">
      {cat}
      <span>{fmt_date_short(p.get('published_at'))}</span>
      <span>·</span>
      <span>{reading_time(p)}</span>
    </div>
    <h3><a href="../posts/{p['slug']}.html">{esc(p.get('title', ''))}</a></h3>
    <p>{excerpt(p, 220)}</p>
  </article>"""

    desc = tag.get("description") or ""
    desc_html = f'<p class="desc">{esc(desc)}</p>' if desc else ""

    feature_img = tag.get("feature_image") or ""
    date_range = ""
    if sorted_posts:
        latest = fmt_date_short(sorted_posts[0].get("published_at"))
        earliest = fmt_date_short(sorted_posts[-1].get("published_at"))
        date_range = f"{earliest} – {latest}"

    count_label = f"{len(sorted_posts)} Post{'s' if len(sorted_posts) != 1 else ''}"
    gif_html = ""
    if feature_img:
        gif_html = f'<img class="tag-hero-gif" src="{esc(feature_img)}" alt="{esc(tag.get("name", ""))}" loading="eager">'

    body = f"""
<header class="tag-hero" style="--tag-bg: url('{esc(feature_img)}');">
  <div class="tag-hero-inner">
    <span class="tag-hero-eyebrow">§ Topic</span>
    {gif_html}
    <h1>{esc(tag.get('name', ''))}</h1>
    {desc_html}
    <span class="meta">{count_label} · {esc(date_range)}</span>
  </div>
</header>
<div class="tag-list">
  <div class="tag-list-heading">§ All posts</div>
  {rows}
</div>
"""
    page = page_shell(tag.get("name", ""), body, "../style.css", from_dir="sub")
    page += colophon(posts_count, tags_count, years_span, top_tags, from_dir="sub")
    return page


# ============================================================
# ARCHIVE
# ============================================================

def render_archive(posts, posts_count, tags_count, years_span, top_tags):
    sorted_posts = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"], reverse=True,
    )
    by_year = defaultdict(list)
    for p in sorted_posts:
        by_year[p["published_at"][:4]].append(p)

    sections = ""
    for year in sorted(by_year.keys(), reverse=True):
        items = ""
        for p in by_year[year]:
            tg = primary_tag(p)
            tag_label = ""
            if is_newsletter(p):
                tag_label = esc(edition_meta(p) or "Newsletter")
            elif tg:
                tag_label = esc(tg["name"])
            items += f"""
  <div class="archive-item">
    <div class="when">{fmt_date_short(p.get('published_at'))}</div>
    <h3><a href="posts/{p['slug']}.html">{esc(p.get('title', ''))}</a></h3>
    <span class="tag">{tag_label}</span>
  </div>"""
        sections += f"""
<h2 class="archive-year">{year}</h2>
{items}
"""

    body = f"""
<header class="tag-header">
  <div class="eyebrow">§ Complete Archive</div>
  <h1>The Archive</h1>
  <p class="desc">Every post published, grouped by year. {len(sorted_posts)} posts across {len(by_year)} years.</p>
  <div class="meta">{years_span}</div>
</header>
<div class="archive-wrap">
  {sections}
</div>
"""
    page = page_shell("Archive", body, "style.css", from_dir="root")
    page += colophon(posts_count, tags_count, years_span, top_tags, from_dir="root")
    return page


# ============================================================
# TAGS INDEX
# ============================================================

def render_tags_index(tags, tag_to_posts, posts_count, tags_count, years_span, top_tags):
    visible = [t for t in tags if not (t.get("name", "") or "").startswith("#")]
    visible.sort(key=lambda t: len(tag_to_posts.get(t["slug"], [])), reverse=True)

    cards = ""
    for i, t in enumerate(visible):
        count = len(tag_to_posts.get(t["slug"], []))
        desc = (t.get("description") or "").strip()
        desc_html = f'<div class="desc">{esc(desc[:140])}{"…" if len(desc) > 140 else ""}</div>' if desc else '<div class="desc"></div>'
        feature_img = t.get("feature_image") or ""
        img_html = ""
        if feature_img:
            img_html = f'<img src="{esc(feature_img)}" alt="{esc(t.get("name", ""))}" loading="lazy">'
        # The two highest-post-count tags become full-width featured billboards
        featured_class = " is-featured" if i < 2 else ""
        cards += f"""
  <a class="topic-card{featured_class}" href="{t['slug']}.html">
    <div class="gif-frame">
      {img_html}
      <span class="label">{count} post{'s' if count != 1 else ''}</span>
      <div class="name">{esc(t['name'])}</div>
    </div>
    {desc_html}
  </a>"""

    body = f"""
<header class="tag-header">
  <div class="eyebrow">§ Topics Index</div>
  <h1>Explore Topics</h1>
  <p class="desc">{len(visible)} topics across {posts_count} posts. Every tag, every GIF, every thread in one place. Click anything to dive in.</p>
  <div class="meta">{esc(years_span)} · {len(visible)} tags · 100% authentic humanly chosen</div>
</header>
<div class="topics-wrap">
  <div class="topics-grid">
  {cards}
  </div>
</div>
"""
    page = page_shell("All Tags", body, "../style.css", from_dir="sub")
    page += colophon(posts_count, tags_count, years_span, top_tags, from_dir="sub")
    return page


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("TOKEN WISDOM SITE GENERATOR")
    print("=" * 60)

    posts, tags, authors, pages = load_data()
    print(f"Loaded: {len(posts)} posts, {len(tags)} tags, {len(authors)} authors")

    # Build relationships
    tag_to_posts = defaultdict(list)
    for post in posts:
        for t in post.get("tags", []) or []:
            tag_to_posts[t["slug"]].append(post)

    tags_by_slug = {t["slug"]: t for t in tags}
    public_tags = [t for t in tags if not (t.get("name", "") or "").startswith("#")]
    top_tags = sorted(public_tags, key=lambda t: len(tag_to_posts.get(t["slug"], [])), reverse=True)

    # Year span
    years = [p["published_at"][:4] for p in posts if p.get("published_at")]
    years_span = f"{min(years)}–{max(years)}" if years else ""

    # Sort posts chronologically for prev/next navigation
    chrono = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"],
    )
    index_of = {p["slug"]: i for i, p in enumerate(chrono)}

    # Per-section issue numbers (ACL.001, POW.153, etc.)
    issue_nums = issue_number_map(posts)

    # Prev/next within same category (essay/newsletter) for more contextual nav
    def siblings(post):
        same = [p for p in chrono if is_newsletter(p) == is_newsletter(post)]
        idx_map = {p["slug"]: i for i, p in enumerate(same)}
        idx = idx_map.get(post["slug"])
        if idx is None:
            return None, None
        prev = same[idx - 1] if idx > 0 else None
        nxt = same[idx + 1] if idx < len(same) - 1 else None
        return prev, nxt

    # Clean output
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir()
    (DOCS_DIR / "posts").mkdir()
    (DOCS_DIR / "tags").mkdir()

    # Write CSS
    print("Writing stylesheet…")
    with open(DOCS_DIR / "style.css", "w") as f:
        f.write(CSS)

    posts_count = len(posts)
    tags_count = len(public_tags)

    # Homepage
    print("Homepage…")
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(render_homepage(posts, tags_by_slug, tag_to_posts, top_tags, years_span))

    # Archive
    print("Archive…")
    with open(DOCS_DIR / "archive.html", "w") as f:
        f.write(render_archive(posts, posts_count, tags_count, years_span, top_tags))

    # Post pages
    nl_count = 0
    essay_count = 0
    print(f"Post pages ({len(posts)})…")
    for i, post in enumerate(posts):
        slug = post.get("slug", "unknown")
        prev_p, next_p = siblings(post)
        num = issue_nums.get(slug, 0)
        if is_newsletter(post):
            html_out = render_newsletter_post(post, prev_p, next_p, posts_count, tags_count, years_span, top_tags, num)
            nl_count += 1
        else:
            html_out = render_essay_post(post, prev_p, next_p, posts_count, tags_count, years_span, top_tags, num)
            essay_count += 1
        with open(DOCS_DIR / "posts" / f"{slug}.html", "w") as f:
            f.write(html_out)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(posts)}")
    print(f"  Essays: {essay_count}  ·  Newsletters: {nl_count}")

    # Tag pages
    print(f"Tag pages ({len(public_tags)})…")
    for t in public_tags:
        posts_for_tag = tag_to_posts.get(t["slug"], [])
        with open(DOCS_DIR / "tags" / f"{t['slug']}.html", "w") as f:
            f.write(render_tag_page(t, posts_for_tag, posts_count, tags_count, years_span, top_tags))

    # Tags index
    with open(DOCS_DIR / "tags" / "index.html", "w") as f:
        f.write(render_tags_index(tags, tag_to_posts, posts_count, tags_count, years_span, top_tags))

    # .nojekyll
    with open(DOCS_DIR / ".nojekyll", "w") as f:
        f.write("")

    html_count = len(list(DOCS_DIR.glob("**/*.html")))
    print()
    print("=" * 60)
    print(f"SITE GENERATED")
    print(f"  HTML pages: {html_count}")
    print(f"  Essays: {essay_count}")
    print(f"  Newsletters: {nl_count}")
    print(f"  Tags: {len(public_tags)}")
    print(f"  Output: {DOCS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

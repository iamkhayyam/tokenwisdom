"""
Token Wisdom — Discoverability layer
====================================

Sitemaps, canonical tags, structured data, a site feed, and llms.txt. Runs as a
post-pass over the finished docs/ tree, after every page has been written.

Why a post-pass rather than threading this through the generators: the site is
2,444 pages emitted from ~14 different call sites, only two of which knew their
own URL. Deriving everything from the file's path on disk means no page can be
forgotten, and canonical/sitemap URLs are guaranteed to agree with each other.

URL form matters here. Cloudflare Pages serves this site extensionless —
/posts/foo.html 308-redirects to /posts/foo — so every URL this module emits is
the extensionless form. A canonical or sitemap entry pointing at a redirect is a
wasted crawl at best and an ignored signal at worst.

What it produces:

  <link rel="canonical">   on every page. The most load-bearing piece: the Ghost
                           origin serves a complete copy of every post and emits
                           no canonical of its own, so tokenwisdom.org has been
                           competing with its own CMS for its own content.
  sitemap.xml              a sitemap index over four child sitemaps (pages,
                           posts, lexicon, tags), split by section so indexing
                           problems can be diagnosed per section instead of as
                           one 2,400-line lump.
  JSON-LD                  WebSite + Organization on the homepage (including the
                           SearchAction that points at our new /search),
                           BlogPosting on posts, DefinedTerm on Lexicon entries.
  feed.xml                 RSS 2.0 for the writing. The site had a podcast feed
                           but no article feed.
  llms.txt                 the llmstxt.org convention — a plain-text map of the
                           site for models reading it as reference.

Pages carrying <meta name="robots" content="noindex"> (the 404 and any hidden
post) are excluded from the sitemap and the feed, but still get a canonical.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"

SITE_URL = "https://tokenwisdom.org"
SITE_NAME = "Token Wisdom"
SITE_TAGLINE = "The Newsletter of Record for the Future of Now"
SITE_DESC = ("The Newsletter of Record for the Future of Now. "
             "100% humanly chosen since 2013.")
DEFAULT_IMAGE = f"{SITE_URL}/assets/og-default.png"
FEED_ITEMS = 40

# Sections that get their own child sitemap. Anything not matching falls into
# "pages" — the handful of top-level routes.
SECTIONS = ("posts", "lexicon", "tags")

_NOINDEX_RE = re.compile(r'<meta\s+name="robots"\s+content="[^"]*noindex', re.I)
_CANONICAL_RE = re.compile(r'<link\s+rel="canonical"', re.I)
_LDJSON_RE = re.compile(r'application/ld\+json', re.I)


# ── URLs ────────────────────────────────────────────────────────────────────

def url_path(rel: Path) -> str:
    """docs-relative path -> the site path that actually serves 200.

    index.html collapses to its directory; everything else drops .html. This is
    the single source of truth for both canonicals and the sitemap, so the two
    can never disagree.
    """
    parts = list(rel.parts)
    if parts[-1] == "index.html":
        parts = parts[:-1]
        return "/" + ("/".join(parts) + "/" if parts else "")
    parts[-1] = parts[-1].removesuffix(".html")
    return "/" + "/".join(parts)


def canonical(rel: Path) -> str:
    return SITE_URL + url_path(rel)


# ── Structured data ─────────────────────────────────────────────────────────

def _publisher() -> dict:
    return {
        "@type": "Organization",
        "name": SITE_NAME,
        "url": SITE_URL,
        "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/assets/icon-512.png"},
    }


def _website_ld() -> dict:
    """Homepage only, per Google's guidance. The SearchAction is what wires our
    own /search into a sitelinks search box — it only became truthful once the
    search page existed."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "alternateName": SITE_TAGLINE,
        "url": SITE_URL + "/",
        "description": SITE_DESC,
        "publisher": _publisher(),
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{SITE_URL}/search?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def _post_ld(post: dict, url: str, image: str) -> dict:
    authors = [a.get("name") for a in (post.get("authors") or []) if a.get("name")]
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": (post.get("title") or "")[:110],  # schema.org caps headline
        "url": url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "description": _clean(post.get("excerpt") or "", 300),
        "datePublished": post.get("published_at") or "",
        "dateModified": post.get("updated_at") or post.get("published_at") or "",
        "publisher": _publisher(),
        "image": image,
        "isAccessibleForFree": True,
    }
    ld["author"] = ([{"@type": "Person", "name": n} for n in authors]
                    if authors else _publisher())
    kw = [t.get("name") for t in (post.get("tags") or [])
          if t.get("name") and not t["name"].startswith("#")]
    if kw:
        ld["keywords"] = ", ".join(kw)
    if post.get("reading_time"):
        ld["timeRequired"] = f"PT{post['reading_time']}M"
    return ld


def _term_ld(term: dict, url: str) -> dict:
    """DefinedTerm is the correct type for a glossary entry and is exactly what
    the Lexicon is — 2,058 hand-written definitions, which is the most
    structurally distinctive thing on this site."""
    ld = {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "name": term.get("name") or "",
        "description": _clean(term.get("definition") or "", 500),
        "url": url,
        "inDefinedTermSet": {
            "@type": "DefinedTermSet",
            "name": "The Token Wisdom Lexicon",
            "url": f"{SITE_URL}/lexicon/",
        },
    }
    if term.get("category"):
        ld["termCode"] = term["category"]
    return ld


def _clean(text: str, limit: int) -> str:
    s = re.sub(r"\s+", " ", html.unescape(str(text or ""))).strip()
    return s[:limit].rsplit(" ", 1)[0] if len(s) > limit else s


# ── Injection ───────────────────────────────────────────────────────────────

def _inject(html_text: str, tags: str) -> str:
    """Insert before </head>. Idempotent at the call sites below, which skip
    files that already carry what we're about to add."""
    idx = html_text.lower().find("</head>")
    if idx == -1:
        return html_text
    return html_text[:idx] + tags + html_text[idx:]


def _ld_script(obj: dict) -> str:
    # </script> inside JSON would close the tag early; escape defensively.
    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>\n'


# ── Feed ────────────────────────────────────────────────────────────────────

def _rfc822(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _write_feed(posts: list, out: Path) -> int:
    items = ""
    for p in posts[:FEED_ITEMS]:
        url = f"{SITE_URL}/posts/{p.get('slug', '')}"
        cats = "".join(
            f"<category>{html.escape(t['name'])}</category>"
            for t in (p.get("tags") or [])
            if t.get("name") and not t["name"].startswith("#"))
        items += f"""
  <item>
    <title>{html.escape(p.get('title') or '')}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{_rfc822(p.get('published_at') or '')}</pubDate>
    <description>{html.escape(_clean(p.get('excerpt') or '', 500))}</description>{cats}
  </item>"""

    out.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{html.escape(SITE_NAME)}</title>
  <link>{SITE_URL}/</link>
  <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>{html.escape(SITE_DESC)}</description>
  <language>en</language>
  <lastBuildDate>{_rfc822(datetime.now(timezone.utc).isoformat())}</lastBuildDate>{items}
</channel>
</rss>
""")
    return min(len(posts), FEED_ITEMS)


# ── llms.txt ────────────────────────────────────────────────────────────────

def _write_llms(out: Path, n_posts: int, n_terms: int, recent: list) -> None:
    """llmstxt.org convention. Worth being explicit about the content policy
    here: the site allows search and reference use but refuses training, which
    is what robots.txt already says in machine terms."""
    lines = [
        f"# {SITE_NAME}",
        "",
        f"> {SITE_TAGLINE}. {n_posts:,} published editions and essays since 2013, "
        f"plus a {n_terms:,}-term Lexicon of the working vocabulary of the field — "
        "every definition written by a human, not generated.",
        "",
        "Content policy: reference and search use are welcome; training is not. "
        "Cite as Token Wisdom and link the canonical URL. See /robots.txt.",
        "",
        "## Start here",
        "",
        f"- [Search]({SITE_URL}/search): full-text across every edition and the whole Lexicon.",
        f"- [The Lexicon]({SITE_URL}/lexicon/): {n_terms:,} defined terms, each with its citation history.",
        f"- [Archive]({SITE_URL}/archive): every edition, dated.",
        f"- [Topics]({SITE_URL}/tags/): the corpus grouped by idea.",
        f"- [Feed]({SITE_URL}/feed.xml): RSS.",
        "",
        "## Recent writing",
        "",
    ]
    for p in recent[:15]:
        title = _clean(p.get("title") or "", 120)
        excerpt = _clean(p.get("excerpt") or "", 160)
        lines.append(f"- [{title}]({SITE_URL}/posts/{p.get('slug','')}): {excerpt}")
    lines.append("")
    out.write_text("\n".join(lines))


def _write_robots(out: Path) -> None:
    """Exists mainly to carry the Sitemap directive — without it a sitemap is
    only discoverable by manual submission.

    Cloudflare's AI Crawl Control currently synthesises this file (it prepends
    Content-Signal declarations and the AI-crawler blocklist) because docs/ had
    no robots.txt to attach them to. Cloudflare merges with an origin file when
    one exists, so the AI policy is deliberately NOT duplicated here — it stays
    configured in one place. Verify what is actually served after deploying; if
    Cloudflare replaces this outright, the Sitemap line has to move into the
    dashboard instead.
    """
    # No User-agent group here on purpose. Sitemap is a group-independent
    # directive, and Cloudflare prepends its own "User-agent: *" record —
    # adding a second one just produces a duplicate group for the same agent.
    out.write_text(f"""# {SITE_NAME} — {SITE_TAGLINE}
# Crawl policy (Content-Signal + AI-crawler blocks) is managed at the edge by
# Cloudflare AI Crawl Control and prepended above this file's contents:
# search and reference use are permitted, training is not.

Sitemap: {SITE_URL}/sitemap.xml

# Plain-text site map for models reading this as reference (llmstxt.org)
# {SITE_URL}/llms.txt
""")


# ── Sitemaps ────────────────────────────────────────────────────────────────

def _sitemap(urls: list, out: Path) -> int:
    body = "".join(
        f"\n  <url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>"
        for u, m in urls)
    out.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'{body}\n</urlset>\n')
    return len(urls)


def build(posts=None, terms=None, docs_dir: Path = DOCS, quiet: bool = False) -> dict:
    if posts is None:
        posts = json.loads((ROOT / "data" / "all_posts.json").read_text())
    if terms is None:
        terms = json.loads((ROOT / "data" / "lexicon.json").read_text())["terms"]

    posts_by_slug = {p.get("slug"): p for p in posts}
    terms_by_slug = {t.get("slug"): t for t in terms}
    today = date.today().isoformat()

    buckets: dict[str, list] = {s: [] for s in SECTIONS}
    buckets["pages"] = []
    noindex_slugs: set[str] = set()
    n_canon = n_ld = n_noindex = 0

    for f in sorted(docs_dir.rglob("*.html")):
        rel = f.relative_to(docs_dir)
        text = f.read_text(errors="ignore")
        add = ""

        if not _CANONICAL_RE.search(text):
            add += f'<link rel="canonical" href="{canonical(rel)}">\n'
            n_canon += 1

        # Structured data, chosen by what the page actually is.
        if not _LDJSON_RE.search(text):
            ld = None
            if rel.as_posix() == "index.html":
                ld = _website_ld()
            elif rel.parts[0] == "posts" and len(rel.parts) == 2:
                p = posts_by_slug.get(rel.stem)
                if p:
                    img = _social_card(rel.stem, docs_dir) or DEFAULT_IMAGE
                    ld = _post_ld(p, canonical(rel), img)
            elif rel.parts[0] == "lexicon" and len(rel.parts) == 2:
                t = terms_by_slug.get(rel.stem)
                if t:
                    ld = _term_ld(t, canonical(rel))
            if ld:
                add += _ld_script(ld)
                n_ld += 1

        if add:
            f.write_text(_inject(text, add))

        # Sitemap membership. noindex pages are canonicalised but never listed:
        # asking a crawler to fetch a page we've told it not to index is noise.
        if _NOINDEX_RE.search(text):
            n_noindex += 1
            if rel.parts[0] == "posts":
                noindex_slugs.add(rel.stem)
            continue

        section = rel.parts[0] if rel.parts[0] in SECTIONS and len(rel.parts) > 1 else "pages"
        lastmod = today
        if section == "posts":
            p = posts_by_slug.get(rel.stem) or {}
            lastmod = (p.get("updated_at") or p.get("published_at") or today)[:10]
        buckets[section].append((canonical(rel), lastmod))

    # Child sitemaps + the index over them.
    sm_dir = docs_dir
    written = {}
    for name, urls in buckets.items():
        if not urls:
            continue
        written[name] = _sitemap(sorted(urls), sm_dir / f"sitemap-{name}.xml")

    index_body = "".join(
        f"\n  <sitemap><loc>{SITE_URL}/sitemap-{n}.xml</loc>"
        f"<lastmod>{today}</lastmod></sitemap>" for n in sorted(written))
    (sm_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'{index_body}\n</sitemapindex>\n')

    # Feed + llms.txt, both from public, listable posts newest-first. Reuses the
    # noindex slugs gathered during the walk rather than re-reading 285 files.
    public = [p for p in posts
              if (p.get("visibility") or "public") == "public"
              and p.get("published_at")
              and p.get("slug") not in noindex_slugs]
    public.sort(key=lambda p: p["published_at"], reverse=True)

    n_feed = _write_feed(public, docs_dir / "feed.xml")
    _write_llms(docs_dir / "llms.txt", len(public), len(terms), public)
    _write_robots(docs_dir / "robots.txt")

    stats = {
        "canonicals": n_canon, "jsonld": n_ld, "noindex_skipped": n_noindex,
        "sitemaps": written, "urls": sum(written.values()), "feed": n_feed,
    }
    if not quiet:
        secs = "  ".join(f"{k} {v}" for k, v in sorted(written.items()))
        print(f"  {n_canon} canonicals, {n_ld} JSON-LD blocks "
              f"({n_noindex} noindex pages skipped)")
        print(f"  sitemap: {stats['urls']} URLs — {secs}")
        print(f"  feed.xml ({n_feed} items) + llms.txt")
    return stats


_MANIFEST = None


def _social_card(slug: str, docs_dir: Path) -> str | None:
    """Card URL from data/social_cards.json, or None.

    Same rule as post_social_card_url() in generate_site.py and for the same
    reason: resolving this from disk advertised images that were never deployed.
    Structured data pointing at a 404 is worse than omitting the field, since
    consumers treat a declared image as a promise.
    """
    global _MANIFEST
    if _MANIFEST is None:
        try:
            _MANIFEST = json.loads((ROOT / "data" / "social_cards.json").read_text())
        except (OSError, ValueError):
            _MANIFEST = {"cards": {}}
    if f"{slug}.png" not in _MANIFEST.get("cards", {}):
        return None
    base = (_MANIFEST.get("base") or "").rstrip("/")
    prefix = (_MANIFEST.get("prefix") or "posts").strip("/")
    return f"{base}/{prefix}/{slug}.png" if base else None


if __name__ == "__main__":
    print("Building discoverability layer…")
    build()

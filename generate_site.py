#!/usr/bin/env python3
"""
Static Site Generator for Token Wisdom Ghost Backup
Generates a New Yorker-style GitHub Pages site from backup data.
"""

import json
import html
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BACKUP_DIR = Path(__file__).parent
DATA_DIR = BACKUP_DIR / "data"
DOCS_DIR = BACKUP_DIR / "docs"

SITE_NAME = "Token Wisdom"
SITE_SUBTITLE = "Ideas & Insight"
SITE_URL = "https://iamkhayyam.github.io/tokenwisdom"


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


def fmt_date(iso_str, fmt="%B %d, %Y"):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except:
        return iso_str[:10]


def fmt_date_short(iso_str):
    return fmt_date(iso_str, "%b %d, %Y")


def reading_time(post):
    rt = post.get("reading_time")
    if rt:
        return f"{rt} min read"
    text = post.get("plaintext") or post.get("html") or ""
    words = len(text.split())
    mins = max(1, words // 250)
    return f"{mins} min read"


def excerpt(post, max_len=200):
    ex = post.get("custom_excerpt") or post.get("excerpt") or ""
    if not ex and post.get("plaintext"):
        ex = post["plaintext"][:max_len]
    ex = html.escape(ex.strip())
    if len(ex) > max_len:
        ex = ex[:max_len].rsplit(" ", 1)[0] + "..."
    return ex


def primary_tag(post):
    tags = post.get("tags", [])
    for t in tags:
        if t.get("visibility") == "public" and not t.get("name", "").startswith("#"):
            return t
    return tags[0] if tags else None


def esc(text):
    return html.escape(str(text or ""))


def feature_image_path(post):
    """Get the local path for a post's feature image."""
    fi = post.get("feature_image")
    if not fi:
        return None
    slug = post.get("slug", "")
    # Check if we have a local copy
    img_dir = BACKUP_DIR / "images" / "posts"
    for f in img_dir.iterdir():
        if f.name.startswith(slug + "_feature"):
            return f"../images/posts/{f.name}"
    return fi  # fallback to remote URL


# ============================================================
# HTML TEMPLATES
# ============================================================

def css():
    return """
:root {
    --cream: #F8F6F1;
    --ink: #1A1A1A;
    --red: #D32F2F;
    --gray: #6B6B6B;
    --light-gray: #E8E6E1;
    --border: #D4D2CC;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Crimson Text', Georgia, serif;
    background: var(--cream);
    color: var(--ink);
    font-size: 20px;
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
}
a { color: var(--ink); text-decoration: none; }

/* Masthead */
.masthead {
    border-bottom: 3px solid var(--ink);
    background: white;
    position: sticky; top: 0; z-index: 100;
}
.masthead-top {
    border-bottom: 1px solid var(--border);
    padding: 0.75rem 2rem;
    display: flex; justify-content: space-between; align-items: center;
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;
}
.masthead-date { color: var(--gray); }
.masthead-links { display: flex; gap: 2rem; }
.masthead-links a { font-weight: 600; }
.masthead-links a:hover { color: var(--red); }
.masthead-main { padding: 2rem; text-align: center; }
.logo {
    font-family: 'Libre Baskerville', serif;
    font-size: 3rem; font-weight: 700;
    letter-spacing: -0.02em; margin-bottom: 0.5rem;
}
.logo a { color: var(--ink); }
.logo a:hover { color: var(--red); }
.logo-subtitle {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; letter-spacing: 0.15em;
    text-transform: uppercase; color: var(--gray);
}
.nav {
    border-top: 1px solid var(--border);
    padding: 1rem 0;
    display: flex; justify-content: center; gap: 3rem; flex-wrap: wrap;
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.08em;
}
.nav a {
    font-weight: 600; position: relative;
}
.nav a::after {
    content: ''; position: absolute; bottom: -4px; left: 0;
    width: 0; height: 2px; background: var(--red);
    transition: width 0.3s ease;
}
.nav a:hover::after { width: 100%; }
.nav a.active { color: var(--red); }
.nav a.active::after { width: 100%; }

/* Hero */
.hero {
    max-width: 1200px; margin: 0 auto;
    padding: 4rem 2rem;
    border-bottom: 1px solid var(--border);
}
.hero-label {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; text-transform: uppercase;
    letter-spacing: 0.12em; color: var(--red);
    font-weight: 700; margin-bottom: 1.5rem;
}
.hero-label a { color: var(--red); }
.hero-title {
    font-family: 'Libre Baskerville', serif;
    font-size: clamp(2.5rem, 5vw, 4rem);
    line-height: 1.15; font-weight: 700;
    margin-bottom: 1.5rem; letter-spacing: -0.02em;
}
.hero-title a { color: var(--ink); }
.hero-title a:hover { color: var(--red); }
.hero-deck {
    font-size: 1.5rem; line-height: 1.5;
    color: var(--gray); margin-bottom: 2rem;
    max-width: 900px;
}
.hero-byline {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.875rem; color: var(--gray); margin-bottom: 0.25rem;
}
.hero-author { color: var(--ink); font-weight: 600; }
.hero-image {
    width: 100%; max-height: 500px; object-fit: cover;
    margin-bottom: 2rem; border-bottom: 1px solid var(--border);
}

/* Three Column */
.main-content {
    max-width: 1400px; margin: 0 auto; padding: 3rem 2rem;
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3rem;
}
.column {
    border-right: 1px solid var(--border); padding-right: 3rem;
}
.column:last-child { border-right: none; padding-right: 0; }

/* Article Cards */
.article {
    margin-bottom: 3rem; padding-bottom: 3rem;
    border-bottom: 1px solid var(--light-gray);
}
.article:last-child { border-bottom: none; }
.article-category {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.7rem; text-transform: uppercase;
    letter-spacing: 0.12em; color: var(--red);
    font-weight: 700; margin-bottom: 0.75rem;
}
.article-category a { color: var(--red); }
.article-title {
    font-family: 'Libre Baskerville', serif;
    font-size: 1.5rem; line-height: 1.3;
    font-weight: 700; margin-bottom: 0.75rem;
    letter-spacing: -0.01em;
}
.article-title a { transition: color 0.3s ease; }
.article-title a:hover { color: var(--red); }
.article-excerpt {
    font-size: 1rem; line-height: 1.6;
    color: var(--gray); margin-bottom: 0.75rem;
}
.article-meta {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; color: var(--gray);
}
.article-author { font-weight: 600; color: var(--ink); }
.article-thumb {
    width: 100%; height: 200px; object-fit: cover;
    margin-bottom: 1rem;
}

/* Post Page */
.post-page {
    max-width: 800px; margin: 0 auto; padding: 3rem 2rem;
}
.post-header { margin-bottom: 3rem; border-bottom: 1px solid var(--border); padding-bottom: 2rem; }
.post-tags { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1rem; }
.post-tag {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.65rem; text-transform: uppercase;
    letter-spacing: 0.1em; color: var(--red);
    border: 1px solid var(--red); padding: 0.25rem 0.75rem;
    font-weight: 600;
}
.post-tag:hover { background: var(--red); color: white; }
.post-body {
    font-size: 1.15rem; line-height: 1.8;
}
.post-body p { margin-bottom: 1.5rem; }
.post-body h2, .post-body h3 {
    font-family: 'Libre Baskerville', serif;
    margin: 2.5rem 0 1rem; font-weight: 700;
}
.post-body h2 { font-size: 1.75rem; }
.post-body h3 { font-size: 1.35rem; }
.post-body img {
    max-width: 100%; height: auto;
    margin: 2rem 0; display: block;
}
.post-body blockquote {
    border-left: 3px solid var(--red);
    padding-left: 1.5rem; margin: 2rem 0;
    font-style: italic; color: var(--gray);
}
.post-body pre, .post-body code {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 0.85em; background: white;
    border: 1px solid var(--border);
}
.post-body pre { padding: 1.5rem; overflow-x: auto; margin: 1.5rem 0; }
.post-body code { padding: 0.15em 0.4em; }
.post-body pre code { padding: 0; border: none; background: none; }
.post-body a { color: var(--red); text-decoration: underline; }
.post-body ul, .post-body ol { margin: 1.5rem 0; padding-left: 2rem; }
.post-body li { margin-bottom: 0.5rem; }
.post-body figure { margin: 2rem 0; }
.post-body figcaption {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.8rem; color: var(--gray);
    margin-top: 0.5rem; text-align: center;
}
.post-body .kg-card { margin: 2rem 0; }
.post-body .kg-image-card img { margin: 0 auto; }
.post-body .kg-bookmark-card {
    border: 1px solid var(--border); padding: 1rem;
    background: white; margin: 1.5rem 0;
}
.post-feature-img {
    width: 100%; max-height: 500px; object-fit: cover;
    margin-bottom: 2rem;
}
.drop-cap::first-letter {
    font-size: 4rem; line-height: 1;
    float: left; margin: 0.1em 0.1em 0 0;
    font-weight: 700;
}

/* Tag Page */
.tag-header {
    max-width: 1200px; margin: 0 auto;
    padding: 3rem 2rem;
    border-bottom: 1px solid var(--border);
    text-align: center;
}
.tag-name {
    font-family: 'Libre Baskerville', serif;
    font-size: 2.5rem; font-weight: 700;
}
.tag-description {
    font-size: 1.125rem; color: var(--gray);
    max-width: 700px; margin: 1rem auto 0; line-height: 1.6;
}
.tag-count {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.8rem; color: var(--gray);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-top: 0.5rem;
}
.post-list {
    max-width: 900px; margin: 0 auto; padding: 2rem;
}
.post-list-item {
    padding: 2rem 0;
    border-bottom: 1px solid var(--light-gray);
}
.post-list-item:last-child { border-bottom: none; }

/* Tags Index */
.tags-grid {
    max-width: 1200px; margin: 0 auto; padding: 2rem;
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.5rem;
}
.tag-card {
    background: white; border: 1px solid var(--border);
    padding: 1.5rem; transition: border-color 0.3s;
}
.tag-card:hover { border-color: var(--red); }
.tag-card-name {
    font-family: 'Libre Baskerville', serif;
    font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem;
}
.tag-card-count {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; color: var(--gray);
    text-transform: uppercase; letter-spacing: 0.08em;
}
.tag-card-desc {
    font-size: 0.9rem; color: var(--gray);
    margin-top: 0.5rem; line-height: 1.5;
}

/* Pagination */
.pagination {
    max-width: 1200px; margin: 2rem auto;
    padding: 2rem; text-align: center;
    font-family: 'Libre Franklin', sans-serif;
}
.pagination a, .pagination span {
    display: inline-block; padding: 0.5rem 1rem;
    margin: 0 0.25rem; font-size: 0.85rem;
    border: 1px solid var(--border);
}
.pagination a:hover { border-color: var(--red); color: var(--red); }
.pagination .current {
    background: var(--ink); color: white;
    border-color: var(--ink);
}

/* Newsletter */
.newsletter {
    max-width: 800px; margin: 4rem auto;
    padding: 3rem; background: white;
    border: 2px solid var(--ink); text-align: center;
}
.newsletter-title {
    font-family: 'Libre Baskerville', serif;
    font-size: 2rem; font-weight: 700; margin-bottom: 1rem;
}
.newsletter-description {
    font-size: 1.125rem; color: var(--gray);
    margin-bottom: 2rem; line-height: 1.6;
}

/* Footer */
footer {
    border-top: 3px solid var(--ink);
    background: white; padding: 3rem 2rem;
}
.footer-content {
    max-width: 1400px; margin: 0 auto;
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 3rem;
}
.footer-section h3 {
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; text-transform: uppercase;
    letter-spacing: 0.12em; font-weight: 700;
    margin-bottom: 1.5rem;
}
.footer-section ul { list-style: none; }
.footer-section li { margin-bottom: 0.75rem; }
.footer-section a {
    color: var(--gray); font-size: 0.875rem;
    transition: color 0.3s ease;
}
.footer-section a:hover { color: var(--ink); }
.footer-bottom {
    max-width: 1400px; margin: 3rem auto 0;
    padding-top: 2rem; border-top: 1px solid var(--border);
    font-family: 'Libre Franklin', sans-serif;
    font-size: 0.75rem; color: var(--gray); text-align: center;
}

/* Responsive */
@media (max-width: 1024px) {
    .main-content { grid-template-columns: 1fr 1fr; }
    .column:nth-child(3) {
        grid-column: 1 / -1; border-right: none;
        border-top: 1px solid var(--border); padding-top: 3rem;
    }
    .footer-content { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
    .masthead-top { flex-direction: column; gap: 1rem; }
    .nav { gap: 1.5rem; }
    .main-content { grid-template-columns: 1fr; }
    .column { border-right: none; padding-right: 0; border-bottom: 1px solid var(--border); padding-bottom: 3rem; }
    .column:last-child { border-bottom: none; }
    .footer-content { grid-template-columns: 1fr; }
    .hero-title { font-size: 2rem; }
    .post-body { font-size: 1.05rem; }
}
"""


def head(title, extra_path=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)} — {SITE_NAME}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Crimson+Text:ital,wght@0,400;0,600;1,400&family=Libre+Franklin:wght@300;400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{extra_path}style.css">
</head>
<body>"""


def masthead(nav_tags, active_tag=None, extra_path=""):
    today = datetime.now().strftime("%A, %B %d, %Y")
    nav_links = f'<a href="{extra_path}index.html">Home</a>'
    for t in nav_tags[:8]:
        active = ' class="active"' if active_tag == t["slug"] else ""
        nav_links += f'<a href="{extra_path}tags/{t["slug"]}.html"{active}>{esc(t["name"])}</a>'
    nav_links += f'<a href="{extra_path}tags/index.html">All Tags</a>'

    return f"""
<header class="masthead">
    <div class="masthead-top">
        <div class="masthead-date">{today}</div>
        <div class="masthead-links">
            <a href="https://tokenwisdom.ghost.io" target="_blank">Ghost</a>
            <a href="https://github.com/iamkhayyam/tokenwisdom" target="_blank">GitHub</a>
        </div>
    </div>
    <div class="masthead-main">
        <h1 class="logo"><a href="{extra_path}index.html">{SITE_NAME}</a></h1>
        <p class="logo-subtitle">{SITE_SUBTITLE}</p>
    </div>
    <nav class="nav">{nav_links}</nav>
</header>"""


def footer_html():
    return f"""
<footer>
    <div class="footer-content">
        <div class="footer-section">
            <h3>About</h3>
            <ul>
                <li><a href="https://tokenwisdom.ghost.io">Token Wisdom</a></li>
                <li><a href="https://github.com/iamkhayyam">GitHub</a></li>
            </ul>
        </div>
        <div class="footer-section">
            <h3>Archive</h3>
            <ul>
                <li><a href="tags/index.html">All Tags</a></li>
                <li><a href="archive.html">All Posts</a></li>
            </ul>
        </div>
        <div class="footer-section">
            <h3>Info</h3>
            <ul>
                <li>267 Posts</li>
                <li>85 Tags</li>
                <li>Since 2013</li>
            </ul>
        </div>
        <div class="footer-section">
            <h3>Source</h3>
            <ul>
                <li><a href="https://tokenwisdom.ghost.io" target="_blank">Ghost Blog</a></li>
                <li><a href="https://github.com/iamkhayyam/tokenwisdom" target="_blank">Backup Repo</a></li>
            </ul>
        </div>
    </div>
    <div class="footer-bottom">
        &copy; {datetime.now().year} {SITE_NAME}. Backed up with care.
    </div>
</footer>
</body>
</html>"""


# ============================================================
# PAGE GENERATORS
# ============================================================

def generate_index(posts, nav_tags):
    """Generate the homepage with hero + three columns."""
    sorted_posts = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"],
        reverse=True,
    )

    if not sorted_posts:
        return ""

    hero = sorted_posts[0]
    rest = sorted_posts[1:28]  # 9 per column x 3

    # Hero section
    tag = primary_tag(hero)
    tag_html = ""
    if tag:
        tag_html = f'<div class="hero-label"><a href="tags/{tag["slug"]}.html">{esc(tag["name"])}</a></div>'

    authors = hero.get("authors", [])
    author_name = authors[0]["name"] if authors else ""

    hero_html = f"""
    <article class="hero">
        {tag_html}
        <h1 class="hero-title"><a href="posts/{hero['slug']}.html">{esc(hero.get('title', ''))}</a></h1>
        <p class="hero-deck">{excerpt(hero, 300)}</p>
        <div class="hero-byline">By <span class="hero-author">{esc(author_name)}</span></div>
        <div class="hero-byline">{fmt_date(hero.get('published_at'))}</div>
    </article>"""

    # Three columns
    cols = [[], [], []]
    for i, post in enumerate(rest):
        cols[i % 3].append(post)

    columns_html = ""
    for col_posts in cols:
        articles = ""
        for p in col_posts:
            t = primary_tag(p)
            cat = f'<div class="article-category"><a href="tags/{t["slug"]}.html">{esc(t["name"])}</a></div>' if t else ""
            a = p.get("authors", [])
            author = a[0]["name"] if a else ""
            articles += f"""
            <article class="article">
                {cat}
                <h2 class="article-title"><a href="posts/{p['slug']}.html">{esc(p.get('title', ''))}</a></h2>
                <p class="article-excerpt">{excerpt(p, 160)}</p>
                <div class="article-meta">
                    By <span class="article-author">{esc(author)}</span> &middot; {fmt_date_short(p.get('published_at'))}
                </div>
            </article>"""
        columns_html += f'<div class="column">{articles}</div>'

    page = head(SITE_NAME)
    page += masthead(nav_tags)
    page += hero_html
    page += f'<section class="main-content">{columns_html}</section>'
    page += f"""
    <div class="pagination">
        <a href="archive.html">View All Posts &rarr;</a>
    </div>"""
    page += footer_html()
    return page


def generate_post_page(post, nav_tags):
    """Generate an individual post page."""
    tag = primary_tag(post)
    tags = post.get("tags", [])
    authors = post.get("authors", [])
    author_name = authors[0]["name"] if authors else ""

    tag_label = ""
    if tag:
        tag_label = f'<div class="hero-label"><a href="../tags/{tag["slug"]}.html">{esc(tag["name"])}</a></div>'

    tags_html = ""
    if tags:
        tags_html = '<div class="post-tags">'
        for t in tags:
            if not t.get("name", "").startswith("#"):
                tags_html += f'<a class="post-tag" href="../tags/{t["slug"]}.html">{esc(t["name"])}</a>'
        tags_html += '</div>'

    content = post.get("html") or post.get("plaintext") or ""

    page = head(post.get("title", ""), "../")
    page += masthead(nav_tags, tag["slug"] if tag else None, "../")
    page += f"""
    <article class="post-page">
        <div class="post-header">
            {tag_label}
            <h1 class="hero-title">{esc(post.get('title', ''))}</h1>
            <div class="hero-byline">By <span class="hero-author">{esc(author_name)}</span></div>
            <div class="hero-byline">{fmt_date(post.get('published_at'))} &middot; {reading_time(post)}</div>
            {tags_html}
        </div>
        <div class="post-body">
            {content}
        </div>
    </article>"""
    page += footer_html().replace('href="tags/', 'href="../tags/').replace('href="archive.html"', 'href="../archive.html"')
    return page


def generate_tag_page(tag, posts_for_tag, nav_tags):
    """Generate a tag listing page."""
    sorted_posts = sorted(
        posts_for_tag,
        key=lambda p: p.get("published_at", ""),
        reverse=True,
    )

    posts_html = ""
    for p in sorted_posts:
        authors = p.get("authors", [])
        author_name = authors[0]["name"] if authors else ""
        posts_html += f"""
        <div class="post-list-item">
            <div class="article-category">{fmt_date_short(p.get('published_at'))}</div>
            <h2 class="article-title"><a href="../posts/{p['slug']}.html">{esc(p.get('title', ''))}</a></h2>
            <p class="article-excerpt">{excerpt(p, 200)}</p>
            <div class="article-meta">
                By <span class="article-author">{esc(author_name)}</span> &middot; {reading_time(p)}
            </div>
        </div>"""

    desc = tag.get("description") or ""
    desc_html = f'<p class="tag-description">{esc(desc)}</p>' if desc else ""

    page = head(tag.get("name", ""), "../")
    page += masthead(nav_tags, tag["slug"], "../")
    page += f"""
    <div class="tag-header">
        <h1 class="tag-name">{esc(tag.get('name', ''))}</h1>
        {desc_html}
        <div class="tag-count">{len(sorted_posts)} article{'s' if len(sorted_posts) != 1 else ''}</div>
    </div>
    <div class="post-list">{posts_html}</div>"""
    page += footer_html().replace('href="tags/', 'href="../tags/').replace('href="archive.html"', 'href="../archive.html"')
    return page


def generate_tags_index(tags, tag_to_posts, nav_tags):
    """Generate the all-tags index page."""
    sorted_tags = sorted(
        [t for t in tags if not t.get("name", "").startswith("#")],
        key=lambda t: len(tag_to_posts.get(t["slug"], [])),
        reverse=True,
    )

    cards = ""
    for t in sorted_tags:
        count = len(tag_to_posts.get(t["slug"], []))
        desc = t.get("description") or ""
        desc_html = f'<div class="tag-card-desc">{esc(desc[:100])}</div>' if desc else ""
        cards += f"""
        <a class="tag-card" href="{t['slug']}.html">
            <div class="tag-card-name">{esc(t['name'])}</div>
            <div class="tag-card-count">{count} article{'s' if count != 1 else ''}</div>
            {desc_html}
        </a>"""

    page = head("All Tags", "../")
    page += masthead(nav_tags, extra_path="../")
    page += f"""
    <div class="tag-header">
        <h1 class="tag-name">All Tags</h1>
        <div class="tag-count">{len(sorted_tags)} tags</div>
    </div>
    <div class="tags-grid">{cards}</div>"""
    page += footer_html().replace('href="tags/', 'href="').replace('href="archive.html"', 'href="../archive.html"')
    return page


def generate_archive(posts, nav_tags):
    """Generate the full archive page."""
    sorted_posts = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"],
        reverse=True,
    )

    # Group by year
    by_year = defaultdict(list)
    for p in sorted_posts:
        year = p["published_at"][:4]
        by_year[year].append(p)

    content = ""
    for year in sorted(by_year.keys(), reverse=True):
        content += f'<h2 style="font-family: Libre Baskerville, serif; font-size: 2rem; margin: 2rem 0 1rem; border-bottom: 2px solid var(--ink); padding-bottom: 0.5rem;">{year}</h2>'
        for p in by_year[year]:
            t = primary_tag(p)
            tag_html = f' <span style="color: var(--red); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; font-family: Libre Franklin, sans-serif;">{esc(t["name"])}</span>' if t else ""
            content += f"""
            <div class="post-list-item">
                <div class="article-category">{fmt_date_short(p.get('published_at'))}{tag_html}</div>
                <h2 class="article-title"><a href="posts/{p['slug']}.html">{esc(p.get('title', ''))}</a></h2>
                <p class="article-excerpt">{excerpt(p, 150)}</p>
            </div>"""

    page = head("Archive")
    page += masthead(nav_tags)
    page += f"""
    <div class="tag-header">
        <h1 class="tag-name">Archive</h1>
        <div class="tag-count">{len(sorted_posts)} posts &middot; {min(by_year.keys())}–{max(by_year.keys())}</div>
    </div>
    <div class="post-list">{content}</div>"""
    page += footer_html()
    return page


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("STATIC SITE GENERATOR — NEW YORKER STYLE")
    print("=" * 60)

    posts, tags, authors, pages = load_data()
    print(f"Loaded: {len(posts)} posts, {len(tags)} tags, {len(authors)} authors, {len(pages)} pages")

    # Build tag -> posts map
    tag_to_posts = defaultdict(list)
    for post in posts:
        for t in post.get("tags", []):
            tag_to_posts[t["slug"]].append(post)

    # Top nav tags (most posts, public, non-internal)
    public_tags = [t for t in tags if not t.get("name", "").startswith("#")]
    nav_tags = sorted(public_tags, key=lambda t: len(tag_to_posts.get(t["slug"], [])), reverse=True)

    # Setup output
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir()
    (DOCS_DIR / "posts").mkdir()
    (DOCS_DIR / "tags").mkdir()

    # Copy images
    print("Copying images...")
    src_images = BACKUP_DIR / "images"
    dst_images = DOCS_DIR / "images"
    if src_images.exists():
        shutil.copytree(src_images, dst_images)
    print(f"  Images copied")

    # Write CSS
    print("Writing CSS...")
    with open(DOCS_DIR / "style.css", "w") as f:
        f.write(css())

    # Generate homepage
    print("Generating homepage...")
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(generate_index(posts, nav_tags))

    # Generate archive
    print("Generating archive...")
    with open(DOCS_DIR / "archive.html", "w") as f:
        f.write(generate_archive(posts, nav_tags))

    # Generate post pages
    print(f"Generating {len(posts)} post pages...")
    for i, post in enumerate(posts):
        slug = post.get("slug", "unknown")
        with open(DOCS_DIR / "posts" / f"{slug}.html", "w") as f:
            f.write(generate_post_page(post, nav_tags))
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(posts)}")
    print(f"  {len(posts)} post pages generated")

    # Generate tag pages
    print(f"Generating {len(public_tags)} tag pages...")
    tag_by_slug = {t["slug"]: t for t in tags}
    for t in public_tags:
        tp = tag_to_posts.get(t["slug"], [])
        with open(DOCS_DIR / "tags" / f"{t['slug']}.html", "w") as f:
            f.write(generate_tag_page(t, tp, nav_tags))

    # Tags index
    with open(DOCS_DIR / "tags" / "index.html", "w") as f:
        f.write(generate_tags_index(tags, tag_to_posts, nav_tags))
    print(f"  {len(public_tags)} tag pages + index generated")

    # CNAME / nojekyll
    with open(DOCS_DIR / ".nojekyll", "w") as f:
        f.write("")

    # Count output
    html_count = len(list(DOCS_DIR.glob("**/*.html")))
    print(f"\n{'=' * 60}")
    print(f"SITE GENERATED!")
    print(f"  HTML pages: {html_count}")
    print(f"  Output: {DOCS_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

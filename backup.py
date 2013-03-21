#!/usr/bin/env python3
"""
Comprehensive Ghost Blog Backup Script
Backs up ALL posts, tags, authors, images, and relationships.
"""

import json
import os
import re
import sys
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Configuration
GHOST_URL = "https://tokenwisdom.ghost.io"
API_KEY = "4694c7c6437b467d3382d6ef6a"
API_BASE = f"{GHOST_URL}/ghost/api/content"
BACKUP_DIR = Path(__file__).parent

# Directory structure
POSTS_DIR = BACKUP_DIR / "posts"
TAGS_DIR = BACKUP_DIR / "tags"
AUTHORS_DIR = BACKUP_DIR / "authors"
IMAGES_DIR = BACKUP_DIR / "images"
POST_IMAGES_DIR = IMAGES_DIR / "posts"
TAG_IMAGES_DIR = IMAGES_DIR / "tags"
AUTHOR_IMAGES_DIR = IMAGES_DIR / "authors"
RELATIONSHIPS_DIR = BACKUP_DIR / "relationships"
DATA_DIR = BACKUP_DIR / "data"


def setup_dirs():
    """Create all backup directories."""
    for d in [POSTS_DIR, TAGS_DIR, AUTHORS_DIR, POST_IMAGES_DIR,
              TAG_IMAGES_DIR, AUTHOR_IMAGES_DIR, RELATIONSHIPS_DIR, DATA_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    print("[OK] Directory structure created")


def api_get(endpoint, params=None):
    """Make a GET request to the Ghost Content API."""
    if params is None:
        params = {}
    params["key"] = API_KEY
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE}/{endpoint}/?{query}"

    req = urllib.request.Request(url)
    req.add_header("Accept-Version", "v5.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] API {endpoint}: HTTP {e.code}")
        body = e.read().decode() if e.fp else ""
        print(f"  Response: {body[:200]}")
        return None
    except Exception as e:
        print(f"  [ERROR] API {endpoint}: {e}")
        return None


def fetch_all_paginated(endpoint, resource_key, params=None):
    """Fetch all pages of a paginated Ghost API endpoint."""
    if params is None:
        params = {}
    all_items = []
    page = 1

    while True:
        params["page"] = str(page)
        params["limit"] = "100"
        data = api_get(endpoint, params)

        if not data or resource_key not in data:
            break

        items = data[resource_key]
        if not items:
            break

        all_items.extend(items)
        meta = data.get("meta", {}).get("pagination", {})
        total_pages = meta.get("pages", 1)

        print(f"  Page {page}/{total_pages} - got {len(items)} {resource_key}")

        if page >= total_pages:
            break
        page += 1

    return all_items


def download_image(url, dest_dir, prefix=""):
    """Download an image and return the local filename."""
    if not url:
        return None

    try:
        # Parse URL to get filename
        parsed = urllib.parse.urlparse(url)
        original_name = os.path.basename(parsed.path)
        if not original_name or original_name == "/":
            # Generate name from URL hash
            original_name = hashlib.md5(url.encode()).hexdigest()[:12] + ".jpg"

        if prefix:
            local_name = f"{prefix}__{original_name}"
        else:
            local_name = original_name

        # Sanitize filename
        local_name = re.sub(r'[^\w\-.]', '_', local_name)
        dest_path = dest_dir / local_name

        if dest_path.exists():
            return local_name

        req = urllib.request.Request(url)
        req.add_header("User-Agent", "GhostBackup/1.0")

        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())

        return local_name
    except Exception as e:
        print(f"  [WARN] Failed to download {url}: {e}")
        return None


def extract_post_images(html_content):
    """Extract all image URLs from post HTML content."""
    if not html_content:
        return []
    # Match src attributes (not srcset)
    src_pattern = r'(?<!\w)src=["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp|svg|avif))["\']'
    urls = re.findall(src_pattern, html_content, re.IGNORECASE)

    # Match srcset - extract individual URLs from srcset values
    srcset_pattern = r'srcset=["\']([^"\']+)["\']'
    srcset_matches = re.findall(srcset_pattern, html_content, re.IGNORECASE)
    for srcset_val in srcset_matches:
        # srcset format: "url1 600w, url2 1000w, ..."
        for entry in srcset_val.split(","):
            entry = entry.strip()
            parts = entry.split()
            if parts and parts[0].startswith("http"):
                urls.append(parts[0])

    # Also match __GHOST_URL__ patterns
    ghost_pattern = r'__GHOST_URL__(/content/images/[^"\')\s]+)'
    ghost_urls = re.findall(ghost_pattern, html_content)
    urls.extend([f"{GHOST_URL}{path}" for path in ghost_urls])
    # Deduplicate
    return list(dict.fromkeys(urls))


def slugify(text):
    """Create a filesystem-safe slug."""
    if not text:
        return "untitled"
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:80] or "untitled"


def save_json(data, path):
    """Save data as formatted JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def save_markdown(content, path):
    """Save content as markdown."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ============================================================
# MAIN BACKUP LOGIC
# ============================================================

def main():
    print("=" * 60)
    print("GHOST BLOG COMPREHENSIVE BACKUP")
    print(f"Source: {GHOST_URL}")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 60)

    setup_dirs()

    # ----------------------------------------------------------
    # 1. FETCH ALL DATA
    # ----------------------------------------------------------
    print("\n[1/7] Fetching all tags...")
    all_tags = fetch_all_paginated("tags", "tags", {
        "include": "count.posts",
        "fields": "id,name,slug,description,feature_image,visibility,meta_title,meta_description,og_image,og_title,og_description,twitter_image,twitter_title,twitter_description,codeinjection_head,codeinjection_foot,canonical_url,accent_color,url"
    })
    print(f"  Total tags: {len(all_tags)}")

    print("\n[2/7] Fetching all posts...")
    all_posts = fetch_all_paginated("posts", "posts", {
        "include": "tags,authors",
        "formats": "html,plaintext",
        "fields": "id,uuid,title,slug,html,plaintext,feature_image,featured,status,visibility,created_at,updated_at,published_at,custom_excerpt,excerpt,meta_title,meta_description,og_image,og_title,og_description,twitter_image,twitter_title,twitter_description,canonical_url,url,reading_time,comment_id"
    })
    print(f"  Total posts: {len(all_posts)}")

    print("\n[3/7] Fetching all authors...")
    all_authors = fetch_all_paginated("authors", "authors", {
        "include": "count.posts",
        "fields": "id,name,slug,profile_image,cover_image,bio,website,location,facebook,twitter,meta_title,meta_description,url"
    })
    print(f"  Total authors: {len(all_authors)}")

    # Also fetch pages
    print("\n[3.5/7] Fetching all pages...")
    all_pages = fetch_all_paginated("pages", "pages", {
        "include": "tags,authors",
        "formats": "html,plaintext",
        "fields": "id,uuid,title,slug,html,plaintext,feature_image,featured,status,visibility,created_at,updated_at,published_at,custom_excerpt,excerpt,meta_title,meta_description,url"
    })
    print(f"  Total pages: {len(all_pages)}")

    # ----------------------------------------------------------
    # 2. SAVE RAW API DATA
    # ----------------------------------------------------------
    print("\n[4/7] Saving raw API data...")
    save_json(all_tags, DATA_DIR / "all_tags.json")
    save_json(all_posts, DATA_DIR / "all_posts.json")
    save_json(all_authors, DATA_DIR / "all_authors.json")
    save_json(all_pages, DATA_DIR / "all_pages.json")
    print("  Saved raw JSON data")

    # ----------------------------------------------------------
    # 3. BUILD RELATIONSHIP MAPS
    # ----------------------------------------------------------
    print("\n[5/7] Building relationships...")

    # Tag -> Posts mapping
    tag_to_posts = defaultdict(list)
    # Post -> Tags mapping
    post_to_tags = defaultdict(list)
    # Author -> Posts mapping
    author_to_posts = defaultdict(list)
    # Post -> Authors mapping
    post_to_authors = defaultdict(list)

    # Tag lookup by slug and id
    tag_by_id = {t["id"]: t for t in all_tags}
    tag_by_slug = {t["slug"]: t for t in all_tags}
    author_by_id = {a["id"]: a for a in all_authors}
    post_by_id = {}

    for post in all_posts:
        post_by_id[post["id"]] = post
        post_info = {
            "id": post["id"],
            "title": post.get("title", ""),
            "slug": post.get("slug", ""),
            "published_at": post.get("published_at", ""),
            "url": post.get("url", ""),
            "featured": post.get("featured", False),
            "reading_time": post.get("reading_time", 0),
        }

        for tag in post.get("tags", []):
            tag_to_posts[tag["slug"]].append(post_info)
            post_to_tags[post["slug"]].append({
                "id": tag["id"],
                "name": tag.get("name", ""),
                "slug": tag.get("slug", ""),
                "visibility": tag.get("visibility", "public"),
            })

        for author in post.get("authors", []):
            author_to_posts[author["slug"]].append(post_info)
            post_to_authors[post["slug"]].append({
                "id": author["id"],
                "name": author.get("name", ""),
                "slug": author.get("slug", ""),
            })

    print(f"  Tag-to-post relationships: {sum(len(v) for v in tag_to_posts.values())}")
    print(f"  Post-to-tag relationships: {sum(len(v) for v in post_to_tags.values())}")

    # ----------------------------------------------------------
    # 4. DOWNLOAD IMAGES
    # ----------------------------------------------------------
    print("\n[6/7] Downloading images...")

    # Tag feature images
    tag_image_map = {}
    print("  Downloading tag images...")
    for tag in all_tags:
        feature_img = tag.get("feature_image")
        og_img = tag.get("og_image")
        twitter_img = tag.get("twitter_image")

        for img_url, suffix in [(feature_img, "feature"), (og_img, "og"), (twitter_img, "twitter")]:
            if img_url:
                local = download_image(img_url, TAG_IMAGES_DIR, f"{tag['slug']}_{suffix}")
                if local:
                    tag_image_map[img_url] = local

    print(f"    Downloaded {len(tag_image_map)} tag images")

    # Author images
    author_image_map = {}
    print("  Downloading author images...")
    for author in all_authors:
        profile_img = author.get("profile_image")
        cover_img = author.get("cover_image")

        for img_url, suffix in [(profile_img, "profile"), (cover_img, "cover")]:
            if img_url:
                local = download_image(img_url, AUTHOR_IMAGES_DIR, f"{author['slug']}_{suffix}")
                if local:
                    author_image_map[img_url] = local

    print(f"    Downloaded {len(author_image_map)} author images")

    # Post images (feature images + inline images)
    post_image_map = {}
    total_post_images = 0
    print("  Downloading post images...")
    for i, post in enumerate(all_posts):
        slug = post.get("slug", "unknown")

        # Feature image
        feature_img = post.get("feature_image")
        og_img = post.get("og_image")
        twitter_img = post.get("twitter_image")

        for img_url, suffix in [(feature_img, "feature"), (og_img, "og"), (twitter_img, "twitter")]:
            if img_url:
                local = download_image(img_url, POST_IMAGES_DIR, f"{slug}_{suffix}")
                if local:
                    post_image_map[img_url] = local
                    total_post_images += 1

        # Inline images from HTML
        inline_images = extract_post_images(post.get("html", ""))
        for img_url in inline_images:
            if img_url not in post_image_map:
                local = download_image(img_url, POST_IMAGES_DIR, slug)
                if local:
                    post_image_map[img_url] = local
                    total_post_images += 1

        if (i + 1) % 10 == 0:
            print(f"    Processed {i + 1}/{len(all_posts)} posts")

    # Also process pages
    for page in all_pages:
        slug = page.get("slug", "unknown")
        feature_img = page.get("feature_image")
        if feature_img:
            local = download_image(feature_img, POST_IMAGES_DIR, f"page_{slug}_feature")
            if local:
                post_image_map[feature_img] = local
                total_post_images += 1
        inline_images = extract_post_images(page.get("html", ""))
        for img_url in inline_images:
            if img_url not in post_image_map:
                local = download_image(img_url, POST_IMAGES_DIR, f"page_{slug}")
                if local:
                    post_image_map[img_url] = local
                    total_post_images += 1

    print(f"    Total post/page images downloaded: {total_post_images}")

    # Save image maps
    save_json(tag_image_map, DATA_DIR / "tag_image_map.json")
    save_json(author_image_map, DATA_DIR / "author_image_map.json")
    save_json(post_image_map, DATA_DIR / "post_image_map.json")

    # ----------------------------------------------------------
    # 5. SAVE INDIVIDUAL FILES
    # ----------------------------------------------------------
    print("\n[7/7] Saving individual files...")

    # Save each tag
    print("  Saving tags...")
    for tag in all_tags:
        slug = tag["slug"]
        tag_dir = TAGS_DIR / slug
        tag_dir.mkdir(exist_ok=True)

        # Tag JSON with full data
        tag_data = {**tag}
        tag_data["posts"] = tag_to_posts.get(slug, [])
        tag_data["post_count"] = len(tag_data["posts"])
        tag_data["local_feature_image"] = tag_image_map.get(tag.get("feature_image"))
        save_json(tag_data, tag_dir / "tag.json")

        # Tag markdown
        posts_list = tag_to_posts.get(slug, [])
        md = f"# {tag.get('name', slug)}\n\n"
        md += f"**Slug:** `{slug}`\n"
        md += f"**ID:** `{tag['id']}`\n"
        md += f"**Visibility:** {tag.get('visibility', 'public')}\n"
        if tag.get('description'):
            md += f"\n## Description\n\n{tag['description']}\n"
        if tag.get('meta_title'):
            md += f"\n**Meta Title:** {tag['meta_title']}\n"
        if tag.get('meta_description'):
            md += f"**Meta Description:** {tag['meta_description']}\n"
        if tag.get('feature_image'):
            local_img = tag_image_map.get(tag['feature_image'], '')
            md += f"\n**Feature Image:** {tag['feature_image']}\n"
            if local_img:
                md += f"**Local Image:** `images/tags/{local_img}`\n"
        if tag.get('accent_color'):
            md += f"**Accent Color:** {tag['accent_color']}\n"
        if tag.get('canonical_url'):
            md += f"**Canonical URL:** {tag['canonical_url']}\n"

        md += f"\n## Posts ({len(posts_list)})\n\n"
        for p in sorted(posts_list, key=lambda x: x.get("published_at", ""), reverse=True):
            date = p.get("published_at", "")[:10] if p.get("published_at") else "draft"
            md += f"- [{p['title']}]({p.get('url', '')}) ({date})\n"

        save_markdown(md, tag_dir / "README.md")

    # Save each author
    print("  Saving authors...")
    for author in all_authors:
        slug = author["slug"]
        author_dir = AUTHORS_DIR / slug
        author_dir.mkdir(exist_ok=True)

        author_data = {**author}
        author_data["posts"] = author_to_posts.get(slug, [])
        author_data["post_count"] = len(author_data["posts"])
        author_data["local_profile_image"] = author_image_map.get(author.get("profile_image"))
        author_data["local_cover_image"] = author_image_map.get(author.get("cover_image"))
        save_json(author_data, author_dir / "author.json")

        posts_list = author_to_posts.get(slug, [])
        md = f"# {author.get('name', slug)}\n\n"
        if author.get('bio'):
            md += f"{author['bio']}\n\n"
        if author.get('location'):
            md += f"**Location:** {author['location']}\n"
        if author.get('website'):
            md += f"**Website:** {author['website']}\n"
        md += f"\n## Posts ({len(posts_list)})\n\n"
        for p in sorted(posts_list, key=lambda x: x.get("published_at", ""), reverse=True):
            date = p.get("published_at", "")[:10] if p.get("published_at") else "draft"
            md += f"- [{p['title']}]({p.get('url', '')}) ({date})\n"

        save_markdown(md, author_dir / "README.md")

    # Save each post
    print("  Saving posts...")
    for post in all_posts:
        slug = post.get("slug", "unknown")
        post_dir = POSTS_DIR / slug
        post_dir.mkdir(exist_ok=True)

        # Post JSON with full data
        post_data = {**post}
        post_data["tag_details"] = post_to_tags.get(slug, [])
        post_data["author_details"] = post_to_authors.get(slug, [])
        post_data["local_feature_image"] = post_image_map.get(post.get("feature_image"))
        save_json(post_data, post_dir / "post.json")

        # Post HTML
        if post.get("html"):
            save_markdown(post["html"], post_dir / "content.html")

        # Post markdown-ish version
        tags_list = post_to_tags.get(slug, [])
        authors_list = post_to_authors.get(slug, [])

        md = f"---\n"
        md += f"title: \"{post.get('title', '').replace('\"', '\\\"')}\"\n"
        md += f"slug: {slug}\n"
        md += f"id: {post['id']}\n"
        md += f"published_at: {post.get('published_at', 'draft')}\n"
        md += f"updated_at: {post.get('updated_at', '')}\n"
        md += f"featured: {post.get('featured', False)}\n"
        md += f"reading_time: {post.get('reading_time', 0)} min\n"
        if post.get('feature_image'):
            md += f"feature_image: {post['feature_image']}\n"
        if post.get('custom_excerpt'):
            md += f"excerpt: \"{post['custom_excerpt'].replace('\"', '\\\"')}\"\n"
        if post.get('meta_title'):
            md += f"meta_title: \"{post['meta_title'].replace('\"', '\\\"')}\"\n"
        if post.get('meta_description'):
            md += f"meta_description: \"{post['meta_description'].replace('\"', '\\\"')}\"\n"
        if post.get('canonical_url'):
            md += f"canonical_url: {post['canonical_url']}\n"
        md += f"url: {post.get('url', '')}\n"

        md += f"tags:\n"
        for t in tags_list:
            md += f"  - name: {t['name']}\n"
            md += f"    slug: {t['slug']}\n"

        md += f"authors:\n"
        for a in authors_list:
            md += f"  - name: {a['name']}\n"
            md += f"    slug: {a['slug']}\n"

        md += f"---\n\n"
        md += f"# {post.get('title', 'Untitled')}\n\n"

        if post.get("plaintext"):
            md += post["plaintext"]
        elif post.get("html"):
            md += post["html"]

        save_markdown(md, post_dir / "README.md")

    # Save each page
    print("  Saving pages...")
    pages_dir = BACKUP_DIR / "pages"
    pages_dir.mkdir(exist_ok=True)
    for page in all_pages:
        slug = page.get("slug", "unknown")
        page_dir = pages_dir / slug
        page_dir.mkdir(exist_ok=True)
        save_json(page, page_dir / "page.json")
        if page.get("html"):
            save_markdown(page["html"], page_dir / "content.html")

        md = f"---\ntitle: \"{page.get('title', '').replace('\"', '\\\"')}\"\nslug: {slug}\n---\n\n"
        md += f"# {page.get('title', 'Untitled')}\n\n"
        md += page.get("plaintext") or page.get("html") or ""
        save_markdown(md, page_dir / "README.md")

    # ----------------------------------------------------------
    # 6. RELATIONSHIP FILES
    # ----------------------------------------------------------
    print("  Creating relationship files...")

    # Tag -> Posts relationships
    save_json(dict(tag_to_posts), RELATIONSHIPS_DIR / "tag_to_posts.json")

    # Post -> Tags relationships
    save_json(dict(post_to_tags), RELATIONSHIPS_DIR / "post_to_tags.json")

    # Author -> Posts relationships
    save_json(dict(author_to_posts), RELATIONSHIPS_DIR / "author_to_posts.json")

    # Post -> Authors relationships
    save_json(dict(post_to_authors), RELATIONSHIPS_DIR / "post_to_authors.json")

    # Cross-reference: Tag matrix (which tags appear together)
    tag_cooccurrence = defaultdict(lambda: defaultdict(int))
    for post_tags in post_to_tags.values():
        slugs = [t["slug"] for t in post_tags]
        for i, s1 in enumerate(slugs):
            for s2 in slugs[i+1:]:
                tag_cooccurrence[s1][s2] += 1
                tag_cooccurrence[s2][s1] += 1
    save_json({k: dict(v) for k, v in tag_cooccurrence.items()}, RELATIONSHIPS_DIR / "tag_cooccurrence.json")

    # Cross-reference markdown
    md = "# Tag-to-Posts Cross Reference\n\n"
    md += f"Generated: {datetime.now().isoformat()}\n\n"
    md += "| Tag | Post Count | Posts |\n"
    md += "|-----|-----------|-------|\n"
    for tag in sorted(all_tags, key=lambda t: len(tag_to_posts.get(t["slug"], [])), reverse=True):
        slug = tag["slug"]
        posts = tag_to_posts.get(slug, [])
        titles = ", ".join([p["title"][:40] for p in posts[:5]])
        if len(posts) > 5:
            titles += f" (+{len(posts)-5} more)"
        md += f"| {tag.get('name', slug)} | {len(posts)} | {titles} |\n"
    save_markdown(md, RELATIONSHIPS_DIR / "tag_posts_crossref.md")

    # Post-to-Tags cross reference markdown
    md = "# Post-to-Tags Cross Reference\n\n"
    md += f"Generated: {datetime.now().isoformat()}\n\n"
    md += "| Post | Published | Tags |\n"
    md += "|------|-----------|------|\n"
    for post in sorted(all_posts, key=lambda p: p.get("published_at", ""), reverse=True):
        slug = post.get("slug", "")
        tags = post_to_tags.get(slug, [])
        tag_names = ", ".join([t["name"] for t in tags])
        date = post.get("published_at", "")[:10] if post.get("published_at") else "draft"
        title = post.get("title", "Untitled")[:50]
        md += f"| {title} | {date} | {tag_names} |\n"
    save_markdown(md, RELATIONSHIPS_DIR / "post_tags_crossref.md")

    # ----------------------------------------------------------
    # 7. SUMMARY / INDEX
    # ----------------------------------------------------------
    print("  Creating index files...")

    # Master index
    md = f"# Ghost Blog Backup: {GHOST_URL}\n\n"
    md += f"**Backup Date:** {datetime.now().isoformat()}\n\n"
    md += f"## Summary\n\n"
    md += f"| Resource | Count |\n"
    md += f"|----------|-------|\n"
    md += f"| Posts | {len(all_posts)} |\n"
    md += f"| Pages | {len(all_pages)} |\n"
    md += f"| Tags | {len(all_tags)} |\n"
    md += f"| Authors | {len(all_authors)} |\n"
    md += f"| Tag Images | {len(tag_image_map)} |\n"
    md += f"| Author Images | {len(author_image_map)} |\n"
    md += f"| Post Images | {len(post_image_map)} |\n"
    md += f"\n## Directory Structure\n\n"
    md += "```\n"
    md += "ghost-io-backup/\n"
    md += "├── posts/           # Each post in its own directory\n"
    md += "│   └── {slug}/\n"
    md += "│       ├── post.json      # Full post data with tags & authors\n"
    md += "│       ├── content.html   # Raw HTML content\n"
    md += "│       └── README.md      # Formatted post with frontmatter\n"
    md += "├── pages/           # Static pages\n"
    md += "│   └── {slug}/\n"
    md += "│       ├── page.json\n"
    md += "│       ├── content.html\n"
    md += "│       └── README.md\n"
    md += "├── tags/            # Each tag with its posts\n"
    md += "│   └── {slug}/\n"
    md += "│       ├── tag.json       # Tag data + all posts list\n"
    md += "│       └── README.md      # Tag overview with post list\n"
    md += "├── authors/         # Each author with their posts\n"
    md += "│   └── {slug}/\n"
    md += "│       ├── author.json\n"
    md += "│       └── README.md\n"
    md += "├── images/          # All downloaded images\n"
    md += "│   ├── posts/       # Post feature + inline images\n"
    md += "│   ├── tags/        # Tag feature images\n"
    md += "│   └── authors/     # Author profile & cover images\n"
    md += "├── relationships/   # Cross-reference files\n"
    md += "│   ├── tag_to_posts.json\n"
    md += "│   ├── post_to_tags.json\n"
    md += "│   ├── author_to_posts.json\n"
    md += "│   ├── post_to_authors.json\n"
    md += "│   ├── tag_cooccurrence.json\n"
    md += "│   ├── tag_posts_crossref.md\n"
    md += "│   └── post_tags_crossref.md\n"
    md += "├── data/            # Raw API responses\n"
    md += "│   ├── all_posts.json\n"
    md += "│   ├── all_pages.json\n"
    md += "│   ├── all_tags.json\n"
    md += "│   ├── all_authors.json\n"
    md += "│   └── *_image_map.json\n"
    md += "└── README.md        # This file\n"
    md += "```\n"

    md += f"\n## All Tags ({len(all_tags)})\n\n"
    for tag in sorted(all_tags, key=lambda t: t.get("name", "").lower()):
        count = len(tag_to_posts.get(tag["slug"], []))
        md += f"- **[{tag.get('name', tag['slug'])}](tags/{tag['slug']}/)** ({count} posts)\n"

    md += f"\n## All Posts ({len(all_posts)})\n\n"
    for post in sorted(all_posts, key=lambda p: p.get("published_at", ""), reverse=True):
        date = post.get("published_at", "")[:10] if post.get("published_at") else "draft"
        tags = [t["name"] for t in post_to_tags.get(post.get("slug", ""), [])]
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        md += f"- **[{post.get('title', 'Untitled')}](posts/{post.get('slug', '')}/)** ({date}){tag_str}\n"

    if all_pages:
        md += f"\n## All Pages ({len(all_pages)})\n\n"
        for page in all_pages:
            md += f"- **[{page.get('title', 'Untitled')}](pages/{page.get('slug', '')}/)** \n"

    md += f"\n## All Authors ({len(all_authors)})\n\n"
    for author in all_authors:
        count = len(author_to_posts.get(author["slug"], []))
        md += f"- **[{author.get('name', author['slug'])}](authors/{author['slug']}/)** ({count} posts)\n"

    save_markdown(md, BACKUP_DIR / "README.md")

    # ----------------------------------------------------------
    # DONE
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("BACKUP COMPLETE!")
    print(f"  Posts: {len(all_posts)}")
    print(f"  Pages: {len(all_pages)}")
    print(f"  Tags: {len(all_tags)}")
    print(f"  Authors: {len(all_authors)}")
    print(f"  Images: {len(tag_image_map) + len(author_image_map) + len(post_image_map)}")
    print(f"  Relationships: tag->post, post->tag, author->post, post->author, tag cooccurrence")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

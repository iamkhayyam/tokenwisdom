#!/usr/bin/env python3
"""
Create individual git commits for each post, dated to published_at.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path(__file__).parent
POSTS_DIR = BACKUP_DIR / "posts"
DATA_DIR = BACKUP_DIR / "data"


def run_git(*args, env_extra=None):
    """Run a git command."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(BACKUP_DIR),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0 and "nothing to commit" not in result.stderr + result.stdout:
        print(f"  [WARN] git {' '.join(args[:3])}: {result.stderr.strip()}")
    return result


def get_post_images(slug, image_map):
    """Get all image files associated with a post slug."""
    images = []
    img_dir = BACKUP_DIR / "images" / "posts"
    if img_dir.exists():
        for f in img_dir.iterdir():
            if f.name.startswith(slug + "_") or f.name.startswith(slug + "__"):
                images.append(f)
    return images


def main():
    # Load posts
    with open(DATA_DIR / "all_posts.json") as f:
        all_posts = json.load(f)

    # Sort by published_at chronologically (oldest first)
    # Put drafts (no published_at) at the end
    def sort_key(p):
        d = p.get("published_at")
        if d:
            return (0, d)
        return (1, p.get("created_at", "9999"))

    all_posts.sort(key=sort_key)

    print(f"Total posts: {len(all_posts)}")
    if all_posts:
        earliest = all_posts[0].get("published_at", all_posts[0].get("created_at", ""))
        print(f"Earliest: {earliest}")
        latest = all_posts[-1].get("published_at", all_posts[-1].get("created_at", ""))
        print(f"Latest: {latest}")

    # Step 1: Reset repo to empty (keep files on disk)
    print("\n[1] Resetting git history...")
    run_git("checkout", "--orphan", "temp_branch")
    run_git("rm", "-rf", "--cached", ".")

    # Step 2: First commit - infrastructure files (tags, authors, pages, data, etc.)
    # Date it to the earliest post
    earliest_date = all_posts[0].get("published_at") or all_posts[0].get("created_at", "2024-01-01T00:00:00.000Z")
    print(f"\n[2] Creating infrastructure commit dated {earliest_date[:10]}...")

    # Add non-post files
    infra_paths = [
        ".gitignore", "backup.py", "README.md",
        "tags", "authors", "pages",
        "data", "relationships",
        "images/tags", "images/authors",
    ]
    for p in infra_paths:
        full = BACKUP_DIR / p
        if full.exists():
            run_git("add", p)

    date_env = {
        "GIT_AUTHOR_DATE": earliest_date,
        "GIT_COMMITTER_DATE": earliest_date,
    }
    run_git(
        "commit", "-m",
        f"Initialize blog backup: tags, authors, pages, relationships\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>",
        env_extra=date_env,
    )

    # Step 3: One commit per post
    print(f"\n[3] Creating {len(all_posts)} post commits...")

    for i, post in enumerate(all_posts):
        slug = post.get("slug", "unknown")
        title = post.get("title", "Untitled")
        pub_date = post.get("published_at") or post.get("created_at", "2024-01-01T00:00:00.000Z")

        post_dir = POSTS_DIR / slug
        if not post_dir.exists():
            print(f"  [{i+1}] SKIP {slug} - directory not found")
            continue

        # Add post directory
        run_git("add", f"posts/{slug}")

        # Add associated images
        img_dir = BACKUP_DIR / "images" / "posts"
        if img_dir.exists():
            for f in img_dir.iterdir():
                if f.name.startswith(slug + "_") or f.name.startswith(slug + "__"):
                    run_git("add", f"images/posts/{f.name}")

        # Get tags for commit message
        tags = post.get("tags", [])
        tag_names = [t.get("name", "") for t in tags[:5]]
        tag_str = f"\n\nTags: {', '.join(tag_names)}" if tag_names else ""

        date_env = {
            "GIT_AUTHOR_DATE": pub_date,
            "GIT_COMMITTER_DATE": pub_date,
        }

        msg = f"Add post: {title}{tag_str}\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
        result = run_git("commit", "-m", msg, env_extra=date_env)

        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(all_posts)}] {slug} ({pub_date[:10]})")

    # Step 4: Add any remaining untracked files (images not matched to a post)
    print("\n[4] Adding any remaining files...")
    run_git("add", ".")
    result = run_git("commit", "-m",
        "Add remaining images and files\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>")
    if "nothing to commit" in (result.stdout + result.stderr):
        print("  No remaining files to add.")
    else:
        print("  Committed remaining files.")

    # Step 5: Replace master with this branch
    print("\n[5] Replacing master branch...")
    run_git("branch", "-D", "master")
    run_git("branch", "-m", "master")

    # Count commits
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(BACKUP_DIR), capture_output=True, text=True,
    )
    count = result.stdout.strip()

    print(f"\nDone! Created {count} commits with historical dates.")
    print("Run: git push --force origin master")

    return 0


if __name__ == "__main__":
    sys.exit(main())

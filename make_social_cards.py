#!/usr/bin/env python3
"""
make_social_cards.py — per-post social cards for Token Wisdom.

Three cards per visible post:

  docs/social/posts/<slug>.png          1200×630  landscape  (og:image, X, Facebook)
  docs/social/posts/<slug>-portrait.png 1080×1350 portrait   (Instagram feed, LinkedIn)
  docs/social/posts/<slug>-story.png    1080×1920 story      (TikTok, Instagram Stories)

Landscape: section kicker + title + excerpt left, feature image right.
Portrait / Story: feature image top (large), branding overlay, title + excerpt below.
Fallback when no local feature image: text-only / orb layout.

Essays → paper palette. Newsletters → dark palette.

Usage:
  python3 make_social_cards.py                     # all visible posts, skip existing
  python3 make_social_cards.py --slug <slug>        # one post
  python3 make_social_cards.py --format landscape   # one format only
  python3 make_social_cards.py --force              # re-render existing
  python3 make_social_cards.py --keep-src           # keep HTML source files
  python3 make_social_cards.py --dry-run            # print plan, no Chrome
"""

import argparse
import html as _html
import json
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

ROOT  = Path(__file__).parent
DATA  = ROOT / "data"
DOCS  = ROOT / "docs"
OUT   = DOCS / "social" / "posts"
SRC   = OUT / "src"
IMAGES = ROOT / "images"
POSTS_IMGS = IMAGES / "posts"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SITE_NAME = "Token Wisdom"
DOMAIN    = "tokenwisdom.org"
FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Libre+Caslon+Display&"
    "family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&"
    "family=DM+Mono:wght@300;400;500&display=swap"
)

PAPER = {
    "bg":      "#f8f4ea",
    "ink":     "#2b2620",
    "muted":   "#6f6455",
    "faint":   "#9a8d78",
    "rule":    "#d9d0be",
    "accent":  "#c05f24",
    "orbwash": "rgba(192,95,36,.10)",
    "imgover": "rgba(40,32,20,.28)",   # subtle tint over feature image
}
DARK = {
    "bg":      "#15130e",
    "ink":     "#f3ecdd",
    "muted":   "#a59c8a",
    "faint":   "#8e8470",
    "rule":    "#2a2718",
    "accent":  "#d98a4e",
    "orbwash": "rgba(200,82,26,.22)",
    "imgover": "rgba(10,8,4,.40)",
}

NEWSLETTER_TAG_SLUG = "worthafortune"

e = lambda s: _html.escape(str(s), quote=True)

# ---------------------------------------------------------------------------
# Image map — Ghost URL → local filename
# ---------------------------------------------------------------------------
_IMG_MAP: dict | None = None

def _img_map() -> dict:
    global _IMG_MAP
    if _IMG_MAP is None:
        try:
            _IMG_MAP = json.loads((DATA / "post_image_map.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            _IMG_MAP = {}
    return _IMG_MAP


def local_feature_image(post) -> Path | None:
    """Return an absolute local path to the post's feature image, or None."""
    url = post.get("feature_image") or ""
    if not url:
        return None
    fname = _img_map().get(url)
    if not fname:
        # Try normalizing the Ghost host variant
        alt = url.replace("tokenwisdom.ghost.io", "ghost-production-198e.up.railway.app")
        fname = _img_map().get(alt) or _img_map().get(
            url.replace("ghost-production-198e.up.railway.app", "tokenwisdom.ghost.io"))
    if not fname:
        return None
    p = POSTS_IMGS / fname
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# Post helpers
# ---------------------------------------------------------------------------

def is_hidden(post) -> bool:
    slugs = {t.get("slug", "") for t in (post.get("tags") or [])}
    return "hash-unlisted" in slugs


def is_newsletter(post) -> bool:
    slugs = {t.get("slug", "") for t in (post.get("tags") or [])}
    return NEWSLETTER_TAG_SLUG in slugs


def palette(post) -> dict:
    return DARK if is_newsletter(post) else PAPER


def section_kicker(post) -> str:
    return "POW · Weekly Edition" if is_newsletter(post) else "ACL · Essay"


def fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except Exception:
        return iso[:10]


def edition_number(post) -> str:
    m = re.match(r"^(\d+(?:st|nd|rd|th)\s+Edition)", post.get("title", ""), re.I)
    return m.group(1) if m else ""


def week_number(post) -> str:
    """Extract 'W19' from raw title like '159th Edition 🔮 Week 19'."""
    m = re.search(r"Week\s+(\d+)", post.get("title", ""), re.I)
    return f"W{m.group(1)}" if m else ""


def week_range(post) -> str:
    """Compute covered week as 'MAY 03–09, 2026' (Mon–Sun before publish date)."""
    iso = post.get("published_at", "")
    if not iso:
        return ""
    try:
        pub = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        end   = pub - timedelta(days=2)   # Sunday before publish
        start = pub - timedelta(days=8)   # Monday before that
        if start.month == end.month:
            return f"{start.strftime('%b %d').upper()}–{end.strftime('%d, %Y')}"
        return f"{start.strftime('%b %d').upper()}–{end.strftime('%b %d, %Y').upper()}"
    except Exception:
        return ""


def display_title(post) -> str:
    raw = post.get("title") or ""
    if is_newsletter(post):
        # Strip "Nth Edition [anything non-alpha] Week N" — handles emoji separators
        cleaned = re.sub(
            r"^\d+(?:st|nd|rd|th)\s+Edition\s*[^a-z]*\s*", "", raw, flags=re.I
        ).strip()
        # If what remains is only "Week N[N]" the title adds nothing over the edition line
        if re.match(r"^Week\s+\d+\s*$", cleaned, re.I):
            cleaned = ""
        return cleaned  # may be empty — callers handle that
    return raw


def clean_excerpt(post, max_chars=180) -> str:
    ex = (post.get("custom_excerpt") or post.get("excerpt") or "").strip()
    if len(ex) > max_chars:
        ex = ex[:max_chars].rsplit(" ", 1)[0] + "…"
    return ex


def title_font_size(title: str, short: str, mid: str, long_: str,
                    short_th=50, mid_th=80) -> str:
    n = len(title)
    if n <= short_th: return short
    if n <= mid_th:   return mid
    return long_


def _wrap(title: str, max_chars=55) -> str:
    if len(title) <= max_chars:
        return e(title)
    return "<br>".join(e(l) for l in textwrap.wrap(title, max_chars))


# ---------------------------------------------------------------------------
# SVG orb
# ---------------------------------------------------------------------------

def orb_svg() -> str:
    svg = (IMAGES / "crystal-ball.svg").read_text()
    freeze = ("<style>*{animation:none!important}"
              ".cb-flare,.cb-flare-h,.cb-flare-v,.cb-flare-d{display:none}</style>")
    return svg.replace("</svg>", freeze + "</svg>")


# ---------------------------------------------------------------------------
# Base HTML doc
# ---------------------------------------------------------------------------

def base_css(p: dict) -> str:
    return f"""
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{ width:100%; height:100%; overflow:hidden; }}
    body {{
      background:{p['bg']}; color:{p['ink']};
      font-family:'Libre Caslon Display', Georgia, serif;
      -webkit-font-smoothing:antialiased; position:relative;
    }}
    .glow {{
      position:absolute; border-radius:50%;
      background:radial-gradient(circle, {p['orbwash']} 0%, transparent 68%);
      pointer-events:none;
    }}
    """


def doc(w: int, h: int, body_html: str, extra_css="", p: dict = None) -> str:
    p = p or DARK
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link href="{FONTS}" rel="stylesheet">'
        f'<style>{base_css(p)}{extra_css}</style>'
        f'</head><body style="width:{w}px;height:{h}px">{body_html}</body></html>'
    )


# ---------------------------------------------------------------------------
# LANDSCAPE card  1200 × 630
# Feature image right panel; text left. Falls back to text-only.
# ---------------------------------------------------------------------------

def landscape_card(post: dict) -> tuple[int, int, str]:
    p   = palette(post)
    bg  = p["bg"]; ink = p["ink"]; acc = p["accent"]
    fnt = p["ink"]; muted = p["muted"]; rul = p["rule"]
    # For essays with a feature image, text sits on a dark gradient — use dark text palette
    _tp = DARK if (not is_newsletter(post)) else p
    w, h = 1200, 630

    title    = display_title(post)
    excerpt  = clean_excerpt(post, max_chars=120)
    date     = fmt_date(post.get("published_at", ""))
    kicker   = section_kicker(post)
    img_path = local_feature_image(post)
    has_img  = img_path is not None

    t_size = title_font_size(title, "58px", "46px", "36px", short_th=45, mid_th=90)

    # Full-bleed image with a semi-transparent bottom vignette — image shows everywhere,
    # just progressively darkened toward the bottom for text legibility.
    foot_bot  = 40
    grad_h    = int(h * 0.72)
    dark_bg   = DARK["bg"]
    grad_bg   = dark_bg if has_img else bg
    grad_spec = f"transparent 0%, {grad_bg}77 42%, {grad_bg}cc 80%"

    if has_img:
        bg_layer = (
            f'<div style="position:absolute;inset:0;'
            f'background:url(\'file://{img_path}\') center/cover no-repeat;"></div>'
        )
        gradient = (
            f'<div style="position:absolute;bottom:0;left:0;right:0;height:{grad_h}px;'
            f'background:linear-gradient(to bottom,{grad_spec});"></div>'
        )
    else:
        bg_layer = (
            f'<div style="position:absolute;inset:0;background:{bg};">'
            f'<div class="glow" style="width:700px;height:700px;right:-200px;top:-200px;"></div>'
            f'<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:flex-end;padding-right:80px;">'
            f'<div style="width:260px;height:{int(260*450/400)}px">{orb_svg()}</div>'
            f'</div></div>'
        )
        gradient = ""

    # Brand bar — top of card
    orb_sz = 28
    ls_edition = edition_number(post) if is_newsletter(post) else ""
    ls_ed_pill = (
        f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;text-transform:uppercase;'
        f'letter-spacing:.14em;font-size:11px;font-weight:700;'
        f'color:{p["bg"]};background:{acc};padding:4px 10px;border-radius:2px;">'
        f'{e(ls_edition)}</span>'
    ) if ls_edition else ""
    brand_bar = (
        f'<div style="position:absolute;top:26px;left:40px;right:40px;'
        f'display:flex;align-items:center;justify-content:space-between;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;text-transform:uppercase;'
        f'letter-spacing:.22em;font-size:11px;font-weight:500;color:{acc};">{e(kicker)}</span>'
        f'{ls_ed_pill}</div>'
        f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;text-transform:uppercase;'
        f'letter-spacing:.16em;font-size:11px;color:{muted};">{e(SITE_NAME)}</span>'
        f'</div>'
    )

    tp = _tp if has_img else p
    title_html = _title_div(title, t_size, tp) if title else ""
    excerpt_html = _excerpt_div(excerpt, "27px", tp) if excerpt else ""
    t_acc = tp["accent"]; t_muted = tp["muted"]; t_rul = tp["rule"]

    orb_seal = (
        f'<div style="width:{orb_sz}px;height:{int(orb_sz*450/400)}px;flex:none;opacity:.85;">'
        f'{orb_svg()}</div>'
    )

    bottom_block = (
        f'<div style="position:absolute;bottom:{foot_bot}px;left:40px;right:40px;'
        f'display:flex;flex-direction:column;gap:10px;">'
        f'{title_html}{excerpt_html}'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'border-top:1px solid {t_rul};padding-top:10px;margin-top:2px;">'
        f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;text-transform:uppercase;'
        f'letter-spacing:.14em;font-size:11px;color:{t_acc};">{e(date)}</span>'
        f'<span style="display:flex;align-items:center;gap:10px;">'
        f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;text-transform:uppercase;'
        f'letter-spacing:.14em;font-size:11px;color:{t_muted};">{e(DOMAIN)}</span>'
        f'{orb_seal}</span>'
        f'</div></div>'
    )

    body = bg_layer + gradient + brand_bar + bottom_block
    return w, h, doc(w, h, body, p=p)


# ---------------------------------------------------------------------------
# PORTRAIT card  1080 × 1350  (Instagram feed, LinkedIn)
# Feature image fills top ~58%; branded text panel below.
# ---------------------------------------------------------------------------

def portrait_card(post: dict) -> tuple[int, int, str]:
    return _vertical_card(post, w=1080, h=1350, img_frac=0.70)


# ---------------------------------------------------------------------------
# STORY card  1080 × 1920  (TikTok, Instagram Stories)
# Feature image fills top ~72%; text panel is taller.
# ---------------------------------------------------------------------------

def story_card(post: dict) -> tuple[int, int, str]:
    return _vertical_card(post, w=1080, h=1920, img_frac=0.72)


def _excerpt_div(excerpt: str, size: str, p: dict) -> str:
    if not excerpt:
        return ""
    ink = p['ink']
    return (f'<div style="font-family:\'Source Serif 4\',Georgia,serif;'
            f'font-weight:400;font-size:{size};line-height:1.55;'
            f'color:{ink};">{e(excerpt)}</div>')


def _title_div(title: str, size: str, p: dict) -> str:
    if not title:
        return ""
    ink = p['ink']
    return (f'<div style="font-family:\'Source Serif 4\',Georgia,serif;'
            f'font-style:italic;font-weight:600;font-size:{size};line-height:1.14;'
            f'letter-spacing:-.010em;color:{ink};">{_wrap(title, 32)}</div>')


def _vertical_card(post: dict, w: int, h: int, img_frac: float) -> tuple[int, int, str]:
    p       = palette(post)
    dark    = is_newsletter(post)

    title    = display_title(post)
    excerpt  = clean_excerpt(post, max_chars=240 if not title else 190)
    date     = fmt_date(post.get("published_at", ""))
    kicker   = section_kicker(post)
    edition  = edition_number(post) if dark else ""
    wk_num   = week_number(post) if dark else ""
    wk_range = week_range(post) if dark else ""
    img_path = local_feature_image(post)
    has_img  = img_path is not None

    orb_sz  = 60
    t_size  = title_font_size(title, "92px", "72px", "54px", short_th=40, mid_th=70)
    ex_size = "38px" if h >= 1800 else "34px"

    # Branding pill + orb — top of card, overlaid on image
    ink  = p["ink"]
    bg   = p["bg"]
    acc  = p["accent"]
    fnt  = p["faint"]
    rul  = p["rule"]

    # Brand bar: kicker pill left, edition pill center (newsletters only), orb right
    edition_pill = (
        f'<div style="font-family:\'DM Mono\',ui-monospace,monospace;'
        f'text-transform:uppercase;letter-spacing:.14em;font-size:15px;font-weight:700;'
        f'color:{bg};background:{acc};padding:6px 16px;border-radius:2px;">'
        f'{e(edition)}</div>'
    ) if edition else ""

    brand_bar = (
        f'<div style="position:absolute;top:32px;left:40px;right:40px;'
        f'display:flex;align-items:center;justify-content:space-between;z-index:10;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="font-family:\'DM Mono\',ui-monospace,monospace;'
        f'text-transform:uppercase;letter-spacing:.20em;font-size:13px;'
        f'color:{ink};font-weight:500;background:{bg};padding:6px 14px;border-radius:2px;">{e(kicker)}</div>'
        f'{edition_pill}</div>'
        f'<div style="width:{orb_sz}px;height:{int(orb_sz*450/400)}px;opacity:.88">{orb_svg()}</div>'
        f'</div>'
    )

    # Newsletter title: "159th Edition · W19 · MAY 03–09, 2026"
    nl_parts = [p for p in [edition, wk_num, wk_range] if p]
    nl_title  = "  ·  ".join(nl_parts)
    edition_line = (
        f'<div style="font-family:\'Source Serif 4\',Georgia,serif;'
        f'font-weight:600;font-size:28px;line-height:1.2;'
        f'color:{ink};margin-bottom:4px;">{e(nl_title)}</div>'
    ) if nl_title and dark else ""

    if dark:
        # Full-bleed image with semi-transparent vignette — image bleeds through everywhere,
        # just darkened enough for text legibility. Eliminates dead-zone above/below text.
        foot_bot = 64
        grad_h   = int(h * 0.42)
        grad_spec = f"transparent 0%, {bg}66 50%, {bg}aa 85%"

        if has_img:
            bg_layer = (
                f'<div style="position:absolute;inset:0;'
                f'background:url(\'file://{img_path}\') center top/cover no-repeat;"></div>'
            )
        else:
            bg_layer = (
                f'<div style="position:absolute;inset:0;background:{bg};">'
                f'<div class="glow" style="width:{int(w*1.5)}px;height:{int(w*1.5)}px;'
                f'left:50%;top:40%;transform:translate(-50%,-50%);"></div>'
                f'<div style="position:absolute;inset:0;display:flex;align-items:center;'
                f'justify-content:center;">'
                f'<div style="width:{int(w*0.42)}px;height:{int(w*0.42*450/400)}px">{orb_svg()}</div>'
                f'</div></div>'
            )

        gradient = (
            f'<div style="position:absolute;bottom:0;left:0;right:0;height:{grad_h}px;'
            f'background:linear-gradient(to bottom,{grad_spec});"></div>'
        )

        # Single block anchored to the bottom: content + rule + footer together
        bottom_block = (
            f'<div style="position:absolute;bottom:{foot_bot}px;left:48px;right:48px;'
            f'display:flex;flex-direction:column;gap:12px;">'
            f'{edition_line}{_title_div(title, t_size, p)}{_excerpt_div(excerpt, ex_size, p)}'
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'border-top:1px solid {rul};padding-top:12px;margin-top:4px;">'
            f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;'
            f'text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:{acc};">{e(date)}</span>'
            f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;'
            f'text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:{fnt};">{e(DOMAIN)}</span>'
            f'</div></div>'
        )

        body = bg_layer + gradient + brand_bar + bottom_block

    else:
        # Essay: full-bleed paper illustration, dark gradient at bottom for cinematic feel.
        # Text uses DARK palette (light on dark) regardless of essay classification.
        dp   = DARK
        d_ink = dp["ink"]; d_acc = dp["accent"]; d_fnt = dp["faint"]; d_rul = dp["rule"]
        dark_bg = dp["bg"]
        foot_bot  = 64
        grad_h    = int(h * 0.42)
        grad_spec = f"transparent 0%, {dark_bg}66 50%, {dark_bg}aa 85%"

        if has_img:
            bg_layer = (
                f'<div style="position:absolute;inset:0;'
                f'background:url(\'file://{img_path}\') center top/cover no-repeat;"></div>'
            )
        else:
            bg_layer = (
                f'<div style="position:absolute;inset:0;background:{bg};">'
                f'<div class="glow" style="width:{int(w*1.4)}px;height:{int(w*1.4)}px;'
                f'left:50%;top:40%;transform:translate(-50%,-50%);"></div>'
                f'<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;">'
                f'<div style="width:{int(w*0.42)}px;height:{int(w*0.42*450/400)}px">{orb_svg()}</div>'
                f'</div></div>'
            )

        gradient = (
            f'<div style="position:absolute;bottom:0;left:0;right:0;height:{grad_h}px;'
            f'background:linear-gradient(to bottom,{grad_spec});"></div>'
        )

        title_html_dark  = _title_div(title, t_size, dp)
        excerpt_html_dark = _excerpt_div(excerpt, ex_size, dp)

        bottom_block = (
            f'<div style="position:absolute;bottom:{foot_bot}px;left:48px;right:48px;'
            f'display:flex;flex-direction:column;gap:12px;">'
            f'{title_html_dark}{excerpt_html_dark}'
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'border-top:1px solid {d_rul};padding-top:12px;margin-top:4px;">'
            f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;'
            f'text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:{d_acc};">{e(date)}</span>'
            f'<span style="font-family:\'DM Mono\',ui-monospace,monospace;'
            f'text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:{d_fnt};">{e(DOMAIN)}</span>'
            f'</div></div>'
        )

        body = bg_layer + gradient + brand_bar + bottom_block

    return w, h, doc(w, h, body, p=p)



# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

FORMATS = {
    "landscape": (landscape_card, ""),
    "portrait":  (portrait_card,  "-portrait"),
    "story":     (story_card,     "-story"),
}


def render_card(slug: str, suffix: str, html_str: str, w: int, h: int,
                force=False, keep_src=False) -> bool:
    OUT.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)

    out_png  = OUT / f"{slug}{suffix}.png"
    src_html = SRC / f"{slug}{suffix}.html"

    if out_png.exists() and not force:
        return False

    src_html.write_text(html_str)
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=2",
            f"--window-size={w},{h}",
            "--virtual-time-budget=15000",
            f"--screenshot={out_png}",
            f"file://{src_html}",
        ],
        capture_output=True, check=True,
    )

    if not keep_src:
        src_html.unlink(missing_ok=True)

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Render per-post social cards.")
    ap.add_argument("--slug",   help="Render a single post by slug.")
    ap.add_argument("--format", choices=list(FORMATS), help="Render one format only.")
    ap.add_argument("--force",    action="store_true")
    ap.add_argument("--keep-src", action="store_true")
    ap.add_argument("--dry-run",  action="store_true")
    args = ap.parse_args()

    posts = json.loads((DATA / "all_posts.json").read_text())

    if args.slug:
        posts = [p for p in posts if p.get("slug") == args.slug]
        if not posts:
            print(f"No post found with slug: {args.slug}", file=sys.stderr)
            sys.exit(1)
    else:
        posts = [p for p in posts if not is_hidden(p)]

    formats = {args.format: FORMATS[args.format]} if args.format else FORMATS

    rendered = skipped = errors = 0

    for post in posts:
        slug = post.get("slug") or ""
        if not slug:
            continue

        kind    = "NL" if is_newsletter(post) else "ES"
        has_img = local_feature_image(post) is not None

        for fmt_name, (fn, suffix) in formats.items():
            try:
                w, h, html = fn(post)

                if args.dry_run:
                    img_mark = "🖼" if has_img else "·"
                    print(f"  {kind} {img_mark} [{fmt_name:9s}]  {slug}{suffix}.png")
                    skipped += 1
                    continue

                did = render_card(slug, suffix, html, w, h,
                                  force=args.force, keep_src=args.keep_src)
                if did:
                    rendered += 1
                    print(f"  ✓  {slug}{suffix}.png")
                else:
                    skipped += 1

            except subprocess.CalledProcessError as exc:
                err = exc.stderr[:120].decode(errors="replace") if exc.stderr else str(exc)
                print(f"  ✗  {slug}{suffix}: Chrome error — {err}", file=sys.stderr)
                errors += 1
            except Exception as exc:
                print(f"  ✗  {slug}{suffix}: {exc}", file=sys.stderr)
                errors += 1

    total = rendered + skipped + errors
    if args.dry_run:
        print(f"\n{total} cards across {len(posts)} posts ({len(formats)} format(s))")
    else:
        print(f"\n{rendered} rendered, {skipped} skipped, {errors} errors — {total} total")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

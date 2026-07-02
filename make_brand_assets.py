#!/usr/bin/env python3
"""
make_brand_assets.py — render the Token Wisdom brand asset set.

One source of truth (images/crystal-ball.svg + images/favicon.svg + the
templates below) → every raster the platforms want:

  images/favicon.ico              16/32/48 (link in <head>, copied to docs/ root)
  images/apple-touch-icon.png     180×180, opaque dark
  images/icon-192.png             192×192, opaque dark (webmanifest)
  images/icon-512.png             512×512, opaque dark (webmanifest)
  images/social/og-default.png    2400×1260 (og:image / twitter:image, 1200×630 @2x)
  images/social/x-avatar.png      800×800   (X profile photo, 400 @2x)
  images/social/x-banner.png      3000×1000 (X header, 1500×500 @2x)
  images/social/linkedin-logo.png 600×600   (LinkedIn company logo, 300 @2x)
  images/social/linkedin-banner.png 2256×382 (LinkedIn company cover, 1128×191 @2x)

Rendering is headless Chrome (the only rasterizer on this machine that does
the SVG's gradients + filters justice); favicon derivatives are Pillow.
generate_site.py copies the deployable subset into docs/ on every build.

Usage: python3 make_brand_assets.py [--only og-default,x-avatar,…] [--keep-src]
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
IMAGES = ROOT / "images"
SOCIAL = IMAGES / "social"
SRC = SOCIAL / "src"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SITE_NAME = "Token Wisdom"
TAGLINE = "The Newsletter of Record for the Future of Now"
DOMAIN = "tokenwisdom.org"

# Dark-theme brand tokens (tw dark palette — the ball reads best on dark)
BG = "#15130e"
INK = "#f3ecdd"
MUTED = "#a59c8a"
FAINT = "#8e8470"
RULE = "#2a2718"
ACCENT = "#d98a4e"

FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Libre+Caslon+Display&"
    "family=DM+Mono:wght@300;400;500&display=swap"
)


def base_css():
    return f"""
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    html, body {{ width:100%; height:100%; overflow:hidden; }}
    body {{
      background:{BG}; color:{INK};
      font-family:'Libre Caslon Display', Georgia, serif;
      -webkit-font-smoothing:antialiased;
      position:relative;
    }}
    .glow {{
      position:absolute; border-radius:50%;
      background:radial-gradient(circle, rgba(200,82,26,.22) 0%, rgba(200,82,26,0) 68%);
      pointer-events:none;
    }}
    .mono {{ font-family:'DM Mono', ui-monospace, monospace; text-transform:uppercase; }}
    .kicker {{ color:{ACCENT}; letter-spacing:.22em; font-weight:500; }}
    .wordmark {{ font-weight:400; letter-spacing:-.025em; line-height:.9; color:{INK}; white-space:nowrap; }}
    .tagline {{ color:{MUTED}; letter-spacing:.18em; font-weight:300; line-height:1.7; }}
    .rule {{ border-top:2px solid {INK}; position:relative; }}
    .rule::after {{ content:''; position:absolute; left:0; right:0; top:3px; border-top:1px solid {RULE}; }}
    .foot {{ color:{FAINT}; letter-spacing:.14em; font-weight:300; }}
    .foot .dia {{ color:{ACCENT}; }}
    .orb-wrap {{ position:relative; display:flex; align-items:center; justify-content:center; }}
    .orb-wrap svg {{ width:100%; height:100%; }}
    """


def doc(w, h, body_html, extra_css=""):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<style>{base_css()}{extra_css}</style>
</head><body style="width:{w}px;height:{h}px">{body_html}</body></html>"""


def orb_svg():
    """Inline the crystal ball, frozen: animations off, lens flare hidden.
    (The flare fires on a 9s cycle — captured mid-fire it reads as a white
    starburst, and virtual time makes the captured frame nondeterministic.)"""
    svg = (IMAGES / "crystal-ball.svg").read_text()
    freeze = ("<style>*{animation:none!important}"
              ".cb-flare,.cb-flare-h,.cb-flare-v,.cb-flare-d{display:none}</style>")
    return svg.replace("</svg>", freeze + "</svg>")


def tpl_og_default():
    w, h = 1200, 630
    body = f"""
    <div class="glow" style="width:900px;height:900px;right:-220px;top:-135px"></div>
    <div style="position:absolute;inset:0;padding:64px 72px;display:flex;flex-direction:column">
      <div class="rule"></div>
      <div style="flex:1;display:flex;align-items:center;gap:48px">
        <div style="flex:1;min-width:0">
          <div class="mono kicker" style="font-size:17px;margin-bottom:30px">Est. 2013 &nbsp;&middot;&nbsp; By @iamkhayyam</div>
          <div class="wordmark" style="font-size:112px">Token Wisdom</div>
          <div class="mono tagline" style="font-size:19px;margin-top:34px;max-width:560px">{TAGLINE}</div>
        </div>
        <div class="orb-wrap" style="width:400px;height:450px;flex:none">{orb_svg()}</div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;border-top:1px solid {RULE};padding-top:22px">
        <span class="mono foot" style="font-size:15px;color:{ACCENT}">{DOMAIN}</span>
        <span class="mono foot" style="font-size:15px"><span class="dia">&#9670;</span>&nbsp; 100% Humanly Chosen</span>
      </div>
    </div>"""
    return w, h, doc(w, h, body)


def tpl_x_banner():
    w, h = 1500, 500
    body = f"""
    <div class="glow" style="width:820px;height:820px;right:-160px;top:-190px"></div>
    <div style="position:absolute;inset:0;padding:60px 84px;display:flex;align-items:center;gap:56px">
      <div style="flex:1;min-width:0">
        <div class="mono kicker" style="font-size:15px;margin-bottom:24px">Est. 2013 &nbsp;&middot;&nbsp; 100% Humanly Chosen</div>
        <div class="wordmark" style="font-size:96px">Token Wisdom</div>
        <div class="mono tagline" style="font-size:17px;margin-top:26px">{TAGLINE}</div>
      </div>
      <div class="orb-wrap" style="width:330px;height:371px;flex:none">{orb_svg()}</div>
    </div>"""
    return w, h, doc(w, h, body)


def tpl_linkedin_banner():
    # 1128×191 — shallow strip; LinkedIn overlaps the logo bottom-left, keep clear.
    w, h = 1128, 191
    body = f"""
    <div class="glow" style="width:420px;height:420px;right:-80px;top:-115px"></div>
    <div style="position:absolute;inset:0;padding:0 64px 0 240px;display:flex;align-items:center;gap:40px">
      <div style="flex:1;min-width:0">
        <div class="wordmark" style="font-size:56px">Token Wisdom</div>
        <div class="mono tagline" style="font-size:12px;letter-spacing:.2em;margin-top:12px">{TAGLINE}</div>
      </div>
      <div class="orb-wrap" style="width:118px;height:133px;flex:none">{orb_svg()}</div>
    </div>"""
    return w, h, doc(w, h, body)


def _tpl_mark(size, orb_frac):
    """Square profile mark: the orb on dark, centered glow. Circle-crop safe."""
    orb_w = int(size * orb_frac)
    orb_h = int(orb_w * 450 / 400)
    body = f"""
    <div class="glow" style="width:{int(size * 1.1)}px;height:{int(size * 1.1)}px;
         left:50%;top:50%;transform:translate(-50%,-50%)"></div>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">
      <div class="orb-wrap" style="width:{orb_w}px;height:{orb_h}px">{orb_svg()}</div>
    </div>"""
    return size, size, doc(size, size, body)


TEMPLATES = {
    "og-default": tpl_og_default,
    "x-banner": tpl_x_banner,
    "linkedin-banner": tpl_linkedin_banner,
    "x-avatar": lambda: _tpl_mark(400, 0.8),
    "linkedin-logo": lambda: _tpl_mark(300, 0.8),
}


def render(name, keep_src=False):
    w, h, html = TEMPLATES[name]()
    SRC.mkdir(parents=True, exist_ok=True)
    src = SRC / f"{name}.html"
    src.write_text(html)
    out = SOCIAL / f"{name}.png"
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=2",
        f"--window-size={w},{h}",
        "--virtual-time-budget=15000",
        f"--screenshot={out}",
        f"file://{src}",
    ], check=True, capture_output=True, timeout=120)
    if not keep_src:
        src.unlink()
        try:
            SRC.rmdir()
        except OSError:
            pass
    print(f"  {out.relative_to(ROOT)}  ({w * 2}×{h * 2})")


def render_favicons():
    """favicon.svg → 512 transparent master → ico + touch/manifest icons."""
    from PIL import Image

    master_html = SOCIAL / "_favicon.html"
    master_png = SOCIAL / "_favicon-512.png"
    SOCIAL.mkdir(parents=True, exist_ok=True)
    master_html.write_text(
        "<!DOCTYPE html><html><head><style>html,body{margin:0;background:transparent}"
        "</style></head><body>"
        f'<img src="file://{IMAGES / "favicon.svg"}" width="512" height="512">'
        "</body></html>"
    )
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--default-background-color=00000000", "--window-size=512,512",
        f"--screenshot={master_png}", f"file://{master_html}",
    ], check=True, capture_output=True, timeout=120)
    master_html.unlink()

    ball = Image.open(master_png).convert("RGBA")
    master_png.unlink()

    # favicon.ico — transparent, full-bleed sphere
    ball.save(IMAGES / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"  images/favicon.ico  (16/32/48)")

    # opaque dark icons with breathing room (iOS/Android crop + round corners)
    for out_name, size, pad_frac in (
        ("apple-touch-icon.png", 180, 0.10),
        ("icon-192.png", 192, 0.10),
        ("icon-512.png", 512, 0.10),
    ):
        canvas = Image.new("RGBA", (size, size), BG)
        inner = int(size * (1 - 2 * pad_frac))
        scaled = ball.resize((inner, inner), Image.LANCZOS)
        off = (size - inner) // 2
        canvas.paste(scaled, (off, off), scaled)
        canvas.convert("RGB").save(IMAGES / out_name)
        print(f"  images/{out_name}  ({size}×{size})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated template names (default: all + favicons)")
    ap.add_argument("--keep-src", action="store_true", help="keep rendered HTML in images/social/src/")
    args = ap.parse_args()

    if not Path(CHROME).exists():
        sys.exit("Chrome not found — headless Chrome does the rasterizing.")

    names = args.only.split(",") if args.only else list(TEMPLATES)
    print("Social images…")
    for n in names:
        render(n.strip(), keep_src=args.keep_src)
    if not args.only:
        print("Favicons…")
        render_favicons()
    print("Done.")


if __name__ == "__main__":
    main()

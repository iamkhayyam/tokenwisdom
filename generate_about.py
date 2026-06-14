#!/usr/bin/env python3
"""Generate docs/about/index.html — the Token Wisdom About page."""

from pathlib import Path
from tw_theme import page

DOCS = Path(__file__).parent / "docs"

ABOUT_CSS = """
.about-wrap{max-width:720px;margin:0 auto;padding:3rem 28px 5rem}
.about-hero{border-bottom:2px solid var(--ink);padding-bottom:1.4rem;margin-bottom:2.4rem}
.about-eyebrow{font-family:var(--mono);font-weight:300;font-size:.64rem;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:.6rem}
.about-title{font-family:var(--display);font-weight:400;font-size:clamp(2.6rem,6vw,4.2rem);line-height:.94;letter-spacing:-.025em;color:var(--ink)}
.about-handle{font-family:var(--mono);font-weight:300;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-top:.8rem}

.about-body{font-family:var(--serif);font-optical-sizing:none;font-variation-settings:"opsz" 17;font-size:1.05rem;line-height:1.65;color:var(--ink)}
.about-body p{margin-bottom:1.3rem}
.about-body h2{font-family:var(--display);font-weight:400;font-size:1.9rem;line-height:1;letter-spacing:-.02em;color:var(--ink);margin:2.4rem 0 .9rem;border-top:1px solid var(--rule);padding-top:1.4rem}
.about-body h3{font-family:var(--sans);font-weight:600;font-size:1rem;letter-spacing:.01em;color:var(--ink);margin:1.8rem 0 .5rem}
.about-body hr{border:none;border-top:1px solid var(--rule);margin:2rem 0}
.about-body a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.about-body a:hover{color:var(--accent-deep)}
.about-body blockquote{font-family:var(--display);font-size:1.6rem;font-weight:400;line-height:1.2;letter-spacing:-.02em;color:var(--ink);border-left:3px solid var(--accent);padding-left:1.2rem;margin:2rem 0}

.about-gif{text-align:center;margin:1.8rem 0}
.about-gif img{max-width:320px;border-radius:4px}

.about-cta{background:var(--ink);color:var(--bg);padding:2.4rem 2rem;border-radius:4px;margin:2.8rem 0;text-align:center}
.about-cta-eyebrow{font-family:var(--mono);font-weight:300;font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:oklch(0.78 0.10 55);margin-bottom:.6rem}
.about-cta-title{font-family:var(--display);font-weight:400;font-size:1.7rem;letter-spacing:-.02em;color:var(--bg);margin-bottom:.4rem}
.about-cta-sub{font-family:var(--serif);font-size:.95rem;color:oklch(0.78 0.06 65);margin-bottom:1.4rem}
.about-cta-btn{display:inline-block;font-family:var(--mono);font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;background:var(--accent);color:#fff;padding:.75em 2em;border-radius:2px;transition:background .15s}
.about-cta-btn:hover{background:var(--accent-deep);color:#fff}
.about-cta-fine{font-family:var(--mono);font-size:.58rem;letter-spacing:.08em;text-transform:uppercase;color:oklch(0.55 0.04 65);margin-top:.8rem}

.about-benefits{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem 2rem;margin:1.6rem 0 2rem}
.about-benefit-title{font-family:var(--sans);font-weight:600;font-size:.88rem;color:var(--ink);margin-bottom:.3rem}
.about-benefit-body{font-family:var(--serif);font-size:.88rem;color:var(--ink-muted);line-height:1.5}
@media(max-width:560px){.about-benefits{grid-template-columns:1fr}}

.about-quote{font-family:var(--display);font-size:clamp(1.4rem,4vw,2.2rem);font-weight:400;line-height:1.15;letter-spacing:-.02em;color:var(--ink);text-align:center;padding:2.4rem 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin:2.4rem 0}
"""

BODY = """
<style>{css}</style>
<div class="about-wrap">

  <div class="about-hero">
    <div class="about-eyebrow">About</div>
    <h1 class="about-title">Token Wisdom</h1>
    <div class="about-handle">@iamkhayyam</div>
  </div>

  <div class="about-body">

    <div class="about-gif">
      <img src="https://tokenwisdom.ghost.io/content/images/2024/02/dropping_knowledge-2.gif" alt="Dropping Knowledge">
    </div>

    <p>Hi! I am Khayyam and I'll be your host with the most for this rapidly accelerating journey into the future and back again to understand what's ahead of us and how to best navigate the space and time. You can find me on the <a href="https://twitter.com/iamkhayyam" rel="noreferrer"><em>Twitters</em></a> every once in a while and quite steadily on <a href="https://linkedin.com/in/iamkhayyam" rel="noreferrer"><strong>LinkedIn</strong></a>.</p>

    <p>I am a dynamic visionary in the field of Strategy &amp; Innovation, known for driving emerging technologies and inspiring change. I have a proven track record of nearly two decades of making significant contributions to the organizations I have worked with by pushing the boundaries of what's possible.</p>

    <p>Throughout my career, I have been committed to creating value and pioneering technological progress. My strategic thinking and passion for innovation have made a lasting impact in the industry. I have not only pioneered new technologies but also sought strategic partnerships, relationships, and investments that align with my vision for a brighter and more innovative future.</p>

    <p>In addition to my technical expertise, I catalyze positive change. By leading the way in commercializing technologies and forging new paths in the business landscape, I have consistently shaped the future through innovation and storytelling.</p>

    <div class="about-gif">
      <img src="https://tokenwisdom.ghost.io/content/images/2024/02/451727_b817a.gif" alt="">
    </div>

    <p>Now, imagine standing on the deck of a ship, sailing through the vast sea of information. The waves of tech updates and AI breakthroughs are relentless, each one more powerful than the last. It's a storm of innovation insights and new discoveries, and navigating these waters can feel like steering through a tempest in the dark. But what if you had a guiding star, a crystal ball to glimpse the future?</p>

    <p>Welcome to <strong><em>Token Wisdom</em></strong>, your compass in this digital sea. Here, we are the seafarers charting a course through the complexities, navigating the obscure, and unearthing buried treasures of knowledge.</p>

    <p>So grab your spyglass and prepare to embark on a voyage of discovery. For in this sea of constant change, knowledge isn't just power — it's a treasure chest filled to the brim with gold. Let's set sail into the world of Token Wisdom and peer into the crystal ball of knowledge and understanding — it's worth a fortune!</p>

    <p><em>X marks the spot.</em></p>

    <h2>Learning about tomorrow, today.</h2>

    <div class="about-cta">
      <div class="about-cta-eyebrow">Sign up for Token Wisdom ✨</div>
      <div class="about-cta-title">Baked fresh daily.</div>
      <div class="about-cta-sub">Invest in knowledge. It provides great returns.</div>
      <a class="about-cta-btn" href="https://tokenwisdom.ghost.io/subscribe">Invest in Knowledge →</a>
      <div class="about-cta-fine">No spam. Unsubscribe anytime.</div>
    </div>

    <h3>It's worth a fortune! 🔮</h3>

    <hr>

    <p><strong>— T H E &nbsp; F I N E &nbsp; P R I N T —</strong></p>

    <p>If you subscribe today, you'll get full access to the website as well as email newsletters about new content when it's available. Your subscription makes this site possible and allows Token Wisdom to continue to exist. Thank you! Wait till I start asking you for money!</p>

    <div class="about-benefits">
      <div>
        <div class="about-benefit-title">Access all areas</div>
        <div class="about-benefit-body">By signing up, you'll get access to the full archive of everything that's been published before and everything that's still to come. For now, you get your very own (FREE) private library of 60k curated pieces of content that will tip the skills on your next IQ test! My library is your library.</div>
      </div>
      <div>
        <div class="about-benefit-title">Fresh content, delivered</div>
        <div class="about-benefit-body">Stay up to date with new content sent straight to your inbox! No more worrying about whether you missed something because of a pesky algorithm or news feed.</div>
      </div>
      <div>
        <div class="about-benefit-title">Meet people like you</div>
        <div class="about-benefit-body">Join a community of other subscribers who share the same interests. We have a Telegram channel and group for the links we review and any further discussion there is to be had. This is available to subscribers for now and will be elevated to paid members in the future.</div>
      </div>
      <div>
        <div class="about-benefit-title">Plan today, for tomorrow</div>
        <div class="about-benefit-body">Dig in and get the best of the best before the rest catch on and catch up.</div>
      </div>
    </div>

    <hr>

    <div class="about-quote">"Luck is what happens when preparation meets opportunity."</div>

    <div class="about-gif">
      <img src="https://tokenwisdom.ghost.io/content/images/2024/02/lucky_block_1.gif" alt="Lucky block">
    </div>

  </div>
</div>
""".format(css=ABOUT_CSS)


def build():
    out_dir = DOCS / "about"
    out_dir.mkdir(exist_ok=True)
    html = page("About — Token Wisdom", BODY, prefix="../")
    (out_dir / "index.html").write_text(html)
    print(f"Wrote {out_dir / 'index.html'}")


if __name__ == "__main__":
    build()

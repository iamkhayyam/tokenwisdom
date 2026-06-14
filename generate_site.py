#!/usr/bin/env python3
"""
Token Wisdom static site generator.

Builds two consistent post templates — the essay (A Closer Look) and the
newsletter (Pearls of Wisdom / Token Wisdom Week) — plus a homepage,
tag pages, archive, and tags index, all sharing one editorial design system
(Libre Caslon Display / Source Serif 4 opsz17 / Archivo / DM Mono 300).
"""

import json
import html
import os
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
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

PODCAST_FEED_URL = "https://feeds.captivate.fm/tokenwisdom-and-notebooklm/"
PODCAST_CACHE = BACKUP_DIR / "data" / "podcast_feed.xml"

TAG_DESCRIPTIONS = {
    "a-closer-look": "A weekly essay from a bucket of topics consisting of all things blockchain, artificial intelligence, extended reality, quantum computing, renewable energy, and regenerative practices.",
    "advertising": "The business of attention — how brands court, capture, and occasionally lose us. Ad tech, creative strategy, targeting ethics, and the ever-shifting economics of getting noticed in a noisy world.",
    "agency": "Who's in control — humans, algorithms, or institutions? Explores autonomy, decision-making power, and what it means to act with intention in systems designed to nudge us in predetermined directions.",
    "agi": "The horizon everyone's racing toward and no one agrees on. Tracking the milestones, the hype, the safety debates, and what artificial general intelligence would actually mean for the rest of us.",
    "ai": "The defining technology of the moment — machine learning, neural networks, large language models, and the tools reshaping every industry. News, analysis, and the questions worth asking.",
    "ask-me-anything": "Every week the most provocative reader question gets a full answer. No topic is off limits. Equal parts advice column, op-ed, and open office hours for the curious and the opinionated.",
    "automation": "Robots aren't coming for your job — they're already here. Covering the tools, workflows, and economic forces turning repetitive tasks into code, and what that displacement actually looks like.",
    "big-tech": "Apple, Google, Meta, Amazon, Microsoft — the companies that built the modern internet and now operate as de facto infrastructure. Strategy, power, policy battles, and the occasional implosion.",
    "bitcoin": "Digital gold, speculative asset, libertarian dream, or monetary revolution? Tracking Bitcoin's price, politics, adoption, and its complicated relationship with the rest of crypto.",
    "blockchain": "The ledger technology beneath crypto and beyond — smart contracts, decentralized apps, supply chain verification, and every other use case that may or may not need a blockchain to work.",
    "brain-health": "The organ running everything deserves more attention. Neuroscience meets wellness: sleep, cognitive performance, mental health, neuroplasticity, and the habits that actually move the needle.",
    "business-intelligence": "Data transformed into decisions. BI tools, dashboards, analytics stacks, and the organizational discipline of actually knowing what's happening inside your business before it's too late.",
    "challenges": "The hard problems — technical, societal, ethical — that don't have easy answers. A place to sit with difficulty, examine trade-offs, and think carefully before reaching for the obvious fix.",
    "code-no-code": "The blurring line between builders and non-builders. Low-code platforms, visual programming, AI-assisted development, and what it means when almost anyone can ship a working product.",
    "content-creation": "The craft and commerce of making things online — writing, video, audio, newsletters, social. Creator economy economics, audience building, and the tools that make or break a content operation.",
    "copyright": "Who owns an idea in the age of generative AI? Intellectual property law colliding with machine learning, remix culture, and platforms that profit from content they didn't create.",
    "creative-design": "Aesthetics with intent — UI, graphic design, branding, motion, and the creative decisions that make products feel inevitable rather than assembled. The intersection of taste and function.",
    "culture": "The ambient stuff we swim in — memes, movements, generational shifts, and the shared references that shape how we think. Tech culture, internet culture, and the culture tech is making.",
    "customs": "The inherited rules nobody voted for. Social norms, professional rituals, and the unwritten expectations that govern behavior — and the fascinating friction when they collide with new technology.",
    "cybersecurity": "The permanent arms race between attackers and defenders. Breaches, exploits, ransomware, zero-days, and the organizations trying to keep the lights on while adversaries look for the next door.",
    "data": "The raw material of the information age — how it's collected, stored, sold, regulated, and weaponized. Privacy, data rights, governance, and the pipelines moving petabytes around the planet.",
    "dear-______-letters": "Open letters to institutions, industries, technologies, and ideas that deserve a frank conversation. Part satire, part sincere — the format that lets you say the thing nobody else is saying.",
    "deeptech": "Science-forward startups building in quantum, biotech, materials science, aerospace, and climate — companies where the R&D cycle is measured in years and the upside is genuinely civilization-scale.",
    "economic-inequality": "The widening gap between those who own the systems and those who run them. How technology amplifies wealth concentration, and the policies, movements, and ideas pushing back.",
    "education": "Learning at every age and stage — from K-12 to corporate training to the informal education happening on YouTube at 2am. EdTech, pedagogy, credentialing, and what school is actually for.",
    "emerging-technology": "The stuff that's almost ready — spatial computing, brain-computer interfaces, fusion energy, synthetic biology. Early signals on technologies that will feel obvious in retrospect.",
    "entertainment-lbe": "Location-based entertainment: immersive experiences, theme parks, escape rooms, AR activations, and the physical spaces being reimagined now that the screen is no longer the only portal.",
    "entrepreneurship": "The unglamorous reality of building something from nothing — fundraising, hiring, product, pivots, and the psychological weight of being responsible for it all. Stories from the arena.",
    "ethical": "The moral weight of what we build. AI ethics, platform responsibility, design decisions with downstream consequences, and the frameworks for thinking carefully about technology's human impact.",
    "explainable-ai": "Black boxes are a liability. XAI covers the tools, methods, and regulatory pressures pushing AI systems toward interpretability — so humans can understand, audit, and trust the outputs.",
    "failing-up": "The entrepreneurial tradition of treating failure as tuition. Honest post-mortems, lessons from shutdowns, and the pattern of people who stumbled badly and built something better after.",
    "flow": "The psychology of peak performance and deep work — getting into the state where time disappears and output compounds. Attention, focus, environment design, and the conditions that make it possible.",
    "future-of-work": "What work looks like when AI handles the routine, offices are optional, and careers span five different industries. Remote work, the gig economy, automation, and the shape of Monday morning.",
    "future-trends": "Pattern recognition at scale — the weak signals, macro forces, and emerging behaviors that suggest where things are heading. Not prediction, but informed direction-finding for what comes next.",
    "generative": "The models that make things — text, images, audio, video, code, and the synthetic media they produce. Generative AI's capabilities, limits, business models, and cultural consequences.",
    "github": "Where code lives and collaboration happens. Open source projects, developer tools, copilot features, and the platform that became essential infrastructure for anyone building software.",
    "gpt": "OpenAI's flagship and the model that changed the public conversation about AI. GPT-4, ChatGPT, the API ecosystem, jailbreaks, business applications, and what the benchmark numbers actually mean.",
    "grifters": "Snake oil in a hoodie. Crypto scams, AI hype merchants, MLM-adjacent tech plays, and the recurring pattern of charismatic founders selling futures that conveniently never arrive.",
    "human-body-communication": "The signals we send without speaking — gesture, posture, biometrics, haptics, and the frontier of interfaces that read and respond to the body rather than waiting for keyboard input.",
    "human-computer-interaction": "The discipline of making technology feel human. HCI research, interface design, accessibility, conversational UI, and the long history of trying to make machines easier to talk to.",
    "innovation": "Real breakthroughs versus rebranded incrementalism. What innovation actually requires — dissent, resources, time, culture — and why most organizations say they want it but can't quite get there.",
    "internet-of-things-iot": "Billions of connected devices collecting data from the physical world — smart homes, industrial sensors, wearables, and the infrastructure questions nobody asked until the hack happened.",
    "interview": "Conversations with founders, researchers, practitioners, and contrarians. The long-form format where people say more than they would in a press release and less than they would in a memoir.",
    "language-models": "The architecture powering the AI moment — transformers, tokenization, context windows, fine-tuning, and the research papers explaining why these things work when they work.",
    "layerzero": "Cross-chain infrastructure and omnichain messaging — the plumbing connecting isolated blockchains and the controversy that came with it. The story of interoperability and its discontents.",
    "lessons-learned": "Distilled experience from people who built things, broke things, and rebuilt them smarter. The practical wisdom that only comes from having been wrong about something expensive.",
    "life-hacks": "Small interventions with outsized returns — productivity systems, habit design, tools, shortcuts, and the recurring realization that most efficiency gains come from eliminating work, not speeding it up.",
    "linkedin": "The professional internet and all its contradictions — thought leadership theater, recruiter DMs, algorithmic engagement bait, and the occasional genuine insight hiding in the feed.",
    "marketing": "Demand generation in the attention economy. Brand strategy, growth tactics, content marketing, influencer economics, and the eternal question of what actually moves people to act.",
    "misinformation": "False information spreading faster than corrections. Platform responsibility, media literacy, AI-generated fakery, and the structural incentives that make lies more shareable than truth.",
    "networking": "Building relationships that matter — the difference between collecting contacts and creating genuine professional community. In-person, digital, and the etiquette of showing up for people.",
    "neuroscience": "The brain as a system — neuroplasticity, decision-making architecture, memory consolidation, and the research illuminating why humans behave the way we do and what that means for design.",
    "newestlatest": "Hand-picked and carefully curated content in a consumed collection of noteworthy news, emerging trends, and must-read insights delivered fresh each week.",
    "nlp": "Natural language processing — the field teaching machines to read, understand, and generate human language. Named entity recognition, sentiment analysis, and the steps between syntax and meaning.",
    "open-source": "Software built in public, by anyone, for everyone. The licenses, communities, economics, and governance models that make open source work — and the corporations that complicate it.",
    "opinionated-editorials": "Takes with teeth. Strong positions on technology, culture, business, and the intersection of all three — written for people who'd rather read a point of view than another balanced take.",
    "perovskite": "The solar material promising to outperform silicon — cheaper, more flexible, and potentially more efficient. Tracking the science, the startups, and the durability problem standing in the way.",
    "personal-growth": "The long project of becoming better at being you — mindset, habits, learning systems, relationships, and the honest acknowledgment that growth is rarely linear or comfortable.",
    "philosophy": "The foundational questions applied to contemporary problems. Ethics, epistemology, consciousness, and the thinkers whose frameworks help make sense of a world moving faster than intuition.",
    "pirate-talk": "The unconventional, the subversive, the off-script. Ideas that don't fit in the approved channels — contrarian takes, creative rebellion, and thinking that refuses to stay in its lane.",
    "pre-crime": "Predictive policing, algorithmic risk scoring, and the ethics of systems that act before harm occurs. The tension between prevention and presumption of innocence in a data-rich world.",
    "privacy": "The shrinking space between you and the systems that know you. Data collection, surveillance capitalism, regulation, and the practical steps individuals and organizations can actually take.",
    "productivity": "Getting the right things done without burning out. Systems, tools, time management, prioritization, and the uncomfortable truth that most productivity problems are actually clarity problems.",
    "prompt-engineering": "The craft of talking to AI models effectively — structuring inputs, controlling outputs, chain-of-thought techniques, and the emerging discipline of getting reliable results from probabilistic systems.",
    "provenance": "Where did this come from and can you prove it? Content authenticity, digital watermarking, supply chain transparency, and the infrastructure for trusting information in an era of synthetic media.",
    "quantum": "Computing with qubits, superposition, and entanglement — and why the timelines keep slipping. Quantum advantage, error correction, cryptography implications, and what's actually shipping.",
    "regenerative": "Beyond sustainability — designing systems that restore rather than deplete. Regenerative agriculture, circular economy, biomimicry, and the businesses building net-positive into their model.",
    "renewable-energy": "The energy transition in real time — solar, wind, storage, grid modernization, and the policy, economics, and engineering questions determining how fast we actually get there.",
    "resume": "The artifact that summarizes a career and the conventions that make it harder than it should be. Hiring signals, skills gaps, portfolio thinking, and the future of credentialing.",
    "risk-reward": "The calculus of consequential decisions — venture bets, career pivots, product launches, policy choices. Framework thinking for situations where the downside is real and the upside uncertain.",
    "semiconductor": "The chips the world runs on — design, fabrication, supply chains, geopolitics, and the companies competing to build the silicon that everything else depends on.",
    "solar": "The fastest-growing energy source on earth. Panel efficiency, installation economics, utility-scale projects, rooftop adoption, and the storage question that determines when solar truly wins.",
    "sports": "Athletics as a lens on performance, business, culture, and data. The analytics revolution, athlete economics, sports tech, and the human stories that make winning and losing matter.",
    "storytelling": "The oldest technology and still the most persuasive. Narrative structure, brand storytelling, documentary craft, and the science of why a well-told story lands where data and argument fail.",
    "strategic": "Thinking in systems, second-order effects, and time horizons longer than this quarter. Competitive strategy, organizational design, and the decisions that shape everything that comes after.",
    "streaming": "The attention economy's most contested real estate — streaming wars, content economics, bundling fatigue, and the algorithmic taste machines determining what gets made and what gets buried.",
    "technology": "The broad sweep of what technology is doing to the world — tools, platforms, infrastructure, and the cultural shifts happening because of them. Curious, critical, and occasionally alarmed.",
    "timewellspent": "The week's top must-watch YouTube videos curated to earn back your screen time with something worth remembering. Quality over quantity, depth over distraction.",
    "travel": "Moving through the world with intention — destinations, logistics, the psychology of being elsewhere, and how the experience of travel changes the traveler in ways that are hard to explain at home.",
    "unsolicited-advice": "Opinions nobody asked for, delivered anyway. Practical guidance, strong suggestions, and the occasional correction offered in the spirit of genuine helpfulness rather than just being right.",
    "user-experience": "Design that serves the person using it. UX research, usability principles, accessibility, information architecture, and the gap between how designers imagine products and how people actually use them.",
    "viral-content": "What spreads and why — the mechanics of sharing, the psychology of contagion, platform amplification, and the uncomfortable truth that emotional resonance matters more than accuracy.",
    "wellness": "Health beyond the absence of illness — sleep, movement, nutrition, mental health, and the growing body of evidence about what actually sustains energy and mood over a lifetime.",
    "worthafortune": "A finely curated collection of the wonderful web we weave with a weekly roundup of the most interesting things worth your attention — links, reads, and discoveries that earned their place.",
}


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
/* FauxCRA — local faces, shared with the homepage masthead (docs/assets/fonts/) */
@font-face{font-family:'FauxCRA';src:url('assets/fonts/FauxCRA-Light.otf') format('opentype');font-weight:300;font-style:normal;font-display:swap}
@font-face{font-family:'FauxCRA';src:url('assets/fonts/FauxCRA-Regular.otf') format('opentype');font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:'FauxCRA';src:url('assets/fonts/FauxCRA-Bold.otf') format('opentype');font-weight:700;font-style:normal;font-display:swap}
@font-face{font-family:'FauxCRA Mono';src:url('assets/fonts/FauxCRA-Monospaced.otf') format('opentype');font-weight:400;font-style:normal;font-display:swap}

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
  --display: 'Libre Caslon Display', Georgia, serif;
  --sans: 'Archivo', -apple-system, BlinkMacSystemFont, sans-serif;
  --mono: 'FauxCRA Mono', 'FauxCRA', 'DM Mono', ui-monospace, 'SFMono-Regular', Consolas, monospace;
  --mono-weight: 400;

  --max-read: 680px;
  --max-wide: 1080px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html { -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }

/* Source Serif 4 — optical size 17 (editorial register) */
:where(body, .prose, .essay-deck, .lex-row-def, .lex-line-def, .def-history li, .tp-title, .term-arc-note) {
  font-optical-sizing: none;
  font-variation-settings: "opsz" 17;
}

/* DM Mono — Light 300 */
:where(.site-top-inner, .post-top-bar, .essay-eyebrow, .essay-byline,
  .nl-masthead-eyebrow, .nl-masthead-subtitle, .home-masthead-eyebrow,
  .home-masthead-sub, .section-label, .section-note, .hero-eyebrow,
  .hero-meta, .hero-cta, .essay-row-eyebrow, .post-nav, .colophon h4,
  .colophon-bottom, .post-tag, .tag-cloud a, .stat .label,
  .sidebar-block h4, .sidebar-item .edition, .archive-item .when,
  .archive-item .tag, .prose h4, .prose figcaption, .prose th,
  .prose .kg-bookmark-metadata, .lex-chip, .lex-cat-count, .lex-count,
  .tag-hero-eyebrow, .tag-hero .meta, .tag-header .eyebrow, .tag-header .meta,
  .ep-meta, .ep-actions, .podcast-hero-eyebrow, .podcast-hero-meta) {
  font-weight: var(--mono-weight);
}

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
/* Masthead nav — mirrors the homepage .mast for cross-site consistency */
.site-top {
  position: sticky; top: 0; z-index: 80;
  background: color-mix(in srgb, var(--paper) 90%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 2px solid var(--ink);
}
.site-top-inner {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 11px 24px;
  display: flex;
  align-items: center;
  gap: 24px;
}
.site-top-mark { display: inline-flex; align-items: center; }
/* legacy wordmark (orb + text) kept for any page still using it */
.site-top-wordmark {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--display); font-size: 16px; font-weight: 700;
  letter-spacing: -0.01em; color: var(--ink); white-space: nowrap;
}
.tw-orb {
  height: 30px;
  width: auto;
  flex-shrink: 0;
}
.site-top-inner { position: relative; }
/* Inline nav retired — the full-page takeover is the nav at every width.
   Left in the DOM with [hidden] so it stays out of the a11y tree (no
   duplicate nav for screen readers); the colophon covers no-JS users. */
.site-top-nav { display: none; }
/* Menu button — opens the full-page takeover at every width */
.site-top-toggle {
  display: inline-flex;
  margin-left: auto;
  align-items: center;
  gap: 0.6em;
  height: 42px;
  padding: 0 16px;
  background: transparent;
  border: 2px solid var(--ink);
  cursor: pointer;
  color: var(--ink);
  -webkit-tap-highlight-color: transparent;
  transition: border-color 0.2s ease, color 0.2s ease;
}
.site-top-toggle:hover { border-color: var(--accent); color: var(--accent); }
.site-top-toggle .ham {
  display: inline-flex; flex-direction: column; justify-content: center;
  gap: 4px; width: 18px; height: 14px;
}
.site-top-toggle .ham span {
  display: block; height: 2px; width: 100%;
  background: currentColor;
}
.site-top-toggle .mtxt {
  font-family: var(--mono); font-weight: 700; font-size: 0.7rem;
  letter-spacing: 0.14em; text-transform: uppercase;
}
.site-top-nav a {
  font-family: var(--mono);
  font-weight: 700;
  font-size: 0.76rem;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--ink-muted);
  padding-top: 4px;
  padding-bottom: 2px;
  border-bottom: 2px solid transparent;
  transition: color 0.15s;
}
.site-top-nav a:hover { color: var(--ink); }
.site-top-nav a.is-active { color: var(--accent); border-color: var(--accent); }
.site-top-sub {
  margin-left: auto;
  font-family: var(--mono);
  font-weight: 700;
  font-size: 0.68rem;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  background: var(--accent);
  color: var(--paper);
  padding: 0.6em 1.2em;
  transition: background 0.15s;
}
.site-top-sub:hover { background: var(--accent-deep); }
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
  inset: 0;
  background-image:
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='4' height='4'%3E%3Crect width='4' height='4' fill='%23fff'/%3E%3Crect x='0' y='0' width='1' height='1' fill='%23000'/%3E%3Crect x='2' y='0' width='1' height='1' fill='%23000'/%3E%3Crect x='1' y='1' width='1' height='1' fill='%23000' opacity='.45'/%3E%3Crect x='3' y='1' width='1' height='1' fill='%23000' opacity='.45'/%3E%3Crect x='0' y='2' width='1' height='1' fill='%23000'/%3E%3Crect x='2' y='2' width='1' height='1' fill='%23000'/%3E%3Crect x='1' y='3' width='1' height='1' fill='%23000' opacity='.45'/%3E%3Crect x='3' y='3' width='1' height='1' fill='%23000' opacity='.45'/%3E%3C/svg%3E"),
    var(--tag-bg);
  background-size: 8px 8px, cover;
  background-position: 0 0, center;
  background-repeat: repeat, no-repeat;
  background-blend-mode: multiply, normal;
  filter: grayscale(1) contrast(1.4) brightness(0.88);
  z-index: -2;
}
.tag-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg,
    rgba(250,248,244,0) 0%,
    rgba(250,248,244,0) 30%,
    rgba(250,248,244,.75) 65%,
    rgba(250,248,244,1) 100%);
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

/* ---------- PODCAST ---------- */
.podcast-hero {
  position: relative;
  overflow: hidden;
  border-bottom: 2px solid var(--ink);
  isolation: isolate;
  padding: 4.5rem 1.5rem 3.5rem;
}
.podcast-hero::before {
  content: '';
  position: absolute;
  inset: -8%;
  background-image: var(--pod-bg);
  background-size: cover;
  background-position: center;
  filter: blur(40px) saturate(1.2) brightness(.55);
  transform: scale(1.25);
  z-index: -2;
}
.podcast-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(26,24,20,.85) 0%, rgba(26,24,20,.7) 100%);
  z-index: -1;
}
.podcast-hero-inner {
  max-width: var(--max-wide);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 3rem;
  align-items: center;
}
.podcast-hero-art img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border: 3px solid var(--paper);
  border-radius: 8px;
  box-shadow: 0 30px 80px -20px rgba(0,0,0,.6);
  display: block;
}
.podcast-hero-copy { color: var(--paper); }
.podcast-hero-eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--accent-muted);
  margin-bottom: 14px;
}
.podcast-hero-title {
  font-family: var(--display);
  font-size: clamp(2.4rem, 5vw, 3.6rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -.02em;
  color: var(--paper);
  margin-bottom: 14px;
}
.podcast-hero-desc {
  font-family: var(--serif);
  font-size: 1.15rem;
  font-style: italic;
  line-height: 1.55;
  color: #d4d0c8;
  margin-bottom: 18px;
  max-width: 620px;
}
.podcast-hero-meta {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: #a29c91;
  margin-bottom: 20px;
}
.podcast-hero-cta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.podcast-hero-cta a {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--paper);
  border: 0.5px solid var(--accent-muted);
  padding: 10px 16px;
  border-radius: 2px;
  transition: all .2s ease;
}
.podcast-hero-cta a:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--paper);
}

.podcast-wrap {
  max-width: var(--max-wide);
  margin: 0 auto;
  padding: 3rem 24px 4rem;
}
.episode-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.episode {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 2rem;
  padding: 2rem 0;
  border-bottom: 0.5px solid var(--paper-rule);
}
.episode:first-child { border-top: 0.5px solid var(--paper-rule); }
.ep-art-col { position: relative; }
.ep-art {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border: 1px solid var(--paper-rule);
  border-radius: 4px;
  display: block;
}
.ep-body { min-width: 0; }
.ep-meta {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .14em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 8px;
}
.ep-title {
  font-family: var(--display);
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.2;
  color: var(--ink);
  margin-bottom: 10px;
  letter-spacing: -.01em;
}
.ep-summary {
  font-family: var(--sans);
  font-size: .95rem;
  line-height: 1.65;
  color: var(--ink-muted);
  margin-bottom: 16px;
}
.ep-audio {
  width: 100%;
  max-width: 100%;
  margin-bottom: 14px;
  border-radius: 4px;
}
.ep-actions {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.ep-actions a {
  color: var(--ink-muted);
  border-bottom: 0.5px solid var(--paper-rule);
  padding-bottom: 2px;
}
.ep-post-link { color: var(--accent) !important; border-color: var(--accent-muted) !important; }
.ep-actions a:hover { color: var(--accent); border-color: var(--accent); }

@media (max-width: 768px) {
  .podcast-hero { padding: 3rem 1.5rem 2.5rem; }
  .podcast-hero-inner { grid-template-columns: 1fr; gap: 2rem; text-align: center; }
  .podcast-hero-art { max-width: 220px; margin: 0 auto; }
  .podcast-hero-desc { margin: 0 auto 18px; }
  .podcast-hero-cta { justify-content: center; }
  .episode { grid-template-columns: 120px 1fr; gap: 1.2rem; padding: 1.6rem 0; }
  .ep-title { font-size: 1.2rem; }
}
@media (max-width: 480px) {
  .episode { grid-template-columns: 1fr; }
  .ep-art-col { max-width: 160px; }
}

/* ---------- RESPONSIVE ---------- */
@media (max-width: 900px) {
  .home-grid { grid-template-columns: 1fr; gap: 2rem; }
  .colophon-inner { grid-template-columns: 1fr 1fr; }
  .archive-item { grid-template-columns: 90px 1fr; }
  .archive-item .tag { grid-column: 2; justify-self: start; margin-top: 2px; }
}
/* ---------- MOBILE — tighten the menu bar ---------- */
@media (max-width: 860px) {
  .site-top-inner { padding: 10px 16px; gap: 14px; }
}
@media (max-width: 380px) {
  .site-top-toggle .mtxt { display: none; }
  .site-top-toggle { padding: 0 12px; }
}
@media (max-width: 600px) {
  body { font-size: 17px; }
  .colophon-inner { grid-template-columns: 1fr; gap: 1.4rem; }
  .colophon-bottom { flex-direction: column; }
  .colophon-sign-off { text-align: left; }
  .essay-wrap, .nl-wrap { padding-left: 1rem; padding-right: 1rem; }
  .post-nav { grid-template-columns: 1fr; }
  .post-nav .pn-next { text-align: left; }
  .home-masthead-title { letter-spacing: -.03em; }
}

/* ============================================================ */
/* LEXICON                                                      */
/* ============================================================ */
.lex-header { max-width: var(--max-wide); }
.lex-chips { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.4rem; }
.lex-chip {
  font-family: var(--mono);
  font-size: .64rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  padding: .42em .7em;
  border: 0.5px solid var(--paper-rule);
  border-radius: 2px;
  background: var(--paper);
  color: var(--ink-muted);
  display: inline-flex; align-items: center; gap: .5em;
  transition: border-color .2s ease, color .2s ease, background .2s ease;
}
.lex-chip span {
  font-size: .9em; color: var(--ink-faint);
  border-left: 0.5px solid var(--paper-rule); padding-left: .5em;
}
.lex-chip:hover { color: var(--ink); }
.lex-chip-accent:hover { border-color: var(--accent); color: var(--accent); }
.lex-chip-teal:hover   { border-color: var(--teal);   color: var(--teal); }
.lex-chip-gold:hover   { border-color: var(--gold);   color: var(--gold); }

.lex-wrap { max-width: var(--max-wide); margin: 0 auto; padding: 2.5rem 24px 4rem; }
.lex-cat { margin-bottom: 3.5rem; scroll-margin-top: 70px; }
.lex-cat-head {
  display: flex; align-items: baseline; gap: 1rem;
  border-top: 2px solid var(--ink);
  padding-top: .8rem; margin-bottom: 1.6rem;
}
.lex-cat-head h2 {
  font-family: var(--display); font-style: italic;
  font-size: 1.7rem; font-weight: 700; color: var(--ink);
}
.lex-bar-accent { border-top-color: var(--accent); }
.lex-bar-teal   { border-top-color: var(--teal); }
.lex-bar-gold   { border-top-color: var(--gold); }
.lex-cat-count {
  font-family: var(--mono); font-size: .66rem; letter-spacing: .14em;
  text-transform: uppercase; color: var(--ink-faint); margin-left: auto;
}
.lex-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.lex-row {
  display: grid;
  grid-template-columns: 1fr 130px;
  grid-template-areas: "head spark" "def spark";
  gap: .15rem 1rem;
  align-items: start;
  padding: 1.1rem 1.2rem;
  border-bottom: 0.5px solid var(--paper-rule);
  border-right: 0.5px solid var(--paper-rule);
}
.lex-grid .lex-row:nth-child(odd) { border-left: 0.5px solid var(--paper-rule); }
.lex-row:hover { background: var(--paper-warm); }
.lex-row-head { grid-area: head; display: flex; flex-direction: column; gap: .15rem; }
.lex-term {
  font-family: var(--display); font-weight: 700; font-size: 1.18rem;
  color: var(--ink); line-height: 1.15;
}
.lex-row:hover .lex-term { color: var(--accent); }
.lex-count {
  font-family: var(--mono); font-size: .6rem; letter-spacing: .1em;
  text-transform: uppercase; color: var(--ink-faint);
}
.lex-row-def {
  grid-area: def; font-family: var(--serif); font-size: .92rem;
  line-height: 1.5; color: var(--ink-muted); margin-top: .3rem;
}
.lex-row-spark { grid-area: spark; align-self: center; }
.spark { display: block; width: 100%; height: auto; opacity: .9; }

/* search + filter */
.lex-search {
  width: 100%; margin-top: 1.4rem; padding: .85rem 1rem;
  font-family: var(--mono); font-size: .8rem; letter-spacing: .02em;
  color: var(--ink); background: var(--paper);
  border: 0.5px solid var(--ink); border-radius: 2px;
}
.lex-search:focus { outline: none; border-color: var(--accent); }
.lex-search::placeholder { color: var(--ink-faint); }
.lex-noresults { font-family: var(--mono); font-size: .8rem; color: var(--ink-faint); margin-top: 1rem; }

/* core vocabulary hero */
.lex-core { margin-bottom: 3.5rem; }

/* compact category listing */
.lex-badge {
  font-family: var(--mono); font-size: .62em; color: var(--accent);
  vertical-align: super; margin-left: .35em; letter-spacing: 0;
}
.lex-lines { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.lex-line {
  display: grid; grid-template-columns: minmax(140px, 38%) 1fr; gap: 1rem;
  align-items: baseline; padding: .7rem 1.1rem;
  border-bottom: 0.5px solid var(--paper-rule); border-right: 0.5px solid var(--paper-rule);
}
.lex-lines .lex-line:nth-child(odd) { border-left: 0.5px solid var(--paper-rule); }
.lex-line:hover { background: var(--paper-warm); }
.lex-line-term { font-family: var(--display); font-weight: 700; font-size: 1.02rem; color: var(--ink); line-height: 1.2; }
.lex-line:hover .lex-line-term { color: var(--accent); }
.lex-line-def { font-family: var(--serif); font-size: .85rem; line-height: 1.45; color: var(--ink-muted); }

/* definition history */
.def-history { list-style: none; margin: 0; }
.def-history li {
  font-family: var(--serif); font-size: .95rem; line-height: 1.55; color: var(--ink-muted);
  padding: .7rem 0; border-bottom: 0.5px solid var(--paper-rule);
}
.dh-ed {
  font-family: var(--mono); font-size: .62rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--accent); margin-right: .7em;
}

.lex-soon {
  margin-top: 2rem; padding: 1.8rem 2rem;
  background: var(--paper-warm); border: 0.5px solid var(--paper-rule);
}
.lex-soon h3 {
  font-family: var(--mono); font-size: .68rem; letter-spacing: .18em;
  text-transform: uppercase; color: var(--accent); margin-bottom: .8rem;
}
.lex-soon p { font-family: var(--serif); color: var(--ink-muted); margin-bottom: .8rem; }
.lex-soon ul { margin: 0 0 0 1.2rem; }
.lex-soon li { font-family: var(--serif); color: var(--ink); margin-bottom: .5rem; line-height: 1.5; }
.lex-soon strong { color: var(--ink); }

/* ---------- TERM PAGE ---------- */
.term-page { max-width: var(--max-wide); margin: 0 auto; padding: 2.6rem 24px 1rem; }
.term-eyebrow {
  font-family: var(--mono); font-size: .68rem; letter-spacing: .18em;
  text-transform: uppercase; margin-bottom: .8rem;
}
.lex-text-accent { color: var(--accent); }
.lex-text-teal   { color: var(--teal); }
.lex-text-gold   { color: var(--gold); }
.term-title {
  font-family: var(--display); font-weight: 700; font-size: clamp(2.4rem, 6vw, 4rem);
  line-height: 1.02; letter-spacing: -.02em; color: var(--ink); margin-bottom: 1.2rem;
}
.term-def {
  font-family: var(--display); font-style: italic; font-weight: 400;
  font-size: clamp(1.3rem, 3vw, 1.7rem); line-height: 1.4;
  color: var(--ink); max-width: 820px; margin-bottom: .7rem;
}
.term-def-src {
  font-family: var(--mono); font-size: .68rem; letter-spacing: .04em;
  color: var(--ink-faint); margin-bottom: 2.2rem;
}
.term-def-src a { color: var(--ink-muted); border-bottom: 1px solid var(--paper-rule); }
.term-def-src a:hover { color: var(--accent); }
.term-def-gloss { font-style: italic; }

.term-stats {
  display: grid; grid-template-columns: repeat(4, 1fr);
  border-top: 2px solid var(--ink); border-bottom: 0.5px solid var(--paper-rule);
  margin-bottom: 3rem;
}
.term-stat { padding: 1.1rem 0; border-right: 0.5px solid var(--paper-rule); }
.term-stat:last-child { border-right: none; }
.ts-num {
  display: block; font-family: var(--display); font-weight: 700;
  font-size: 1.5rem; color: var(--ink); line-height: 1;
}
.ts-lbl {
  display: block; font-family: var(--mono); font-size: .58rem;
  letter-spacing: .14em; text-transform: uppercase; color: var(--ink-faint); margin-top: .4rem;
}

.term-section { margin-bottom: 2.8rem; }
.term-h3 {
  font-family: var(--display); font-style: italic; font-weight: 700;
  font-size: 1.4rem; color: var(--ink); margin-bottom: .5rem;
}
.term-h3-count { font-family: var(--mono); font-style: normal; font-size: .8rem; color: var(--ink-faint); }
.term-arc-note { font-family: var(--serif); color: var(--ink-muted); font-size: .95rem; margin-bottom: 1.2rem; max-width: 680px; }
.term-arc-note a { color: var(--accent); border-bottom: 1px solid var(--accent-muted); }

.bar-timeline {
  display: flex; align-items: flex-end; gap: 2px;
  height: var(--bt-h, 120px);
  border-bottom: 0.5px solid var(--ink);
  padding-bottom: 0;
}
.bt-col { display: flex; align-items: flex-end; justify-content: center; height: 100%; }
.bt-bar { width: 70%; min-height: 1px; opacity: .82; transition: opacity .15s ease; border-radius: 1px 1px 0 0; }
.bt-col:hover .bt-bar { opacity: 1; }

.term-body { display: grid; grid-template-columns: 1fr 280px; gap: 3rem; align-items: start; }
.term-posts { display: flex; flex-direction: column; }
.term-post {
  display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
  padding: .7rem 0; border-bottom: 0.5px solid var(--paper-rule);
}
.term-post:hover { color: var(--accent); }
.tp-title { font-family: var(--serif); font-size: 1rem; color: inherit; }
.tp-meta {
  font-family: var(--mono); font-size: .6rem; letter-spacing: .08em;
  text-transform: uppercase; color: var(--ink-faint); white-space: nowrap; flex-shrink: 0;
}
.term-more { font-family: var(--mono); font-size: .66rem; color: var(--ink-faint); margin-top: .8rem; letter-spacing: .1em; }
.term-side { position: sticky; top: 70px; }
.term-side-block { margin-bottom: 1.8rem; }
.term-side-block h4 {
  font-family: var(--mono); font-size: .62rem; letter-spacing: .16em;
  text-transform: uppercase; color: var(--ink-muted); margin-bottom: .7rem;
}
.term-back { font-family: var(--mono); font-size: .72rem; letter-spacing: .08em; color: var(--accent); }

@media (max-width: 820px) {
  .lex-grid { grid-template-columns: 1fr; }
  .lex-grid .lex-row { border-left: 0.5px solid var(--paper-rule); }
  .lex-lines { grid-template-columns: 1fr; }
  .lex-lines .lex-line { border-left: 0.5px solid var(--paper-rule); grid-template-columns: 1fr; gap: .2rem; }
  .term-body { grid-template-columns: 1fr; gap: 2rem; }
  .term-side { position: static; }
  .term-stats { grid-template-columns: 1fr 1fr; }
  .term-stat:nth-child(2) { border-right: none; }
  .term-stat:nth-child(1), .term-stat:nth-child(2) { border-bottom: 0.5px solid var(--paper-rule); }
}
"""


# ============================================================
# FRAGMENT BUILDERS
# ============================================================

def head_tag(title, favicon_path="assets/crystal-ball.svg"):
    fonts = (
        "https://fonts.googleapis.com/css2?"
        "family=Libre+Caslon+Display&"
        "family=Archivo:wght@400;500;600;700&"
        "family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,300;1,8..60,400&"
        "family=DM+Mono:wght@300;400;500&display=swap"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)} — {SITE_NAME}</title>
<meta name="description" content="{esc(SITE_TAGLINE)}">
<link rel="icon" type="image/svg+xml" href="{favicon_path}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<link rel="stylesheet" href="{{css_path}}">
</head>
<body>
"""


def site_top(from_dir="root"):
    from tw_theme import NAV, nav_overlay
    prefix = "" if from_dir == "root" else "../"
    orb = f'<img src="{prefix}assets/crystal-ball.svg" alt="" class="tw-orb">'
    nav_links = "\n      ".join(
        f'<a href="{prefix}{href}">{label}</a>'
        for _, label, href in NAV
    )
    return f"""
<header class="site-top">
  <div class="site-top-inner">
    <a href="{prefix}index.html" class="site-top-mark" aria-label="Token Wisdom — home">{orb}</a>
    <nav class="site-top-nav" id="site-nav" hidden>
      {nav_links}
      <a class="site-top-sub" href="https://tokenwisdom.ghost.io/subscribe">Subscribe</a>
    </nav>
    <button class="site-top-toggle" data-nav-toggle aria-label="Open menu" aria-expanded="false" aria-controls="nav-takeover">
      <span class="ham"><span></span><span></span><span></span></span>
      <span class="mtxt">Menu</span>
    </button>
  </div>
</header>
{nav_overlay(prefix)}
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
        <li><a href="{prefix}tags/index.html">All Topics</a></li>
        <li><a href="{prefix}lexicon/index.html">The Lexicon</a></li>
        <li><a href="{prefix}tags/a-closer-look.html">Essays</a></li>
        <li><a href="{prefix}tags/worthafortune.html">Newsletters</a></li>
        <li><a href="{prefix}podcast.html">Podcast</a></li>
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
    favicon = "assets/crystal-ball.svg" if from_dir == "root" else "../assets/crystal-ball.svg"
    head = head_tag(title, favicon_path=favicon).format(css_path=css_path)
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
        <span class="section-label">01</span>
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
        <span class="section-label">02</span>
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

    desc = TAG_DESCRIPTIONS.get(tag.get("slug", "")) or tag.get("description") or ""
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
    {gif_html}
    <h1>{esc(tag.get('name', ''))}</h1>
    {desc_html}
    <span class="meta">{count_label} · {esc(date_range)}</span>
  </div>
</header>
<div class="tag-list">
  <div class="tag-list-heading">All posts</div>
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
    import json as _json
    sorted_posts = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"], reverse=True,
    )
    by_year = defaultdict(list)
    for p in sorted_posts:
        by_year[p["published_at"][:4]].append(p)

    # Compact post records for JS-driven visual views: slug, title, date, tag-slugs
    posts_data = []
    tag_names = {}
    for p in sorted_posts:
        tag_slugs = []
        for t in p.get("tags", []):
            ts = t.get("slug", "")
            tn = (t.get("name", "") or "")
            if ts.startswith("hash-") or tn.startswith("#"):
                continue  # skip internal/hidden tags
            tag_slugs.append(ts)
            tag_names[ts] = tn
        posts_data.append({
            "s": p["slug"],
            "t": p.get("title", "") or "",
            "d": (p.get("published_at") or "")[:10],
            "g": tag_slugs,
        })
    posts_json = _json.dumps(posts_data, separators=(",", ":"), ensure_ascii=False)
    tagnames_json = _json.dumps(tag_names, separators=(",", ":"), ensure_ascii=False)

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

    archive_css = """
<style>
/* ── Archive Calendar & Clusters ── */
.archive-year-section { position: relative; padding-top: 1.4rem; }
.archive-year-section:first-child { padding-top: 0; }
.archive-cal-wrap {
  background: var(--paper);
  margin: 0 0 .6rem;
  padding: .5rem 0 .6rem;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--paper-rule);
}
/* Year heading folds into the sticky bar (compact, no standalone border) */
.archive-cal-wrap .archive-year {
  border-top: none;
  font-size: 1.5rem;
  margin: 0 0 .5rem;
  padding: 0;
}
.archive-cal {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
  margin-bottom: .55rem;
}
.cal-month {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 500;
  letter-spacing: .1em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 3px;
  cursor: default;
  border: 1px solid var(--paper-rule);
  color: var(--ink-faint);
  background: transparent;
  transition: background .12s, color .12s, border-color .12s;
  line-height: 1.6;
}
.cal-month.has-posts {
  color: var(--ink);
  border-color: color-mix(in srgb, var(--ink) 30%, transparent);
  cursor: pointer;
}
.cal-month.has-posts:hover,
.cal-month.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.archive-clusters {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  align-items: center;
}
.clusters-label {
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: .13em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-right: 2px;
}
.cluster-tag {
  font-family: var(--mono);
  font-size: 8px;
  font-weight: 500;
  letter-spacing: .09em;
  text-transform: uppercase;
  padding: 2px 9px;
  border-radius: 20px;
  background: transparent;
  border: 1px solid var(--paper-rule);
  color: var(--ink-muted);
  cursor: pointer;
  transition: all .12s;
  line-height: 1.7;
}
.cluster-tag:hover { border-color: var(--ink); color: var(--ink); }
.cluster-tag.active { background: var(--ink); color: var(--paper); border-color: var(--ink); }
#archive-filter-bar {
  position: sticky;
  top: 0;
  z-index: 200;
  background: var(--ink);
  color: var(--paper);
  padding: 9px 24px;
  display: none;
  align-items: center;
  gap: 10px;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .12em;
  text-transform: uppercase;
  box-shadow: 0 2px 8px rgba(0,0,0,.18);
}
#archive-filter-bar.visible { display: flex; }
#archive-filter-bar .fbar-label { opacity: .55; }
#archive-filter-bar .fbar-tag { font-weight: 600; }
#archive-filter-bar .fbar-count { opacity: .45; }
#archive-filter-bar .fbar-clear {
  margin-left: auto;
  cursor: pointer;
  opacity: .5;
  transition: opacity .12s;
  text-decoration: underline;
}
#archive-filter-bar .fbar-clear:hover { opacity: 1; }
.archive-item.arc-dimmed { opacity: .1; transition: opacity .2s; pointer-events: none; }
.archive-year-section.arc-dimmed { opacity: .15; transition: opacity .2s; pointer-events: none; }

/* ── View toggle ── */
:root {
  --cl-essay: #b5402f;
  --cl-newsletter: #c0892d;
  --cl-dear: #3f7d86;
  --cl-featured: #6b6760;
}
.archive-viewbar {
  display: flex;
  gap: 0;
  margin: 0 0 1.6rem;
  border: 1px solid var(--ink);
  border-radius: 4px;
  overflow: hidden;
  width: fit-content;
}
.archive-viewbar button {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: .12em;
  text-transform: uppercase;
  padding: 8px 16px;
  background: transparent;
  color: var(--ink-muted);
  border: none;
  border-right: 1px solid var(--paper-rule);
  cursor: pointer;
  transition: background .12s, color .12s;
}
.archive-viewbar button:last-child { border-right: none; }
.archive-viewbar button:hover { color: var(--ink); }
.archive-viewbar button.active { background: var(--ink); color: var(--paper); }
.archive-view { display: none; }
.archive-view.active { display: block; }

/* shared legend */
.arc-legend {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin: .2rem 0 1.4rem;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ink-muted);
}
.arc-legend span { display: inline-flex; align-items: center; gap: 6px; }
.arc-legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }

/* shared tooltip */
#arc-tip {
  position: fixed;
  z-index: 500;
  pointer-events: none;
  background: var(--ink);
  color: var(--paper);
  font-family: var(--mono);
  font-size: 10px;
  line-height: 1.4;
  letter-spacing: .04em;
  padding: 6px 10px;
  border-radius: 4px;
  max-width: 240px;
  opacity: 0;
  transition: opacity .1s;
  box-shadow: 0 3px 12px rgba(0,0,0,.25);
}
#arc-tip.show { opacity: 1; }
#arc-tip .tip-t { font-weight: 600; text-transform: none; letter-spacing: 0; }
#arc-tip .tip-m { opacity: .6; margin-top: 2px; }

/* ── Heatmap ── */
.heatmap-row {
  display: grid;
  grid-template-columns: 56px repeat(12, 1fr);
  gap: 4px;
  align-items: center;
  margin-bottom: 4px;
}
.heatmap-yearlabel {
  font-family: var(--display);
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--ink);
}
.heatmap-monthhdr {
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ink-faint);
  text-align: center;
}
.heatmap-cell {
  aspect-ratio: 1 / 1;
  border-radius: 3px;
  background: var(--paper-rule);
  cursor: default;
  transition: transform .1s, outline .1s;
  outline: 0 solid transparent;
}
.heatmap-cell.has {
  cursor: pointer;
}
.heatmap-cell.has:hover {
  transform: scale(1.12);
  outline: 2px solid var(--ink);
}
.heatmap-grid-header {
  display: grid;
  grid-template-columns: 56px repeat(12, 1fr);
  gap: 4px;
  margin-bottom: 8px;
}

/* ── Timeline ── */
.timeline-scroll { overflow-x: auto; padding-bottom: 12px; }
.timeline-svg { display: block; }
.timeline-dot { cursor: pointer; transition: r .1s; }
.timeline-dot:hover { stroke: var(--ink); stroke-width: 1.5; }
.timeline-axis-label {
  font-family: var(--mono);
  font-size: 10px;
  fill: var(--ink-muted);
  letter-spacing: .08em;
}
.timeline-axis-line { stroke: var(--paper-rule); stroke-width: 1; }

/* ── Bubbles ── */
.bubbles-svg { display: block; width: 100%; height: auto; }
.bubble { cursor: pointer; transition: opacity .12s; }
.bubble:hover { opacity: .82; }
.bubble-label {
  font-family: var(--mono);
  text-transform: uppercase;
  letter-spacing: .04em;
  fill: var(--paper);
  pointer-events: none;
  text-anchor: middle;
  dominant-baseline: central;
}
.bubbles-hint {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin-bottom: 1rem;
}

@media (max-width: 700px) {
  .heatmap-row, .heatmap-grid-header { grid-template-columns: 40px repeat(12, 1fr); gap: 2px; }
  .heatmap-monthhdr { font-size: 6px; }
}
</style>"""

    archive_js_template = r'''
<script>
(function () {
  const POSTS = __POSTS__;
  const TAGNAMES = __TAGNAMES__;
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  const SLUG_TAGS = {};
  POSTS.forEach(p => { SLUG_TAGS[p.s] = p.g; });

  const CLUSTERS = [
    { label: 'A Closer Look',    key: 'essay',      match: g => g.includes('a-closer-look') },
    { label: 'Pearls of Wisdom', key: 'newsletter', match: g => g.includes('worthafortune') },
    { label: 'Dear ____',        key: 'dear',       match: g => g.includes('dear-______-letters') },
    { label: 'Featured',         key: 'featured',   match: g => {
      if (!g.length) return false;
      if (g.includes('a-closer-look') || g.includes('worthafortune') || g.includes('dear-______-letters')) return false;
      return true;
    } },
  ];
  const CLUSTER_COLOR = {
    essay: 'var(--cl-essay)', newsletter: 'var(--cl-newsletter)',
    dear: 'var(--cl-dear)',   featured: 'var(--cl-featured)',
  };
  const CLUSTER_LABEL = { essay: 'A Closer Look', newsletter: 'Pearls of Wisdom', dear: 'Dear ____', featured: 'Featured' };

  function primaryCluster(g) {
    if (g.includes('a-closer-look')) return 'essay';
    if (g.includes('worthafortune')) return 'newsletter';
    if (g.includes('dear-______-letters')) return 'dear';
    return 'featured';
  }
  function esc(s) { return (s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function parseWhen(str) {
    const parts = (str || '').trim().replace(',','').split(/\s+/);
    return { month: MONTHS.indexOf(parts[0]), day: parseInt(parts[1]) };
  }
  function slugFromHref(href) { return (href || '').replace(/.*posts\//, '').replace(/\.html$/, ''); }
  function fmtMonthYear(d) { const [y,m] = d.split('-'); return MONTHS[parseInt(m)-1] + ' ' + y; }
  function fmtFull(d) { const [y,m,day] = d.split('-'); return MONTHS[parseInt(m)-1] + ' ' + parseInt(day) + ', ' + y; }

  // ── Tooltip ───────────────────────────────────────────────────────────────
  const tip = document.createElement('div');
  tip.id = 'arc-tip';
  document.body.appendChild(tip);
  function showTip(e, title, meta) {
    tip.innerHTML = '<div class="tip-t">' + esc(title) + '</div>' + (meta ? '<div class="tip-m">' + esc(meta) + '</div>' : '');
    tip.classList.add('show'); moveTip(e);
  }
  function moveTip(e) {
    let x = e.clientX + 14, y = e.clientY + 14;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    if (x + w > window.innerWidth - 8) x = e.clientX - w - 14;
    if (y + h > window.innerHeight - 8) y = e.clientY - h - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hideTip() { tip.classList.remove('show'); }

  const archiveWrap = document.querySelector('.archive-wrap');

  // ── Filter bar ────────────────────────────────────────────────────────────
  const filterBar = document.createElement('div');
  filterBar.id = 'archive-filter-bar';
  filterBar.innerHTML =
    '<span class="fbar-label">Showing</span>' +
    '<span class="fbar-tag" id="fbar-tag-name"></span>' +
    '<span class="fbar-count" id="fbar-tag-count"></span>' +
    '<span class="fbar-clear" id="fbar-clear">× clear</span>';
  if (archiveWrap) archiveWrap.prepend(filterBar);
  const fbarTagName = document.getElementById('fbar-tag-name');
  const fbarCount   = document.getElementById('fbar-tag-count');
  const fbarClear   = document.getElementById('fbar-clear');
  let activeKey = null;

  function itemTags(item) {
    const href = item.querySelector('h3 a')?.getAttribute('href') || '';
    return SLUG_TAGS[slugFromHref(href)] || [];
  }
  function applyFilter(key, matchFn, label) {
    activeKey = key;
    document.querySelectorAll('.cluster-tag').forEach(c => c.classList.remove('active'));
    const allItems    = document.querySelectorAll('.archive-item');
    const allSections = document.querySelectorAll('.archive-year-section');
    if (!key) {
      allItems.forEach(el => el.classList.remove('arc-dimmed'));
      allSections.forEach(el => el.classList.remove('arc-dimmed'));
      filterBar.classList.remove('visible');
      return;
    }
    let matchCount = 0;
    allItems.forEach(el => {
      if (matchFn(itemTags(el))) { el.classList.remove('arc-dimmed'); matchCount++; }
      else { el.classList.add('arc-dimmed'); }
    });
    allSections.forEach(section => {
      const hasMatch = [...section.querySelectorAll('.archive-item')].some(el => !el.classList.contains('arc-dimmed'));
      section.classList.toggle('arc-dimmed', !hasMatch);
    });
    fbarTagName.textContent = label;
    fbarCount.textContent   = '· ' + matchCount + ' post' + (matchCount !== 1 ? 's' : '');
    filterBar.classList.add('visible');
  }
  fbarClear.addEventListener('click', () => applyFilter(null));

  // ── View toggle ───────────────────────────────────────────────────────────
  const VIEWS = [
    { key: 'list',     label: 'List' },
    { key: 'heatmap',  label: 'Heatmap' },
    { key: 'timeline', label: 'Timeline' },
    { key: 'clusters', label: 'Clusters' },
  ];
  const viewbar = document.createElement('div');
  viewbar.className = 'archive-viewbar';
  VIEWS.forEach(v => {
    const b = document.createElement('button');
    b.textContent = v.label;
    b.dataset.view = v.key;
    if (v.key === 'list') b.classList.add('active');
    b.addEventListener('click', () => setView(v.key));
    viewbar.appendChild(b);
  });
  if (archiveWrap) archiveWrap.prepend(viewbar);

  const rendered = {};
  function setView(name) {
    document.querySelectorAll('.archive-viewbar button').forEach(b => b.classList.toggle('active', b.dataset.view === name));
    document.querySelectorAll('.archive-view').forEach(p => p.classList.toggle('active', p.id === 'view-' + name));
    if (name !== 'list') applyFilter(null);
    filterBar.style.display = name === 'list' ? '' : 'none';
    if (!rendered[name]) { renderView(name); rendered[name] = true; }
  }
  function renderView(name) {
    if (name === 'heatmap')  renderHeatmap();
    if (name === 'timeline') renderTimeline();
    if (name === 'clusters') renderClusters();
  }

  // ── LIST VIEW: per-year sticky calendars ─────────────────────────────────
  const siteTopH = (document.querySelector('.site-top')?.offsetHeight || 48) + 4;
  [...document.querySelectorAll('h2.archive-year')].forEach(h2 => {
    const year = h2.textContent.trim();
    const itemNodes = [];
    let sib = h2.nextElementSibling;
    while (sib && !sib.matches('h2.archive-year')) {
      if (sib.matches('.archive-item')) itemNodes.push(sib);
      sib = sib.nextElementSibling;
    }
    const byMonth = {};
    const monthFirstItem = new Map();
    itemNodes.forEach(item => {
      const d = parseWhen(item.querySelector('.when')?.textContent);
      if (d.month < 0) return;
      if (!byMonth[d.month]) { byMonth[d.month] = []; monthFirstItem.set(d.month, item); }
      byMonth[d.month].push(item);
    });
    const clusterCounts = {};
    CLUSTERS.forEach(c => { clusterCounts[c.key] = 0; });
    itemNodes.forEach(item => { const tags = itemTags(item); CLUSTERS.forEach(c => { if (c.match(tags)) clusterCounts[c.key]++; }); });

    // Remember where the year section belongs, then fold the heading into the sticky bar
    const sectionAnchor = document.createComment('year-' + year);
    h2.parentNode.insertBefore(sectionAnchor, h2);

    const calWrap = document.createElement('div');
    calWrap.className = 'archive-cal-wrap';
    calWrap.style.cssText = 'position:sticky;top:' + siteTopH + 'px;z-index:50;';
    calWrap.appendChild(h2);  // year heading rides inside the sticky header
    const cal = document.createElement('div');
    cal.className = 'archive-cal';
    MONTHS.forEach((name, i) => {
      const btn = document.createElement('button');
      const hasPosts = !!byMonth[i];
      btn.className = 'cal-month' + (hasPosts ? ' has-posts' : '');
      btn.textContent = name;
      if (hasPosts) {
        const n = byMonth[i].length;
        btn.title = n + ' post' + (n > 1 ? 's' : '') + ' · ' + name + ' ' + year;
        btn.addEventListener('click', () => {
          document.getElementById('y' + year + '-m' + i)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          cal.querySelectorAll('.cal-month').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          setTimeout(() => btn.classList.remove('active'), 2000);
        });
      }
      cal.appendChild(btn);
    });
    calWrap.appendChild(cal);

    const clusters = document.createElement('div');
    clusters.className = 'archive-clusters';
    const lbl = document.createElement('span');
    lbl.className = 'clusters-label';
    lbl.textContent = 'filter:';
    clusters.appendChild(lbl);
    CLUSTERS.forEach(c => {
      const count = clusterCounts[c.key];
      if (!count) return;
      const chip = document.createElement('button');
      chip.className = 'cluster-tag';
      chip.dataset.key = c.key;
      chip.textContent = c.label + ' · ' + count;
      chip.addEventListener('click', () => {
        const isActive = activeKey === c.key;
        applyFilter(isActive ? null : c.key, c.match, c.label);
        if (!isActive) document.querySelectorAll('.cluster-tag[data-key="' + c.key + '"]').forEach(el => el.classList.add('active'));
      });
      clusters.appendChild(chip);
    });
    calWrap.appendChild(clusters);

    const section = document.createElement('div');
    section.className = 'archive-year-section';
    sectionAnchor.parentNode.insertBefore(section, sectionAnchor);
    sectionAnchor.remove();
    section.appendChild(calWrap);
    const headH = calWrap.offsetHeight || (siteTopH + 60);
    itemNodes.forEach(item => {
      const d = parseWhen(item.querySelector('.when')?.textContent);
      if (d.month >= 0 && monthFirstItem.get(d.month) === item) {
        const anchor = document.createElement('div');
        anchor.id = 'y' + year + '-m' + d.month;
        anchor.style.cssText = 'scroll-margin-top:' + (siteTopH + headH + 8) + 'px;height:0;';
        section.appendChild(anchor);
      }
      section.appendChild(item);
    });
  });

  function legendHTML() {
    return '<div class="arc-legend">' + CLUSTERS.map(c =>
      '<span><i style="background:' + CLUSTER_COLOR[c.key] + '"></i>' + c.label + '</span>'
    ).join('') + '</div>';
  }

  // ── HEATMAP VIEW ──────────────────────────────────────────────────────────
  function renderHeatmap() {
    const host = document.getElementById('view-heatmap');
    // year → month → {count, clusters:{}}
    const grid = {};
    let maxCount = 0;
    POSTS.forEach(p => {
      const [y, m] = p.d.split('-');
      const mi = parseInt(m) - 1;
      grid[y] = grid[y] || {};
      grid[y][mi] = grid[y][mi] || { count: 0, cl: {} };
      grid[y][mi].count++;
      const k = primaryCluster(p.g);
      grid[y][mi].cl[k] = (grid[y][mi].cl[k] || 0) + 1;
      if (grid[y][mi].count > maxCount) maxCount = grid[y][mi].count;
    });
    const years = Object.keys(grid).sort((a, b) => b - a);

    let html = legendHTML();
    html += '<div class="heatmap-grid-header"><div></div>' +
      MONTHS.map(m => '<div class="heatmap-monthhdr">' + m[0] + '</div>').join('') + '</div>';
    years.forEach(y => {
      html += '<div class="heatmap-row"><div class="heatmap-yearlabel">' + y + '</div>';
      for (let mi = 0; mi < 12; mi++) {
        const cell = grid[y][mi];
        if (!cell) { html += '<div class="heatmap-cell"></div>'; continue; }
        const dom = Object.entries(cell.cl).sort((a, b) => b[1] - a[1])[0][0];
        const ratio = cell.count / maxCount;
        const pct = Math.round((0.25 + 0.75 * ratio) * 100);
        const bg = 'color-mix(in srgb, ' + CLUSTER_COLOR[dom] + ' ' + pct + '%, transparent)';
        html += '<div class="heatmap-cell has" style="background:' + bg + '" ' +
          'data-y="' + y + '" data-m="' + mi + '" data-n="' + cell.count + '" data-dom="' + dom + '"></div>';
      }
      html += '</div>';
    });
    host.innerHTML = html;

    host.querySelectorAll('.heatmap-cell.has').forEach(cell => {
      const y = cell.dataset.y, mi = +cell.dataset.m, n = +cell.dataset.n, dom = cell.dataset.dom;
      cell.addEventListener('mouseenter', e => showTip(e, MONTHS[mi] + ' ' + y, n + ' post' + (n !== 1 ? 's' : '') + ' · mostly ' + CLUSTER_LABEL[dom]));
      cell.addEventListener('mousemove', moveTip);
      cell.addEventListener('mouseleave', hideTip);
      cell.addEventListener('click', () => {
        hideTip();
        setView('list');
        requestAnimationFrame(() => document.getElementById('y' + y + '-m' + mi)?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      });
    });
  }

  // ── TIMELINE VIEW ─────────────────────────────────────────────────────────
  function renderTimeline() {
    const host = document.getElementById('view-timeline');
    const dated = POSTS.filter(p => /^\d{4}-\d{2}/.test(p.d));
    const ym = d => { const [y, m] = d.split('-'); return [parseInt(y), parseInt(m)]; };
    let minY = 9999, minM = 12, maxIdx = 0;
    dated.forEach(p => { const [y, m] = ym(p.d); if (y < minY || (y === minY && m < minM)) { minY = y; minM = m; } });
    const idxOf = p => { const [y, m] = ym(p.d); return (y - minY) * 12 + (m - minM); };
    const bins = {};
    dated.forEach(p => { const i = idxOf(p); (bins[i] = bins[i] || []).push(p); if (i > maxIdx) maxIdx = i; });

    const colW = 13, padL = 44, padR = 20, padT = 24;
    const maxStack = Math.max(...Object.values(bins).map(a => a.length), 1);
    const rowH = 13, baseY = padT + maxStack * rowH;
    const axisY = baseY + 8;
    const width = padL + (maxIdx + 1) * colW + padR;
    const height = axisY + 26;

    let dots = '', axis = '';
    // year gridlines + labels at each January
    for (let i = 0; i <= maxIdx; i++) {
      const y = minY + Math.floor((minM - 1 + i) / 12);
      const m = ((minM - 1 + i) % 12) + 1;
      if (m === 1 || i === 0) {
        const x = padL + i * colW + colW / 2;
        axis += '<line class="timeline-axis-line" x1="' + x + '" y1="' + padT + '" x2="' + x + '" y2="' + axisY + '"></line>';
        axis += '<text class="timeline-axis-label" x="' + x + '" y="' + (axisY + 16) + '" text-anchor="middle">' + y + '</text>';
      }
    }
    Object.entries(bins).forEach(([i, arr]) => {
      const x = padL + (+i) * colW + colW / 2;
      arr.sort((a, b) => a.d < b.d ? -1 : 1);
      arr.forEach((p, j) => {
        const cy = baseY - j * rowH;
        const k = primaryCluster(p.g);
        dots += '<circle class="timeline-dot" cx="' + x + '" cy="' + cy + '" r="4" fill="' + CLUSTER_COLOR[k] + '" ' +
          'data-s="' + p.s + '" data-t="' + esc(p.t).replace(/"/g, '&quot;') + '" data-d="' + p.d + '" data-k="' + k + '"></circle>';
      });
    });

    host.innerHTML = legendHTML() +
      '<div class="timeline-scroll"><svg class="timeline-svg" width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '">' +
      axis + dots + '</svg></div>';

    host.querySelectorAll('.timeline-dot').forEach(dot => {
      dot.addEventListener('mouseenter', e => { dot.setAttribute('r', '6'); showTip(e, dot.dataset.t, fmtFull(dot.dataset.d) + ' · ' + CLUSTER_LABEL[dot.dataset.k]); });
      dot.addEventListener('mousemove', moveTip);
      dot.addEventListener('mouseleave', () => { dot.setAttribute('r', '4'); hideTip(); });
      dot.addEventListener('click', () => { window.location.href = 'posts/' + dot.dataset.s + '.html'; });
    });
  }

  // ── CLUSTERS (BUBBLES) VIEW ───────────────────────────────────────────────
  function renderClusters() {
    const host = document.getElementById('view-clusters');
    const counts = {}, clTally = {};
    POSTS.forEach(p => {
      const k = primaryCluster(p.g);
      p.g.forEach(slug => {
        counts[slug] = (counts[slug] || 0) + 1;
        (clTally[slug] = clTally[slug] || {})[k] = (clTally[slug]?.[k] || 0) + 1;
      });
    });
    let entries = Object.entries(counts).filter(([s, c]) => c >= 2 && TAGNAMES[s]);
    entries.sort((a, b) => b[1] - a[1]);
    entries = entries.slice(0, 55);
    if (!entries.length) { host.innerHTML = '<p>No tags.</p>'; return; }

    const maxC = entries[0][1], minC = entries[entries.length - 1][1];
    const rMin = 16, rMax = 66;
    const radius = c => rMin + (rMax - rMin) * Math.sqrt((c - minC) / Math.max(1, maxC - minC));

    // spiral packing (largest first, from center)
    const placed = [];
    const gap = 3;
    entries.forEach(([slug, c]) => {
      const r = radius(c);
      let a = 0, rad = 0, x = 0, y = 0, ok = false;
      while (!ok) {
        x = rad * Math.cos(a); y = rad * Math.sin(a);
        ok = placed.every(q => Math.hypot(x - q.x, y - q.y) >= r + q.r + gap);
        if (!ok) { a += 0.4; rad += 0.7; }
        if (rad > 6000) break;
      }
      const dom = Object.entries(clTally[slug]).sort((p, q) => q[1] - p[1])[0][0];
      placed.push({ slug, c, r, x, y, dom, name: TAGNAMES[slug] });
    });

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    placed.forEach(p => { minX = Math.min(minX, p.x - p.r); minY = Math.min(minY, p.y - p.r); maxX = Math.max(maxX, p.x + p.r); maxY = Math.max(maxY, p.y + p.r); });
    const pad = 8;
    const vbW = (maxX - minX) + pad * 2, vbH = (maxY - minY) + pad * 2;

    let svg = '';
    placed.forEach(p => {
      const cx = p.x - minX + pad, cy = p.y - minY + pad;
      svg += '<g class="bubble" data-slug="' + p.slug + '" data-name="' + esc(p.name).replace(/"/g, '&quot;') + '" data-c="' + p.c + '">';
      svg += '<circle cx="' + cx + '" cy="' + cy + '" r="' + p.r + '" fill="' + CLUSTER_COLOR[p.dom] + '"></circle>';
      if (p.r >= 20) {
        const fs = Math.max(7, Math.min(p.r * 0.34, 13));
        const maxChars = Math.max(3, Math.floor(p.r / 4));
        let label = p.name.toUpperCase();
        if (label.length > maxChars) label = label.slice(0, maxChars - 1) + '…';
        svg += '<text class="bubble-label" x="' + cx + '" y="' + cy + '" style="font-size:' + fs + 'px">' + esc(label) + '</text>';
      }
      svg += '</g>';
    });

    host.innerHTML = '<div class="bubbles-hint">Each bubble is a topic · size = number of posts · click to filter the list</div>' +
      legendHTML() +
      '<svg class="bubbles-svg" viewBox="0 0 ' + vbW + ' ' + vbH + '" preserveAspectRatio="xMidYMid meet" style="max-height:72vh">' + svg + '</svg>';

    host.querySelectorAll('.bubble').forEach(b => {
      const name = b.dataset.name, c = +b.dataset.c, slug = b.dataset.slug;
      b.addEventListener('mouseenter', e => showTip(e, name, c + ' post' + (c !== 1 ? 's' : '')));
      b.addEventListener('mousemove', moveTip);
      b.addEventListener('mouseleave', hideTip);
      b.addEventListener('click', () => {
        hideTip();
        setView('list');
        applyFilter('tag:' + slug, g => g.includes(slug), name);
      });
    });
  }
})();
</script>'''
    archive_js = archive_js_template.replace("__POSTS__", posts_json).replace("__TAGNAMES__", tagnames_json)

    body = f"""
<header class="tag-header">
  <div class="eyebrow">Complete Archive</div>
  <h1>The Archive</h1>
  <p class="desc">Every post published, grouped by year. {len(sorted_posts)} posts across {len(by_year)} years.</p>
  <div class="meta">{years_span}</div>
</header>
{archive_css}
<div class="archive-wrap">
  <div id="view-list" class="archive-view active">
  {sections}
  </div>
  <div id="view-heatmap" class="archive-view"></div>
  <div id="view-timeline" class="archive-view"></div>
  <div id="view-clusters" class="archive-view"></div>
</div>
{archive_js}
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
        desc = (TAG_DESCRIPTIONS.get(t.get("slug", "")) or t.get("description") or "").strip()
        desc_html = f'<div class="desc">{esc(desc[:300])}</div>' if desc else '<div class="desc"></div>'
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
  <div class="eyebrow">Topics Index</div>
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
# PODCAST
# ============================================================

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def fetch_podcast_feed():
    """Download and cache the podcast RSS feed."""
    PODCAST_CACHE.parent.mkdir(exist_ok=True)
    try:
        print(f"Fetching podcast feed…")
        req = urllib.request.Request(PODCAST_FEED_URL, headers={"User-Agent": "TokenWisdom/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        PODCAST_CACHE.write_bytes(data)
        print(f"  Cached {len(data) // 1024}KB")
        return data
    except Exception as e:
        print(f"  [WARN] Fetch failed ({e}); using cached copy if available")
        if PODCAST_CACHE.exists():
            return PODCAST_CACHE.read_bytes()
        return None


def parse_podcast(feed_bytes):
    """Return (channel_info, [episodes])."""
    if not feed_bytes:
        return None, []
    try:
        root = ET.fromstring(feed_bytes)
    except ET.ParseError as e:
        print(f"  [WARN] Podcast feed parse error: {e}")
        return None, []

    ch = root.find("channel")
    if ch is None:
        return None, []

    def text(el, tag, ns=None):
        node = el.find(tag, NS) if ns else el.find(tag)
        return (node.text or "").strip() if node is not None and node.text else ""

    channel = {
        "title": text(ch, "title"),
        "description": text(ch, "description"),
        "summary": text(ch, "itunes:summary", NS),
        "link": text(ch, "link"),
        "image": "",
        "author": text(ch, "itunes:author", NS),
        "copyright": text(ch, "copyright"),
    }
    img_node = ch.find("image/url")
    if img_node is not None and img_node.text:
        channel["image"] = img_node.text.strip()
    itunes_img = ch.find("itunes:image", NS)
    if itunes_img is not None:
        channel["image"] = itunes_img.attrib.get("href", channel["image"])

    episodes = []
    for item in ch.findall("item"):
        title = text(item, "title")
        pub_date = text(item, "pubDate")
        duration = text(item, "itunes:duration", NS)
        summary = text(item, "itunes:summary", NS) or text(item, "description")
        # Strip HTML tags for a clean excerpt, keep full HTML separately
        html_body = text(item, "content:encoded", NS) or text(item, "description")
        plain = re.sub(r"<[^>]+>", " ", summary or "")
        plain = re.sub(r"\s+", " ", plain).strip()

        enclosure = item.find("enclosure")
        audio_url = enclosure.attrib.get("url", "") if enclosure is not None else ""
        audio_type = enclosure.attrib.get("type", "audio/mpeg") if enclosure is not None else "audio/mpeg"

        ep_img = channel["image"]
        img_node = item.find("itunes:image", NS)
        if img_node is not None:
            ep_img = img_node.attrib.get("href", ep_img)

        episode_num = text(item, "itunes:episode", NS)
        season = text(item, "itunes:season", NS)
        guid = text(item, "guid")

        # Try to parse pubDate into a datetime for formatting
        pub_dt = None
        try:
            from email.utils import parsedate_to_datetime
            pub_dt = parsedate_to_datetime(pub_date)
        except Exception:
            pass

        episodes.append({
            "title": title,
            "summary_plain": plain,
            "summary_html": html_body,
            "pub_date_raw": pub_date,
            "pub_date": pub_dt,
            "duration": duration,
            "audio_url": audio_url,
            "audio_type": audio_type,
            "image": ep_img,
            "episode_num": episode_num,
            "season": season,
            "guid": guid,
        })

    return channel, episodes


def format_duration(s):
    """Turn '38:56' or '2345' (seconds) into '38 min'."""
    if not s:
        return ""
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 3:
            h, m, _sec = parts
            total = int(h) * 60 + int(m)
            return f"{total} min"
        if len(parts) == 2:
            m, _sec = parts
            return f"{int(m)} min"
    try:
        total = int(s) // 60
        return f"{total} min" if total else ""
    except ValueError:
        return s


def episode_match_post(episode, posts):
    """Try to link an episode to the post it covers, by slug/title overlap."""
    ep_title = (episode["title"] or "").lower()
    # Strip leading "W13 •A• " style prefix
    cleaned = re.sub(r"^w\d+\s*[•\*]?\s*[ab]?\s*[•\*]?\s*", "", ep_title)
    cleaned = re.sub(r"[✨🔮🌶️]", "", cleaned)
    cleaned = re.sub(r"[^\w\s-]", "", cleaned).strip()

    best = None
    best_score = 0
    ep_tokens = set(cleaned.split())
    if not ep_tokens:
        return None
    for p in posts:
        title = (p.get("title") or "").lower()
        title = re.sub(r"[✨🔮🌶️]", "", title)
        title = re.sub(r"[^\w\s-]", "", title)
        p_tokens = set(title.split())
        if not p_tokens:
            continue
        overlap = len(ep_tokens & p_tokens)
        # Only count meaningful overlap (≥3 tokens or ≥60% of the smaller set)
        min_len = min(len(ep_tokens), len(p_tokens))
        if overlap >= 3 and overlap / max(min_len, 1) >= 0.5:
            if overlap > best_score:
                best_score = overlap
                best = p
    return best


def render_podcast_page(channel, episodes, posts, posts_count, tags_count, years_span, top_tags):
    if not channel:
        return ""

    feed_title = channel.get("title", "Podcast")
    feed_image = channel.get("image", "")
    feed_desc = (channel.get("summary") or channel.get("description") or "").strip()
    # Trim lines starting with http
    feed_desc = re.sub(r"https?://\S+", "", feed_desc).strip()

    # Episode cards
    eps_html_parts = []
    for i, ep in enumerate(episodes):
        ep_num_display = ""
        if ep.get("pub_date"):
            ep_num_display = ep["pub_date"].strftime("%b %-d, %Y").upper()
        elif ep.get("pub_date_raw"):
            ep_num_display = ep["pub_date_raw"][:16]

        duration = format_duration(ep.get("duration", ""))
        meta_bits = [b for b in [f"EP {len(episodes) - i:03d}", ep_num_display, duration] if b]
        meta_line = " · ".join(meta_bits)

        # Match to post
        matched = episode_match_post(ep, posts)
        post_link = ""
        if matched:
            post_link = f'<a class="ep-post-link" href="posts/{matched["slug"]}.html">Read the essay →</a>'

        summary = ep.get("summary_plain") or ""
        if len(summary) > 420:
            summary = summary[:420].rsplit(" ", 1)[0] + "…"

        audio_url = ep.get("audio_url", "")
        audio_block = ""
        if audio_url:
            audio_block = f"""
      <audio controls preload="none" class="ep-audio">
        <source src="{esc(audio_url)}" type="{esc(ep.get('audio_type') or 'audio/mpeg')}">
        Your browser doesn't support audio playback.
        <a href="{esc(audio_url)}">Download the MP3</a>
      </audio>"""

        image = ep.get("image") or feed_image
        img_block = ""
        if image:
            img_block = f'<img class="ep-art" src="{esc(image)}" alt="" loading="lazy">'

        eps_html_parts.append(f"""
  <article class="episode" id="ep-{esc(ep.get('guid', str(i)))[:24]}">
    <div class="ep-art-col">
      {img_block}
    </div>
    <div class="ep-body">
      <div class="ep-meta">{esc(meta_line)}</div>
      <h3 class="ep-title">{esc(ep.get('title', ''))}</h3>
      <p class="ep-summary">{esc(summary)}</p>
      {audio_block}
      <div class="ep-actions">
        {post_link}
        <a class="ep-download" href="{esc(audio_url)}" download>Download MP3 ↓</a>
      </div>
    </div>
  </article>""")

    eps_html = "\n".join(eps_html_parts)

    body = f"""
<div class="podcast-hero" style="--pod-bg: url('{esc(feed_image)}');">
  <div class="podcast-hero-inner">
    <div class="podcast-hero-art">
      <img src="{esc(feed_image)}" alt="{esc(feed_title)}">
    </div>
    <div class="podcast-hero-copy">
      <div class="podcast-hero-eyebrow">Podcast · Powered by NotebookLM</div>
      <h1 class="podcast-hero-title">{esc(feed_title)}</h1>
      <p class="podcast-hero-desc">{esc(feed_desc)}</p>
      <div class="podcast-hero-meta">{len(episodes)} Episodes · Updated weekly · Free</div>
      <div class="podcast-hero-cta">
        <a href="{esc(PODCAST_FEED_URL)}" target="_blank" rel="noopener">RSS Feed →</a>
        <a href="https://podcasts.apple.com/podcast/notebooklm-token-wisdom/id1773842822" target="_blank" rel="noopener">Apple Podcasts →</a>
        <a href="https://open.spotify.com/show/5mSXO8bJmZbaRkiL7TnXop" target="_blank" rel="noopener">Spotify →</a>
      </div>
    </div>
  </div>
</div>

<div class="podcast-wrap">
  <div class="section-header">
    <span class="section-label">All Episodes</span>
    <span class="section-title">The Feed</span>
    <span class="section-note">{len(episodes)} episodes · newest first</span>
  </div>

  <div class="episode-list">
    {eps_html}
  </div>
</div>
"""
    page = page_shell(feed_title, body, "style.css", from_dir="root")
    page += colophon(posts_count, tags_count, years_span, top_tags, from_dir="root")
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
    import tw_theme
    with open(DOCS_DIR / "style.css", "w") as f:
        f.write(CSS + tw_theme.OVERLAY_CSS)

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

    # Podcast
    print("Podcast…")
    feed_bytes = fetch_podcast_feed()
    channel, episodes = parse_podcast(feed_bytes)
    if channel:
        print(f"  {len(episodes)} episodes")
        with open(DOCS_DIR / "podcast.html", "w") as f:
            f.write(render_podcast_page(channel, episodes, posts, posts_count, tags_count, years_span, top_tags))
    else:
        print("  [WARN] Podcast page skipped (feed unavailable)")

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

    # The Lexicon — living glossary built from the corpus
    print("Lexicon…")
    import lexicon
    lex_ctx = {
        "posts_count": posts_count, "tags_count": tags_count,
        "years_span": years_span, "top_tags": top_tags,
        "now": datetime.now().strftime("%Y-%m-%d"),
    }
    lexicon.build(posts, lex_ctx, __import__("sys").modules[__name__])

    # The Corpus Report — Feltron-style quantified portrait of the corpus
    print("Corpus Report…")
    import metrics
    metrics.build(posts, {
        "posts_count": posts_count, "tags_count": tags_count,
        "years_span": years_span, "top_tags": top_tags,
    }, __import__("sys").modules[__name__])

    # Homepage (redesigned) — overrides the index.html written above.
    # Self-contained doc (own fonts/CSS) so it doesn't clash with the legacy
    # chrome the other pages still use; assets are copied into docs/assets/.
    print("Homepage (v2)…")
    assets_dir = DOCS_DIR / "assets"
    assets_dir.mkdir(exist_ok=True)
    for asset in ("crystal-ball.svg", "fortune_teller.gif"):
        src_asset = BACKUP_DIR / "images" / asset
        if src_asset.exists():
            shutil.copy(src_asset, assets_dir / asset)
    fonts_src = BACKUP_DIR / "fonts"
    fonts_dst = assets_dir / "fonts"
    fonts_dst.mkdir(exist_ok=True)
    for font in fonts_src.glob("*.otf"):
        shutil.copy(font, fonts_dst / font.name)
    import mockup_home
    mockup_home.build("index.html")

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

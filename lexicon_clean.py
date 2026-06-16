#!/usr/bin/env python3
"""Shared definition sanitizer for the Lexicon corpus.

Some glossary definitions harvested from newsletter PDFs are polluted: the
"The Less You Know" section parse bled into page furniture (YouTube/social
embeds, the essay outro, hashtag blocks, the footer) or merged an adjacent
glossary entry. This module is the single source of truth for detecting that
pollution and salvaging a clean definition.

Used in two places:
  · lexicon_sources.py / lexicon.py — at build time, so a rebuild can't
    reintroduce pollution (canonical = most-recent clean def).
  · clean_lexicon.py — to scrub the already-built data/lexicon.json in place.
"""

import re

# Phrases that only appear in page furniture / essay outro / footers — never in
# a hand-authored one-line glossary definition. A definition is truncated at the
# earliest of these (and dropped if nothing usable remains before it).
BOILERPLATE = [
    "enjoy the videos and music",
    "follow me on",
    "uploaded a video",
    "the wise one knows",
    "sign up for more token wisdom",
    "carry the torch of foresight",
    "just because jon snow",
    "embrace the pursuit of knowledge",
    "until next time",
    "this newsletter was curated",
    "100% authentic humanly chosen",
    "token wisdom ·",
    "🔮 token wisdom",
    "a glossary of",
    "the more you learn",
    "the corpus was always the crime scene",
]

# URL / handle fragments — a real glossary definition never contains a raw URL.
_URL_RX = re.compile(
    r"https?://|www\.|youtube\.com|patreon|\bx\.com/|bsky\.app|\bt\.co/|"
    r"ghost\.io|ecoticias|\.com/|\.org/|\.net/",
    re.IGNORECASE,
)
# Stray YouTube/CDN numeric IDs (7+ digits run together).
_VIDEOID_RX = re.compile(r"\b\d{7,}\b")
# A run of hashtags (the newsletter footer tag block: "#epistemology #attribution …").
_HASHTAGS_RX = re.compile(r"(?:#\w+\s*){2,}")
# A bracketed bare URL artifact, e.g. "[https://tokenwisdom.ghost.io/subscribe]".
_BRACKET_URL_RX = re.compile(r"\[\s*https?://[^\]]*\]")

# Term *names* that are themselves parse artifacts, not real glossary terms.
# (Matched case-insensitively against the normalized term name.)
ARTIFACT_NAMES = {
    "subscribe", "archive", "follow me on x", "anyone", "anyone'", "ce", "ce)",
    "latest edition", "previous edition", "next edition",
}


def is_artifact_name(name):
    """True if a term *name* is a parser artifact rather than a real term."""
    n = (name or "").strip().lower().strip(" .)('\"")
    if n in {a.strip(" .)('\"") for a in ARTIFACT_NAMES}:
        return True
    # A name that is itself a URL or starts with one.
    if _URL_RX.search(name or "") or (name or "").strip().startswith("["):
        return True
    return False


def _earliest(text, *finders):
    """Return the earliest match index among the given finders, or len(text)."""
    idxs = []
    low = text.lower()
    for f in finders:
        if callable(f):                       # regex search on original text
            m = f(text)
            if m:
                idxs.append(m.start())
        else:                                 # lowercase substring
            i = low.find(f)
            if i >= 0:
                idxs.append(i)
    return min(idxs) if idxs else len(text)


def pollution_reasons(defn):
    """Return a list of reasons a definition looks polluted ([] if clean)."""
    if not defn:
        return []
    low = defn.lower()
    reasons = []
    if _URL_RX.search(defn):
        reasons.append("url")
    if _VIDEOID_RX.search(defn):
        reasons.append("video-id")
    if _HASHTAGS_RX.search(defn):
        reasons.append("hashtags")
    for b in BOILERPLATE:
        if b in low:
            reasons.append(f"boiler:{b}")
            break
    return reasons


def is_polluted(defn):
    return bool(pollution_reasons(defn))


def sanitize(defn):
    """Salvage a clean definition from a (possibly polluted) one.

    Truncate at the earliest pollution boundary; drop bracketed-URL artifacts.
    Returns the cleaned text, or "" if nothing usable remains. The caller
    decides whether "" means "fall back to an earlier clean def / manual def".
    """
    if not defn:
        return ""
    text = _BRACKET_URL_RX.sub("", defn).strip()
    if not text:
        return ""
    cut = _earliest(
        text,
        _URL_RX.search,
        _VIDEOID_RX.search,
        _HASHTAGS_RX.search,
        *BOILERPLATE,
    )
    salvaged = text[:cut].strip()
    # Trim trailing fragments left dangling by the cut (stray separators, a
    # half-started clause ending in a conjunction/preposition).
    salvaged = re.sub(r"[\s\-—–:,;]+$", "", salvaged).strip()
    salvaged = re.sub(r"\s+", " ", salvaged)
    # A salvage shorter than a few words isn't a usable definition.
    if len(salvaged) < 12 or len(salvaged.split()) < 2:
        return ""
    return salvaged


# Hand-written replacements for terms whose polluted definition cannot be
# cleanly salvaged by truncation (garbled PDF text, mid-sentence run-ons, or a
# real def buried under an essay pull-quote). Keyed by slug. Used by the
# one-time data scrub; the build-time path relies on sanitize()/pick_clean().
MANUAL_DEFS = {
    "technology":
        "The applied tools, systems, and infrastructure through which "
        "scientific knowledge is put to practical use.",
    "darcy-s-law":
        "A 19th-century law of fluid dynamics describing the rate at which a "
        "fluid flows through a porous medium.",
    "skybrator":
        "A bladeless wind turbine that generates power by vibrating rather "
        "than spinning.",
    "lifi":
        "Wireless communication technology that transmits data using visible "
        "light (Light Fidelity).",
    "multi-core-fiber":
        "Optical fiber carrying several independent light paths (cores) in a "
        "single strand to multiply transmission capacity.",
    "gamma-beta-oscillations-neuroscience":
        "Rhythmic electrical oscillations in the brain — gamma (30–100 Hz) and "
        "beta (13–30 Hz) — associated with attention, awareness, and "
        "consciousness-related states across species.",
    "charles-taylor":
        "Philosopher, author of Sources of the Self; cited on the historicity "
        "of the inward self.",
    "moncrieff-et-al-2022":
        "The umbrella review in Molecular Psychiatry that found no consistent "
        "evidence of an association between serotonin and depression — the "
        "inflection point for the collapse of the serotonin hypothesis.",
    "four-step-playbook":
        "The dispossession sequence identified in the essay: (1) frame the "
        "human cost as a problem the technology will solve, (2) introduce the "
        "technology as augmentation, (3) capture the value upstream while the "
        "practitioner appears in the marketing, (4) extract the practitioner "
        "from the equation.",
    "w17-acl-157":
        "No Heir. No Lesson — the A Closer Look essay that mapped the "
        "compression of three-state inheritance (past/present/future) into "
        "two-state input/output.",
}


def pick_clean(history, fallback=""):
    """Most-recent definition-history entry that survives sanitization.

    `history` is a list of {"text": ...} dicts in chronological order.
    Returns the sanitized text of the latest clean entry, else `fallback`.
    """
    for h in reversed(history or []):
        s = sanitize(h.get("text", ""))
        if s:
            return s
    return fallback

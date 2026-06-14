# Token Wisdom — Design System

The **hybrid**: IEEE Spectrum *bones* (structural clarity, kicker-driven hierarchy,
metadata discipline, whitespace, data-forward authority) with Token Wisdom *soul*
(a warm signature accent, a serif for long-form reading, a mono technical voice).
Goal: reads as a technical journal of record, never as a generic tech-news clone.

## Color — strategy: Restrained, cool neutrals + one warm signature accent

Tinted neutrals (never `#000`/`#fff`), OKLCH, chroma falling off near the extremes.
The accent is the *soul* — Token Wisdom's burnt orange, kept from the old system so
the brand survives the shift. No institutional blue (that's the clone trap).

```
--bg:          oklch(0.992 0.004 70);   /* near-white, a hair warm — cleaner than the old cream */
--surface:     oklch(0.975 0.005 70);   /* sectioned/inset areas, card fills */
--surface-ink: oklch(0.205 0.012 65);   /* inverted blocks (footer, marquee) */
--ink:         oklch(0.235 0.012 60);   /* primary text — warm charcoal */
--ink-muted:   oklch(0.505 0.012 60);   /* deks, meta */
--ink-faint:   oklch(0.66  0.010 60);   /* timestamps, faint labels */
--rule:        oklch(0.905 0.006 70);   /* hairlines */
--rule-strong: oklch(0.235 0.012 60);   /* the 2px black section rule (Spectrum signature) */

--accent:      oklch(0.585 0.155 47);   /* TW burnt orange — kickers, links, emphasis */
--accent-deep: oklch(0.475 0.140 44);   /* hover */
--accent-wash: oklch(0.95  0.030 60);   /* tint behind active chips */

--teal:        oklch(0.520 0.070 195);  /* lexicon category */
--gold:        oklch(0.700 0.095 85);   /* lexicon category */
```

Accent stays ≤10% of any surface (Restrained). The 2px black rule + mono kickers do
the structural work; orange is for signal, not decoration.

## Typography

Three voices, each with a job. The shift from the old system: **Playfair Display
(literary serif) is retired**; headlines move to a journalistic grotesque sans.

```
--sans:  'Libre Franklin', -apple-system, BlinkMacSystemFont, sans-serif; /* headlines, UI, cards */
--serif: 'Source Serif 4', Georgia, serif;   /* long-form essay body only — the reading voice */
--mono:  'DM Mono', ui-monospace, monospace; /* kickers, metadata, labels — the technical voice */
```

- **Headlines & decks:** Libre Franklin, 600–800 weight, tight tracking on large sizes.
- **Kickers:** DM Mono, uppercase, 0.14em tracking, 0.7rem, accent or ink-muted.
- **Metadata line:** DM Mono, 0.68rem, ink-faint — `BYLINE · 8 MIN · MAR 31, 2026`.
- **Essay body:** Source Serif 4, 19px/1.7, max 70ch. Sans everywhere else.
- Scale (≥1.25): 0.7 · 0.78 · 0.88 · 1 · 1.25 · 1.6 · 2.1 · 2.9 · 4.0 rem. Hierarchy via scale + weight, not color.

## Layout

- Widths: `--w-wide: 1200px` (grids), `--w-read: 680px` (essay column), `--w-text: 70ch`.
- Spacing scale (rem): 0.25 0.5 0.75 1 1.5 2 3 4 6. Vary it for rhythm; no uniform padding.
- **Spectrum signatures:** the 2px black section rule with a mono label above each
  block; kicker → headline → dek → meta stack; 16:9 or 3:2 lead images.
- **Cards, used with restraint (not the lazy grid):** one large lead story, then a
  *varied* mix — a 2-up of medium cards, a dense list-row column, a topic rail. Never
  one monotonous same-size grid (that's the AI-slop tell). No nested cards. No
  side-stripe borders — use the full hairline or a leading kicker instead.

## Components

- **Kicker** — mono uppercase section/category tag, optional accent.
- **Meta line** — mono `author · read-time · date`.
- **Lead story** — oversized sans headline + dek + 16:9 image + kicker + meta.
- **Story row** — compact list item: kicker, headline, meta; hairline separated.
- **Topic rail** — horizontal mono chips linking to tag pages.
- **Section rule** — 2px ink top border + mono label + count, right-aligned meta.
- **Lexicon term card** — term (sans 700) + recurrence badge + dek + sparkline.

## Motion

Subtle only. Ease-out-quart/expo, ~150–250ms. Never animate layout properties
(transform/opacity only). No bounce, no glass, no gradient text.

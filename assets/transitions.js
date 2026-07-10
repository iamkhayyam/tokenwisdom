/**
 * Token Wisdom — page transitions + bottom peek sliver.
 *
 *   #tw-peek  (fixed, bottom 0) — next-post feature image + title.
 *
 * Reveals as a locked sliver at 75% scroll and stays pinned to the bottom
 * of the viewport. No hover expand, no colophon inside the tray — the
 * colophon lives back in normal page flow.
 *
 * Click peek → sweep animation covers viewport, navigates.
 * pn-prev/pn-next and index→post links → page fade before navigating.
 * .essay-index progress bar → fades out at 95% scroll (last-5% handoff).
 */

(function () {
  'use strict';

  var PEEK_SLIM  = 52;
  var DURATION   = 400;

  /* ── CSS ──────────────────────────────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = [
    /* Page exit (pn-prev/pn-next, index links) */
    '.tw-fade-out {',
    '  opacity: 0 !important;',
    '  transform: scale(0.94) translate3d(0, -4%, 0) !important;',
    '  transition: opacity ' + DURATION + 'ms cubic-bezier(0.165,0.84,0.44,1),',
    '              transform ' + DURATION + 'ms cubic-bezier(0.165,0.84,0.44,1) !important;',
    '  pointer-events: none !important;',
    '}',

    /* Peek — locked at bottom of viewport once revealed.
       Full-viewport-width strip painted in the colophon base color so the
       side gutters match the footer visually. The image + label inside
       are centered and capped at the essay-index content slot. */
    '#tw-peek {',
    '  position: fixed;',
    '  bottom: 0;',
    '  left: 0;',
    '  right: 0;',
    '  transform: translateY(100%);',
    '  z-index: 900;',
    '  width: auto;',
    '  height: ' + PEEK_SLIM + 'px;',
    '  overflow: hidden;',
    '  cursor: pointer;',
    '  background: oklch(0.195 0.055 31);',
    '  transition: transform 520ms cubic-bezier(0.19,1,0.22,1);',
    '  will-change: transform;',
    '}',
    '#tw-peek.tw-shown {',
    '  transform: translateY(0);',
    '}',
    /* Sweep — inner image + label unconstrain to fill viewport */
    '#tw-peek.tw-peek-sweeping {',
    '  top: 0;',
    '  height: auto;',
    '  z-index: 950;',
    '  transition: none;',
    '}',

    /* Feature image — centered strip, capped to essay content width */
    '#tw-peek-bg {',
    '  position: absolute;',
    '  top: 0;',
    '  left: 50%;',
    '  transform: translateX(-50%);',
    '  width: 100%;',
    '  max-width: 1080px;',
    '  height: 100%;',
    '  object-fit: cover;',
    '  object-position: center 30%;',
    '  filter: brightness(0.5);',
    '  display: block;',
    '  margin: 0;',
    '}',
    '#tw-peek.tw-peek-sweeping #tw-peek-bg {',
    '  max-width: none;',
    '  left: 0;',
    '  transform: none;',
    '  height: 100%;',
    '}',

    '#tw-peek-label {',
    '  position: absolute;',
    '  top: 0;',
    '  bottom: 0;',
    '  left: 50%;',
    '  transform: translateX(-50%);',
    '  width: 100%;',
    '  max-width: 1080px;',
    '  display: flex;',
    '  flex-direction: row;',
    '  align-items: center;',
    '  justify-content: center;',
    '  gap: 12px;',
    '  padding: 0 1rem;',
    '  text-align: center;',
    '}',
    '#tw-peek-eyebrow {',
    '  font-family: var(--mono, monospace);',
    '  font-size: 10px;',
    '  letter-spacing: 0.14em;',
    '  text-transform: uppercase;',
    '  color: rgba(255,255,255,0.55);',
    '  flex-shrink: 0;',
    '}',
    '#tw-peek-title {',
    '  font-family: var(--sans, sans-serif);',
    '  font-size: 13px;',
    '  font-weight: 600;',
    '  color: #fff;',
    '  white-space: nowrap;',
    '  overflow: hidden;',
    '  text-overflow: ellipsis;',
    '  max-width: 560px;',
    '}',
    /* Sweep state — big centered stack when the wipe covers the viewport */
    '#tw-peek.tw-peek-sweeping #tw-peek-label {',
    '  flex-direction: column;',
    '  gap: 6px;',
    '}',
    '#tw-peek.tw-peek-sweeping #tw-peek-title {',
    '  font-size: 26px;',
    '  white-space: normal;',
    '  line-height: 1.2;',
    '}',

    /* Progress bar coordination: at 75%+ scroll, lift bar above the peek.
       At 95%+, fade it out. (last-5% handoff to the peek/colophon area) */
    '.essay-index {',
    '  transition: opacity 320ms ease, transform 320ms cubic-bezier(0.19,1,0.22,1), bottom 320ms cubic-bezier(0.19,1,0.22,1) !important;',
    '}',
    'body.tw-peek-shown .essay-index {',
    '  bottom: ' + PEEK_SLIM + 'px !important;',
    '}',
    'body.tw-progress-hidden .essay-index {',
    '  opacity: 0 !important;',
    '  pointer-events: none !important;',
    '  transform: translateY(10px) !important;',
    '}'
  ].join('\n');
  document.head.appendChild(style);

  /* ── Helpers ──────────────────────────────────────────────────────── */
  function fadeOutPage(cb) {
    document.body.classList.add('tw-fade-out');
    setTimeout(cb, DURATION);
  }

  function isSameOriginPost(href) {
    try {
      var url = new URL(href, location.href);
      return url.origin === location.origin && /\/posts\//.test(url.pathname);
    } catch (_) { return false; }
  }

  /* ── Peek (only on post pages that carry data-next-*) ────────────── */
  var body      = document.body;
  var nextHref  = body.getAttribute('data-next-href');
  var nextTitle = body.getAttribute('data-next-title');
  var nextImage = body.getAttribute('data-next-image');

  if (!nextHref || !nextTitle) {
    return; // no next post → nothing to peek at
  }

  var peek = document.createElement('div');
  peek.id = 'tw-peek';
  peek.setAttribute('role', 'link');
  peek.setAttribute('tabindex', '0');
  peek.setAttribute('aria-label', 'Read next: ' + nextTitle);

  var bg = document.createElement('img');
  bg.id = 'tw-peek-bg';
  bg.alt = '';
  if (nextImage) bg.src = nextImage;

  var lbl = document.createElement('div');
  lbl.id = 'tw-peek-label';
  lbl.innerHTML =
    '<span id="tw-peek-eyebrow">Read Next</span>' +
    '<span id="tw-peek-title">' + nextTitle.replace(/</g, '&lt;') + '</span>';

  peek.appendChild(bg);
  peek.appendChild(lbl);
  body.appendChild(peek);

  function navigate() {
    if (peek.classList.contains('tw-peek-sweeping')) return;
    peek.classList.add('tw-peek-sweeping');
    setTimeout(function () { location.href = nextHref; }, 620);
  }
  peek.addEventListener('click', navigate);
  peek.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(); }
  });

  /* ── Scroll-based reveal ─────────────────────────────────────────── */
  function update() {
    var scrollable = document.documentElement.scrollHeight - window.innerHeight;
    if (scrollable <= 0) {
      peek.classList.add('tw-shown');
      body.classList.add('tw-peek-shown', 'tw-progress-hidden');
      return;
    }
    var pct = window.scrollY / scrollable;
    if (pct >= 0.67) {
      peek.classList.add('tw-shown');
      body.classList.add('tw-peek-shown');
    } else {
      peek.classList.remove('tw-shown');
      body.classList.remove('tw-peek-shown');
    }
    if (pct >= 0.95) {
      body.classList.add('tw-progress-hidden');
    } else {
      body.classList.remove('tw-progress-hidden');
    }
  }
  window.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update);
  requestAnimationFrame(update);

  /* ── Index→post links ────────────────────────────────────────────── */
  if (!/\/posts\//.test(location.pathname)) {
    document.querySelectorAll('a[href]').forEach(function (a) {
      if (!isSameOriginPost(a.getAttribute('href'))) return;
      if (a.getAttribute('target') === '_blank') return;
      a.addEventListener('click', function (e) {
        var href = a.getAttribute('href');
        e.preventDefault();
        fadeOutPage(function () { location.href = href; });
      });
    });
  }
})();

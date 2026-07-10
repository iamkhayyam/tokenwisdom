/**
 * Token Wisdom — page transitions + bottom tray.
 *
 * The tray is one unit with two stacked parts:
 *
 *   #tw-tray  (fixed, bottom 0)
 *     #tw-peek     — next-post image (top half of unit)
 *     #tw-foot     — footer bar → colophon (bottom half of unit)
 *
 * Hover anywhere on the tray → both parts expand together.
 * Click peek → sweep animation covers viewport with the next post's image.
 * pn-prev/pn-next and index→post links get a page fade before navigation.
 */

(function () {
  'use strict';

  var PEEK_SLIM  = 52;
  var PEEK_FULL  = 260;
  var FOOT_SLIM  = 48;
  var DURATION   = 400;

  /* ── CSS ──────────────────────────────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = [
    /* Page exit (used for pn-prev/pn-next and index links) */
    '.tw-fade-out {',
    '  opacity: 0 !important;',
    '  transform: scale(0.94) translate3d(0, -4%, 0) !important;',
    '  transition: opacity ' + DURATION + 'ms cubic-bezier(0.165,0.84,0.44,1),',
    '              transform ' + DURATION + 'ms cubic-bezier(0.165,0.84,0.44,1) !important;',
    '  pointer-events: none !important;',
    '}',

    /* Tray — one docked unit, flex-column so parts stack visually.
       Hidden at rest; slides up in stages: peek at 50% scroll, foot at 95%. */
    '#tw-tray {',
    '  position: fixed;',
    '  bottom: 0;',
    '  left: 0;',
    '  right: 0;',
    '  z-index: 900;',
    '  display: flex;',
    '  flex-direction: column;',
    '  transform: translateY(100%);',
    '  will-change: transform;',
    '  transition: transform 520ms cubic-bezier(0.19, 1, 0.22, 1);',
    '}',
    '#tw-tray.tw-peek-shown {',
    '  transform: translateY(' + FOOT_SLIM + 'px);',
    '}',
    '#tw-tray.tw-foot-shown {',
    '  transform: translateY(0);',
    '}',

    /* Peek — sliver at rest, expands with tray on hover */
    '#tw-peek {',
    '  position: relative;',
    '  height: ' + PEEK_SLIM + 'px;',
    '  overflow: hidden;',
    '  cursor: pointer;',
    '  background: var(--ink, #1a1814);',
    '  will-change: height;',
    '  transition: height 520ms cubic-bezier(0.19, 1, 0.22, 1);',
    '}',
    '#tw-tray.tw-open #tw-peek {',
    '  height: ' + PEEK_FULL + 'px;',
    '}',
    /* Sweep — peek grows upward to fill the viewport */
    '#tw-peek.tw-peek-sweeping {',
    '  position: fixed;',
    '  left: 0;',
    '  right: 0;',
    '  bottom: ' + FOOT_SLIM + 'px;',
    '  top: 0;',
    '  height: auto;',
    '  z-index: 950;',
    '  transition: top 600ms ease-in-out;',
    '}',
    /* Image sits at the top of the peek at destination scale.
       Matches .essay-cover img exactly: width capped to essay-frame max
       (--max-wide 1080px minus 2.5rem gutters), height 440px, cover,
       50% 38% position. As the peek grows in height, more of the same-scale
       image reveals downward — no zoom, no rescale past the actual post. */
    '#tw-peek-bg {',
    '  position: absolute;',
    '  top: 0;',
    '  left: 50%;',
    '  transform: translateX(-50%);',
    '  width: 100%;',
    '  max-width: 100%;',
    '  height: 440px;',
    '  object-fit: cover;',
    '  object-position: 50% 38%;',
    '  filter: brightness(0.5);',
    '  display: block;',
    '  transition: max-width 520ms cubic-bezier(0.19, 1, 0.22, 1);',
    '}',
    '#tw-tray.tw-open #tw-peek-bg {',
    '  max-width: calc(var(--max-wide, 1080px) - 5rem);',
    '}',
    '@media (max-width: 720px) {',
    '  #tw-peek-bg { height: 280px; }',
    '}',
    '#tw-peek-label {',
    '  position: absolute;',
    '  inset: 0;',
    '  display: flex;',
    '  flex-direction: column;',
    '  align-items: center;',
    '  justify-content: center;',
    '  gap: 5px;',
    '  padding: 0 1.5rem;',
    '  text-align: center;',
    '}',
    '#tw-peek-eyebrow {',
    '  font-family: var(--mono, monospace);',
    '  font-size: 10px;',
    '  letter-spacing: 0.14em;',
    '  text-transform: uppercase;',
    '  color: rgba(255,255,255,0.55);',
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
    '  transition: font-size 300ms ease;',
    '}',
    '#tw-tray.tw-open #tw-peek-title {',
    '  font-size: 22px;',
    '  white-space: normal;',
    '  line-height: 1.2;',
    '}',
    '#tw-peek-cta {',
    '  font-family: var(--mono, monospace);',
    '  font-size: 10px;',
    '  letter-spacing: 0.1em;',
    '  text-transform: uppercase;',
    '  color: rgba(255,255,255,0.45);',
    '  border-bottom: 1px solid rgba(255,255,255,0.2);',
    '  padding-bottom: 1px;',
    '  opacity: 0;',
    '  transition: opacity 280ms ease 80ms;',
    '}',
    '#tw-tray.tw-open #tw-peek-cta { opacity: 1; }',

    /* Footer — bar at rest, expands with tray on hover */
    '#tw-foot {',
    '  position: relative;',
    '  overflow: hidden;',
    '  height: ' + FOOT_SLIM + 'px;',
    '  will-change: height;',
    '  transition: height 520ms cubic-bezier(0.19, 1, 0.22, 1);',
    '}',
    '#tw-tray.tw-open #tw-foot {',
    '  height: var(--tw-foot-full, 400px);',
    '}',
    '#tw-foot-bar {',
    '  position: relative;',
    '  z-index: 1;',
    '  height: ' + FOOT_SLIM + 'px;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: space-between;',
    '  padding: 0 2rem;',
    '  background: var(--ink, #1a1814);',
    '}',
    '#tw-foot-bar-mark, #tw-foot-bar-action {',
    '  font-family: var(--mono, monospace);',
    '  font-size: 10px;',
    '  letter-spacing: 0.12em;',
    '  text-transform: uppercase;',
    '}',
    '#tw-foot-bar-mark { color: rgba(255,255,255,0.45); }',
    '#tw-foot-bar-action {',
    '  color: rgba(255,255,255,0.35);',
    '  transition: color 200ms ease;',
    '}',
    '#tw-tray.tw-open #tw-foot-bar-action { color: rgba(255,255,255,0.7); }',
    '#tw-foot footer.tw-colophon {',
    '  position: relative;',
    '  margin: 0;',
    '  overflow-y: auto;',
    '}',

    /* No body padding needed — tray is hidden at rest and only reveals
       once the reader has scrolled past 50% / 95% of the page. */
    'body.has-tray { padding-bottom: 0; }',

    /* Essay-index progress bar coordination:
       - At 50%+ scroll, lift the bar above the peek sliver so both stack.
       - At 95%+ scroll, fade the bar out — the footer tray takes over. */
    '.essay-index {',
    '  transition: opacity 320ms ease, transform 320ms cubic-bezier(0.19,1,0.22,1), bottom 320ms cubic-bezier(0.19,1,0.22,1) !important;',
    '}',
    'body.tw-peek-shown .essay-index {',
    '  bottom: ' + PEEK_SLIM + 'px !important;',
    '}',
    'body.tw-foot-shown .essay-index {',
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

  /* ── Build tray ───────────────────────────────────────────────────── */
  var body      = document.body;
  var nextHref  = body.getAttribute('data-next-href');
  var nextTitle = body.getAttribute('data-next-title');
  var nextImage = body.getAttribute('data-next-image');
  var colophon  = document.querySelector('footer.tw-colophon');

  if (!colophon) return;

  colophon.parentNode.removeChild(colophon);

  var tray = document.createElement('div');
  tray.id = 'tw-tray';

  /* ── Peek (top of unit) ── */
  var peek = null;
  if (nextHref && nextTitle) {
    peek = document.createElement('div');
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
      '<span id="tw-peek-title">' + nextTitle.replace(/</g, '&lt;') + '</span>' +
      '<span id="tw-peek-cta">Open edition →</span>';

    peek.appendChild(bg);
    peek.appendChild(lbl);
    tray.appendChild(peek);

    function navigate() {
      if (peek.classList.contains('tw-peek-sweeping')) return;
      tray.classList.remove('tw-open');
      /* Sweep: peek breaks out of the tray flow and covers the viewport */
      var rect = peek.getBoundingClientRect();
      peek.style.top = rect.top + 'px';
      peek.classList.add('tw-peek-sweeping');
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { peek.style.top = '0px'; });
      });
      setTimeout(function () { location.href = nextHref; }, 620);
    }
    peek.addEventListener('click', navigate);
    peek.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(); }
    });
  }

  /* ── Footer (bottom of unit) ── */
  var foot = document.createElement('div');
  foot.id = 'tw-foot';

  var bar = document.createElement('div');
  bar.id = 'tw-foot-bar';
  bar.innerHTML =
    '<span id="tw-foot-bar-mark">🔮 Token Wisdom</span>' +
    '<span id="tw-foot-bar-action">Explore ↑</span>';

  foot.appendChild(bar);
  foot.appendChild(colophon);
  tray.appendChild(foot);
  body.appendChild(tray);

  requestAnimationFrame(function () {
    var fullH = FOOT_SLIM + colophon.offsetHeight;
    foot.style.setProperty('--tw-foot-full', fullH + 'px');
  });

  /* ── Unified hover on the whole unit (only when at least peek is shown) ── */
  tray.addEventListener('mouseenter', function () {
    if (tray.classList.contains('tw-peek-shown') || tray.classList.contains('tw-foot-shown')) {
      tray.classList.add('tw-open');
    }
  });
  tray.addEventListener('mouseleave', function (e) {
    if (!tray.contains(e.relatedTarget)) {
      tray.classList.remove('tw-open');
    }
  });

  /* ── Scroll-based reveal: peek at 50%, foot at 95% ── */
  function updateTrayVisibility() {
    var scrollable = document.documentElement.scrollHeight - window.innerHeight;
    if (scrollable <= 0) {
      tray.classList.add('tw-foot-shown');
      tray.classList.remove('tw-peek-shown');
      return;
    }
    var pct = window.scrollY / scrollable;
    if (pct >= 0.95) {
      tray.classList.remove('tw-peek-shown');
      tray.classList.add('tw-foot-shown');
      body.classList.remove('tw-peek-shown');
      body.classList.add('tw-foot-shown');
    } else if (pct >= 0.75) {
      tray.classList.remove('tw-foot-shown');
      tray.classList.add('tw-peek-shown');
      body.classList.remove('tw-foot-shown');
      body.classList.add('tw-peek-shown');
    } else {
      tray.classList.remove('tw-peek-shown');
      tray.classList.remove('tw-foot-shown');
      tray.classList.remove('tw-open');
      body.classList.remove('tw-peek-shown');
      body.classList.remove('tw-foot-shown');
    }
  }
  window.addEventListener('scroll', updateTrayVisibility, { passive: true });
  window.addEventListener('resize', updateTrayVisibility);
  requestAnimationFrame(updateTrayVisibility);

  /* ── Post-nav links ──────────────────────────────────────────────── */
  document.querySelectorAll('.pn-prev, .pn-next').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var href = a.getAttribute('href');
      if (!href || a.getAttribute('target') === '_blank') return;
      e.preventDefault();
      fadeOutPage(function () { location.href = href; });
    });
  });

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

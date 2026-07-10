/**
 * Token Wisdom — page transitions + bottom tray.
 *
 * Structure (post / interior pages):
 *
 *   #tw-tray  (fixed, bottom 0, always visible on interior pages)
 *     #tw-peek          — next-post image strip; hover to expand image
 *     #tw-foot          — slim footer bar; hover to expand full colophon
 *       #tw-foot-bar    — always-visible strip (wordmark + subscribe)
 *       footer.tw-colophon — full colophon, revealed on hover
 *
 * Hover zones are independent: peek hover ≠ footer hover.
 *
 * Page-exit transitions: .pn-prev/.pn-next and index→post links
 * fade the page out before navigating.
 */

(function () {
  'use strict';

  var PEEK_SLIM  = 52;   // px — peek sliver at rest
  var PEEK_FULL  = 260;  // px — peek when hovered
  var FOOT_SLIM  = 48;   // px — footer bar at rest
  var DURATION   = 400;  // ms

  /* ── CSS ──────────────────────────────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = [
    /* Page exit */
    '.tw-fade-out {',
    '  opacity: 0 !important;',
    '  transform: scale(0.94) translate3d(0, -4%, 0) !important;',
    '  transition: opacity ' + DURATION + 'ms cubic-bezier(0.165,0.84,0.44,1),',
    '              transform ' + DURATION + 'ms cubic-bezier(0.165,0.84,0.44,1) !important;',
    '  pointer-events: none !important;',
    '}',

    /* Tray — always docked at bottom on interior pages */
    '#tw-tray {',
    '  position: fixed;',
    '  bottom: 0;',
    '  left: 0;',
    '  right: 0;',
    '  z-index: 900;',
    '}',

    /* ── Peek strip ── */
    /* Uses top+bottom instead of height so the strip sweeps upward from the
       bottom edge of the viewport when navigating. */
    '#tw-peek {',
    '  position: fixed;',
    '  left: 0;',
    '  right: 0;',
    '  bottom: ' + FOOT_SLIM + 'px;',
    '  top: calc(100vh - ' + (FOOT_SLIM + PEEK_SLIM) + 'px);',
    '  overflow: hidden;',
    '  cursor: pointer;',
    '  z-index: 901;',
    '  transition: top 460ms cubic-bezier(0.165,0.84,0.44,1);',
    '}',
    '#tw-peek.tw-peek-open {',
    '  top: calc(100vh - ' + (FOOT_SLIM + PEEK_FULL) + 'px);',
    '}',
    '#tw-peek.tw-peek-sweeping {',
    '  top: 0;',
    '  transition: top 500ms cubic-bezier(0.165,0.84,0.44,1);',
    '}',
    '#tw-peek-bg {',
    '  position: absolute;',
    '  inset: 0;',
    '  background-size: cover;',
    '  background-position: center 30%;',
    '  filter: brightness(0.48);',
    '  transform: scale(1.05);',
    '  transition: transform 500ms ease, filter 420ms ease;',
    '}',
    '#tw-peek.tw-peek-open #tw-peek-bg,',
    '#tw-peek.tw-peek-sweeping #tw-peek-bg {',
    '  transform: scale(1);',
    '  filter: brightness(0.42);',
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
    '  transition: font-size 300ms ease, white-space 0ms;',
    '}',
    '#tw-peek.tw-peek-open #tw-peek-title {',
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
    '#tw-peek.tw-peek-open #tw-peek-cta { opacity: 1; }',

    /* ── Footer zone ── */
    '#tw-foot {',
    '  position: relative;',
    '  overflow: hidden;',
    '  height: ' + FOOT_SLIM + 'px;',
    '  transition: height 420ms cubic-bezier(0.165,0.84,0.44,1);',
    '}',
    '#tw-foot.tw-foot-open {',
    '  height: var(--tw-foot-full, 400px);',
    '}',
    /* Slim bar — always visible strip */
    '#tw-foot-bar {',
    '  position: relative;',
    '  z-index: 1;',
    '  height: ' + FOOT_SLIM + 'px;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: space-between;',
    '  padding: 0 2rem;',
    '  background: var(--ink, #1a1814);',
    '  cursor: ns-resize;',
    '}',
    '#tw-foot-bar-mark {',
    '  font-family: var(--mono, monospace);',
    '  font-size: 10px;',
    '  letter-spacing: 0.12em;',
    '  text-transform: uppercase;',
    '  color: rgba(255,255,255,0.45);',
    '}',
    '#tw-foot-bar-action {',
    '  font-family: var(--mono, monospace);',
    '  font-size: 10px;',
    '  letter-spacing: 0.12em;',
    '  text-transform: uppercase;',
    '  color: rgba(255,255,255,0.35);',
    '  transition: color 200ms ease;',
    '}',
    '#tw-foot:hover #tw-foot-bar-action { color: rgba(255,255,255,0.7); }',
    /* Colophon inside the foot zone */
    '#tw-foot footer.tw-colophon {',
    '  position: relative;',
    '  margin: 0;',
    '  overflow-y: auto;',
    '}',

    /* Body clearance */
    'body.has-tray {',
    '  padding-bottom: ' + FOOT_SLIM + 'px;',
    '}',
    'body.has-tray.has-peek {',
    '  padding-bottom: ' + (FOOT_SLIM + PEEK_SLIM) + 'px;',
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

  /* ── Peek section ── */
  var peek = null;
  if (nextHref && nextTitle) {
    peek = document.createElement('div');
    peek.id = 'tw-peek';
    peek.setAttribute('role', 'link');
    peek.setAttribute('tabindex', '0');
    peek.setAttribute('aria-label', 'Read next: ' + nextTitle);

    var bg = document.createElement('div');
    bg.id = 'tw-peek-bg';
    if (nextImage) bg.style.backgroundImage = 'url(' + nextImage + ')';

    var lbl = document.createElement('div');
    lbl.id = 'tw-peek-label';
    lbl.innerHTML =
      '<span id="tw-peek-eyebrow">Read Next</span>' +
      '<span id="tw-peek-title">' + nextTitle.replace(/</g, '&lt;') + '</span>' +
      '<span id="tw-peek-cta">Open edition →</span>';

    peek.appendChild(bg);
    peek.appendChild(lbl);
    tray.appendChild(peek);

    /* Independent hover for peek only */
    peek.addEventListener('mouseenter', function () {
      peek.classList.add('tw-peek-open');
    });
    peek.addEventListener('mouseleave', function (e) {
      if (!peek.contains(e.relatedTarget)) {
        peek.classList.remove('tw-peek-open');
      }
    });

    function navigate() {
      if (peek.classList.contains('tw-peek-sweeping')) return;
      peek.classList.remove('tw-peek-open');
      peek.classList.add('tw-peek-sweeping');
      setTimeout(function () { location.href = nextHref; }, 520);
    }
    peek.addEventListener('click', navigate);
    peek.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(); }
    });
  }

  /* ── Footer section ── */
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

  /* Measure colophon height after it's in the DOM, set CSS var */
  requestAnimationFrame(function () {
    var fullH = FOOT_SLIM + colophon.offsetHeight;
    foot.style.setProperty('--tw-foot-full', fullH + 'px');
  });

  /* Independent hover for footer only */
  foot.addEventListener('mouseenter', function () {
    foot.classList.add('tw-foot-open');
  });
  foot.addEventListener('mouseleave', function (e) {
    if (!foot.contains(e.relatedTarget)) {
      foot.classList.remove('tw-foot-open');
    }
  });

  /* Body padding */
  body.classList.add('has-tray');
  if (peek) body.classList.add('has-peek');

  /* ── Post-nav links ───────────────────────────────────────────────── */
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

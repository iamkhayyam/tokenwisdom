/* Token Wisdom — site search.
 *
 * Our own engine over our own index. No dependencies, no vendor, no key.
 * Reads docs/search/{meta,postings}.json (built by search_index.py) and drives
 * two surfaces: the ⌘K overlay on every page, and /search.html.
 *
 * Loading is progressive on purpose. meta.json (~115 KB gz) arrives first and
 * already answers term / title / tag / definition queries, so the box is live
 * almost immediately. postings.json (~285 KB gz) streams in behind it and
 * silently upgrades the same query to full essay text — the results list
 * re-renders itself when it lands. There is never a blocking spinner.
 *
 * The tokenizer here MUST match tokenize() in search_index.py. If one changes
 * and the other doesn't, body matching quietly stops working.
 */
(function () {
  'use strict';

  var STOPWORDS = new Set(('the a an and or but of to in is it its for on with as at by from that this these those ' +
    'be are was were been being will would can could should not no you your we our us they their them he she his ' +
    'her i me my have has had do does did so if then than there here what when where who how why all any both ' +
    'each more most other some such only own same too very just about into over after before up out off down ' +
    'again also one two').split(' '));

  var TOKEN_RE = /[a-z0-9][a-z0-9'\-]*/g;
  var MIN_LEN = 3;

  function tokenize(text) {
    var out = [], m;
    TOKEN_RE.lastIndex = 0;
    while ((m = TOKEN_RE.exec(String(text || '').toLowerCase()))) {
      if (m[0].length >= MIN_LEN && !STOPWORDS.has(m[0])) out.push(m[0]);
    }
    return out;
  }

  /* Query tokens keep short/stop words that full tokenize() drops — someone
   * typing "ai" or "why now" still deserves a result. We only enforce a
   * 2-char floor so a single letter doesn't scan the whole corpus. */
  function queryTokens(q) {
    var out = [], m;
    TOKEN_RE.lastIndex = 0;
    while ((m = TOKEN_RE.exec(String(q || '').toLowerCase()))) {
      if (m[0].length >= 2) out.push(m[0]);
    }
    return out;
  }

  var B36 = {};
  for (var i = 0; i < 36; i++) B36['0123456789abcdefghijklmnopqrstuvwxyz'[i]] = i;

  /* "0.1.2" -> [0,1,3]. Delta-decoded base36, matching _b36() in the builder. */
  function decodePostings(str) {
    var parts = str.split('.'), out = new Array(parts.length), prev = 0;
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i], n = 0;
      for (var j = 0; j < p.length; j++) n = n * 36 + B36[p[j]];
      prev += n;
      out[i] = prev;
    }
    return out;
  }

  // ── State ────────────────────────────────────────────────────────────────

  var S = {
    base: '',
    meta: null,        // {posts:[], terms:[]}
    postings: null,    // {t: {token: encodedString}}
    tokenList: null,   // cached Object.keys(postings.t) for prefix expansion
    metaPromise: null,
    postingsPromise: null,
    // Fired when postings land so any listening UI can re-render. A list, not
    // a slot: /search.html and the ⌘K overlay both subscribe on the same page.
    upgradeFns: [],
  };

  function fireUpgrade() {
    S.upgradeFns.forEach(function (fn) {
      try { fn(); } catch (e) { /* one bad listener shouldn't sink the rest */ }
    });
  }

  function load(base) {
    S.base = base || '';
    if (S.metaPromise) return S.metaPromise;

    S.metaPromise = fetch(S.base + 'search/meta.json')
      .then(function (r) {
        if (!r.ok) throw new Error('meta ' + r.status);
        return r.json();
      })
      .then(function (j) {
        S.meta = j;
        // Only now go after the big file — meta must win the race for the
        // first paint, and on a cold cache these would otherwise contend.
        S.postingsPromise = fetch(S.base + 'search/postings.json')
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (p) {
            if (!p) return;
            S.postings = p;
            S.tokenList = Object.keys(p.t);
            fireUpgrade();
          })
          .catch(function () { /* full-text is an enhancement, not a requirement */ });
        return j;
      });
    return S.metaPromise;
  }

  // ── Scoring ──────────────────────────────────────────────────────────────
  //
  // Weights are ordered by how much a match tells you about intent. Someone
  // typing "latent space" almost certainly wants the Lexicon entry or the
  // essay titled that — not the fourteen editions that mention it in passing.
  // So: term names and post titles dominate, body text is the long tail.

  var W = {
    termNameExact: 240, termNamePrefix: 110, termNameWord: 95, termNameSub: 45,
    termDefinition: 18, termCategory: 14,
    termPhraseExact: 160, termPhrasePrefix: 60,
    titlePhrase: 90, titleWord: 55, titlePrefix: 40,
    tag: 26, excerpt: 13, body: 8, bodyStrong: 26,
  };

  /* Popularity, logarithmic. A term the newsletter has defined 16 times should
   * beat one it defined 3 times, but not by 5×, and never enough to outrank a
   * genuine name match. Linear weighting got this wrong: an incidental word in
   * a rare term's definition used to outscore 16 editions of evidence. */
  function popularity(n) { return Math.log(1 + (n || 0)) / Math.LN2 * 14; }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  /* Word-initial match: "quant" hits "quantum" (as-you-type prefixes must
   * keep working) but "agi" no longer hits "engaging", "messaging" or
   * "imaging". Plain indexOf() treats those as real matches, which buries a
   * correct result under nonsense on any short query. Cached — these run over
   * every term and post on every keystroke. */
  var reCache = {};
  function wordRe(tok) {
    return reCache[tok] || (reCache[tok] = new RegExp('\\b' + escRe(tok), 'i'));
  }
  function hasWord(hay, tok) { return wordRe(tok).test(hay); }

  /* Expand a query token to every indexed body token it prefixes, so "agen"
   * finds agent/agents/agentic. Capped — a 2-char prefix can match thousands
   * of tokens and the tail contributes nothing but work. */
  function expand(tok) {
    if (!S.tokenList) return [];
    if (S.postings.t[tok]) {
      // Exact hit still gets prefix siblings, but the exact form leads.
      var hits = [tok];
      if (tok.length >= 4) {
        for (var i = 0; i < S.tokenList.length && hits.length < 24; i++) {
          var t = S.tokenList[i];
          if (t !== tok && t.lastIndexOf(tok, 0) === 0) hits.push(t);
        }
      }
      return hits;
    }
    if (tok.length < 3) return [];
    var out = [];
    for (var j = 0; j < S.tokenList.length && out.length < 24; j++) {
      if (S.tokenList[j].lastIndexOf(tok, 0) === 0) out.push(S.tokenList[j]);
    }
    return out;
  }

  function search(q) {
    var res = { terms: [], posts: [], full: !!S.postings, query: q };
    if (!S.meta) return res;
    var raw = String(q || '').trim().toLowerCase();
    if (raw.length < 2) return res;
    var toks = queryTokens(raw);
    if (!toks.length) return res;

    // ── Lexicon terms ──────────────────────────────────────────────────────
    var terms = S.meta.terms, tOut = [];
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i], name = t[0].toLowerCase(), def = (t[2] || '').toLowerCase();
      var cat = (t[3] || '').toLowerCase();
      var score = 0, hitAll = true;

      for (var k = 0; k < toks.length; k++) {
        var tk = toks[k], sName = 0, sCtx = 0;
        if (name === tk) sName = W.termNameExact;
        else if (name.lastIndexOf(tk, 0) === 0) sName = W.termNamePrefix;
        else if (hasWord(name, tk)) sName = W.termNameWord;
        // Mid-word substring only for longer tokens, where it's likely to be a
        // real stem rather than an accident of spelling.
        else if (tk.length >= 5 && name.indexOf(tk) > -1) sName = W.termNameSub;
        if (hasWord(def, tk)) sCtx += W.termDefinition;
        if (hasWord(cat, tk)) sCtx += W.termCategory;
        if (!sName && !sCtx) { hitAll = false; break; }
        // Name evidence supersedes context rather than stacking with it —
        // otherwise a term whose definition happens to repeat its own name
        // collects a bonus that has nothing to do with the reader's intent.
        score += sName || sCtx;
      }
      if (!hitAll || !score) continue;

      // Whole-query phrase, scored once and separately from the token loop.
      if (name === raw) score += W.termPhraseExact;
      else if (name.lastIndexOf(raw, 0) === 0) score += W.termPhrasePrefix;

      score += popularity(t[4]);
      tOut.push({ kind: 'term', name: t[0], slug: t[1], def: t[2], cat: t[3], n: t[4], score: score });
    }

    // ── Posts ──────────────────────────────────────────────────────────────
    // Body hits are gathered first so title/tag/excerpt scoring can be a
    // single pass that also decides whether every query token was satisfied.
    var bodyHits = {};    // postIdx -> query tokens present anywhere in the body
    var strongHits = {};  // postIdx -> query tokens the post is actually about
    if (S.postings) {
      for (var b = 0; b < toks.length; b++) {
        var seen = {}, seenStrong = {};
        var forms = expand(toks[b]);
        for (var f = 0; f < forms.length; f++) {
          var ids = decodePostings(S.postings.t[forms[f]]);
          for (var d = 0; d < ids.length; d++) seen[ids[d]] = 1;
          var sEnc = S.postings.s && S.postings.s[forms[f]];
          if (sEnc) {
            var sIds = decodePostings(sEnc);
            for (var e = 0; e < sIds.length; e++) seenStrong[sIds[e]] = 1;
          }
        }
        for (var id in seen) bodyHits[id] = (bodyHits[id] || 0) + 1;
        for (var sid in seenStrong) strongHits[sid] = (strongHits[sid] || 0) + 1;
      }
    }

    var posts = S.meta.posts, pOut = [];
    for (var pi = 0; pi < posts.length; pi++) {
      var p = posts[pi], title = p[0].toLowerCase();
      var exc = (p[2] || '').toLowerCase();
      var tagStr = (p[4] || []).join(' ').toLowerCase();
      var pscore = 0, ok = true;

      if (title.indexOf(raw) > -1) pscore += W.titlePhrase;

      for (var m = 0; m < toks.length; m++) {
        var qt = toks[m], sc = 0;
        if (new RegExp('\\b' + escRe(qt) + '\\b').test(title)) sc += W.titleWord;
        else if (hasWord(title, qt)) sc += W.titlePrefix;
        if (hasWord(tagStr, qt)) sc += W.tag;
        if (hasWord(exc, qt)) sc += W.excerpt;
        if (!sc && (bodyHits[pi] || 0) === 0) { ok = false; break; }
        pscore += sc;
      }
      // Every token must land somewhere — either a metadata field or the body.
      if (ok && !pscore && (bodyHits[pi] || 0) < toks.length) ok = false;
      if (!ok) continue;

      pscore += (bodyHits[pi] || 0) * W.body + (strongHits[pi] || 0) * W.bodyStrong;
      // posts[] is newest-first from the builder, so index is a free recency
      // tiebreaker — no date parsing at query time.
      pscore -= pi * 0.004;
      pOut.push({
        kind: 'post', title: p[0], slug: p[1], excerpt: p[2],
        date: p[3], tags: p[4], mins: p[5], score: pscore,
      });
    }

    var byScore = function (a, b) { return b.score - a.score; };
    res.terms = tOut.sort(byScore);
    res.posts = pOut.sort(byScore);
    return res;
  }

  // ── Rendering ────────────────────────────────────────────────────────────

  function highlight(text, toks) {
    var s = esc(text);
    if (!toks.length) return s;
    var pat = toks.map(escRe).sort(function (a, b) { return b.length - a.length; }).join('|');
    // \b so the highlight agrees with what actually matched — marking "agi"
    // inside "engaging" advertises a match the ranking didn't count.
    return s.replace(new RegExp('\\b(' + pat + ')', 'gi'), '<mark>$1</mark>');
  }

  function fmtDate(d) {
    if (!d) return '';
    var parts = d.split('-');
    var mo = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return mo[parseInt(parts[1], 10) - 1] + ' ' + parts[2].replace(/^0/, '') + ', ' + parts[0];
  }

  /* Renders the result list shared by the overlay and /search.html.
   * `limit` bounds each group; the page passes a larger one than the overlay. */
  function render(res, opts) {
    opts = opts || {};
    var base = S.base, lim = opts.limit || 8;
    var toks = queryTokens(res.query || '');
    var h = '', n = 0;

    if (res.terms.length) {
      h += '<div class="tws-group"><div class="tws-grouphead">Lexicon' +
        '<span class="tws-count">' + res.terms.length + '</span></div>';
      res.terms.slice(0, lim).forEach(function (t) {
        h += '<a class="tws-hit tws-term" data-i="' + (n++) + '" href="' + base + 'lexicon/' + esc(t.slug) + '.html">' +
          '<span class="tws-hit-main">' +
          '<span class="tws-hit-title">' + highlight(t.name, toks) + '</span>' +
          (t.def ? '<span class="tws-hit-sub">' + highlight(t.def, toks) + '</span>' : '') +
          '</span>' +
          '<span class="tws-hit-meta">' + (t.n ? t.n + '×' : '') + '</span></a>';
      });
      if (res.terms.length > lim) {
        h += '<div class="tws-more">+ ' + (res.terms.length - lim) + ' more terms</div>';
      }
      h += '</div>';
    }

    if (res.posts.length) {
      h += '<div class="tws-group"><div class="tws-grouphead">Writing' +
        '<span class="tws-count">' + res.posts.length + '</span></div>';
      res.posts.slice(0, lim).forEach(function (p) {
        h += '<a class="tws-hit tws-post" data-i="' + (n++) + '" href="' + base + 'posts/' + esc(p.slug) + '.html">' +
          '<span class="tws-hit-main">' +
          '<span class="tws-hit-title">' + highlight(p.title, toks) + '</span>' +
          (p.excerpt ? '<span class="tws-hit-sub">' + highlight(p.excerpt, toks) + '</span>' : '') +
          '</span>' +
          '<span class="tws-hit-meta">' + esc(fmtDate(p.date)) + '</span></a>';
      });
      if (res.posts.length > lim) {
        h += '<div class="tws-more">+ ' + (res.posts.length - lim) + ' more' +
          (opts.seeAllHref ? ' — <a href="' + opts.seeAllHref + '">see all results →</a>' : '') + '</div>';
      }
      h += '</div>';
    }

    if (!n) {
      h = '<div class="tws-empty"><p>No matches for <em>' + esc(res.query) + '</em>.</p>' +
        '<p class="tws-empty-hint">Try a single word, or a Lexicon term.</p></div>';
    } else if (!res.full) {
      // Honest about the state: these results are real, just not yet full-text.
      h += '<div class="tws-status">Searching titles, tags and the Lexicon — full text loading…</div>';
    }
    return { html: h, count: n };
  }

  window.TWSearch = {
    load: load, search: search, render: render,
    tokenize: tokenize, queryTokens: queryTokens,
    ready: function () { return !!S.meta; },
    full: function () { return !!S.postings; },
    onUpgrade: function (fn) {
      S.upgradeFns.push(fn);
      if (S.postings) fn();  // late subscriber — postings already here
    },
    stats: function () {
      return S.meta ? { posts: S.meta.posts.length, terms: S.meta.terms.length } : null;
    },
  };
})();

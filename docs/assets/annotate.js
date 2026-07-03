/* Token Wisdom — self-hosted community layer.
 * Highlights · private notes · public responses, anchored with W3C-style
 * text-quote + text-position selectors. Dependency-free; no bundler.
 * SOURCE FILE — copied into docs/assets/ by generate_site.py.
 *
 * Anonymous readers: highlights + private notes live in localStorage only.
 * Signed-in members: everything syncs to our own API (magic-link auth).
 */
(function () {
  "use strict";

  var API = (window.TW_API || "").replace(/\/$/, "");
  var ROOT = document.querySelector(".prose");
  if (!ROOT) return; // only post pages have a .prose body

  var SLUG = (location.pathname.split("/").pop() || "").replace(/\.html$/, "");
  var LS_TOKEN = "tw_token";
  var LS_HL = "tw_hl:" + SLUG;
  var CTX = 32; // prefix/suffix length

  var state = { me: null, highlights: [], responses: [], articleResponses: [] };

  // ── tiny DOM helpers ──────────────────────────────────────────────────────────
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "class") n.className = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];
      else if (k === "text") n.textContent = attrs[k];
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function initials(name) {
    return (name || "?").split(/\s+/).slice(0, 2).map(function (w) { return w[0] || ""; }).join("");
  }
  function fmtTime(t) {
    if (!t) return "";
    var d = new Date(t.replace(" ", "T") + (t.length <= 19 ? "Z" : ""));
    if (isNaN(d)) return "";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }

  // ── token + API ─────────────────────────────────────────────────────────────
  function token() { return localStorage.getItem(LS_TOKEN); }
  function setToken(t) { if (t) localStorage.setItem(LS_TOKEN, t); }
  function clearToken() { localStorage.removeItem(LS_TOKEN); }

  function api(path, opts) {
    if (!API) return Promise.reject(new Error("no API configured"));
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    var t = token();
    if (t) headers.Authorization = "Bearer " + t;
    return fetch(API + path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) {
      if (r.status === 204) return {};
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  }

  // ── anchoring: text nodes / offsets / selectors ───────────────────────────────
  function textNodes() {
    var out = [], w = document.createTreeWalker(ROOT, NodeFilter.SHOW_TEXT, null);
    while (w.nextNode()) out.push(w.currentNode);
    return out;
  }
  function fullText() {
    return textNodes().map(function (n) { return n.data; }).join("");
  }
  function pointToOffset(node, off) {
    var acc = 0, nodes = textNodes();
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i] === node) return acc + off;
      acc += nodes[i].data.length;
    }
    return acc;
  }
  function offsetToPoint(offset) {
    var acc = 0, nodes = textNodes();
    for (var i = 0; i < nodes.length; i++) {
      var len = nodes[i].data.length;
      if (offset <= acc + len) return { node: nodes[i], off: offset - acc };
      acc += len;
    }
    var last = nodes[nodes.length - 1];
    return last ? { node: last, off: last.data.length } : null;
  }

  function selectorFromRange(range) {
    if (!ROOT.contains(range.startContainer) || !ROOT.contains(range.endContainer)) return null;
    var start = pointToOffset(range.startContainer, range.startOffset);
    var end = pointToOffset(range.endContainer, range.endOffset);
    if (end <= start) return null;
    var text = fullText();
    return {
      exact: text.slice(start, end),
      prefix: text.slice(Math.max(0, start - CTX), start),
      suffix: text.slice(end, end + CTX),
      start: start, end: end,
    };
  }

  function commonSuffix(a, b) { var i = 0; while (i < a.length && i < b.length &&
    a[a.length - 1 - i] === b[b.length - 1 - i]) i++; return i; }
  function commonPrefix(a, b) { var i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++; return i; }

  function locate(sel) {
    var text = fullText();
    if (sel.start != null && text.slice(sel.start, sel.end) === sel.exact)
      return [sel.start, sel.end];
    if (!sel.exact) return null;
    var idx = -1, best = -1, bestScore = -2;
    while ((idx = text.indexOf(sel.exact, idx + 1)) !== -1) {
      var pre = text.slice(Math.max(0, idx - (sel.prefix || "").length), idx);
      var suf = text.slice(idx + sel.exact.length, idx + sel.exact.length + (sel.suffix || "").length);
      var score = commonSuffix(pre, sel.prefix || "") + commonPrefix(suf, sel.suffix || "");
      if (score > bestScore) { bestScore = score; best = idx; }
    }
    return best < 0 ? null : [best, best + sel.exact.length];
  }

  function rangeFromSelector(sel) {
    var span = locate(sel);
    if (!span) return null;
    var a = offsetToPoint(span[0]), b = offsetToPoint(span[1]);
    if (!a || !b) return null;
    var r = document.createRange();
    try { r.setStart(a.node, a.off); r.setEnd(b.node, b.off); } catch (e) { return null; }
    return r;
  }

  // Wrap a range in <mark>, splitting text nodes so it works across element bounds.
  function wrapRange(range, id, extraClass) {
    var nodes = [], w = document.createTreeWalker(ROOT, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        return range.intersectsNode(n) && n.data.length
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    while (w.nextNode()) nodes.push(w.currentNode);
    var marks = [];
    nodes.forEach(function (node) {
      var from = node === range.startContainer ? range.startOffset : 0;
      var to = node === range.endContainer ? range.endOffset : node.data.length;
      if (to <= from) return;
      var seg = node;
      if (from > 0) seg = node.splitText(from);
      if (to - from < seg.data.length) seg.splitText(to - from);
      var mark = el("mark", { class: "tw-hl" + (extraClass ? " " + extraClass : ""), "data-anno": id });
      seg.parentNode.insertBefore(mark, seg);
      mark.appendChild(seg);
      marks.push(mark);
    });
    return marks;
  }

  // ── highlight store (anon localStorage vs authed API) ─────────────────────────
  function authed() { return !!token(); }
  function localHls() { try { return JSON.parse(localStorage.getItem(LS_HL) || "[]"); } catch (e) { return []; } }
  function saveLocalHls(arr) { localStorage.setItem(LS_HL, JSON.stringify(arr)); }
  function uid() { return "loc-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }

  function renderAllHighlights() {
    state.highlights.forEach(function (h) {
      if (!h.anchor || document.querySelector('mark[data-anno="' + cssId(h.id) + '"]')) return;
      var r = rangeFromSelector(h.anchor);
      if (r) wrapRange(r, h.id, h.kind === "note" ? "tw-note" : "");
    });
    // public anchored responses get an underline mark
    state.responses.forEach(function (resp) {
      if (!resp.anchor || resp.parent_id) return;
      if (document.querySelector('mark[data-anno="' + cssId(resp.id) + '"]')) return;
      var r = rangeFromSelector(resp.anchor);
      if (r) wrapRange(r, resp.id, "tw-response");
    });
  }
  function cssId(id) { return String(id).replace(/"/g, '\\"'); }

  function addHighlight(sel, kind, body) {
    var rec = {
      id: uid(), kind: kind, body: body || null, privacy: "private",
      anchor: sel, created_at: new Date().toISOString(),
    };
    if (authed()) {
      return api("/posts/" + encodeURIComponent(SLUG) + "/annotations", {
        method: "POST", body: { kind: kind, body: body || null, anchor: sel },
      }).then(function (saved) {
        state.highlights.push(saved);
        var r = rangeFromSelector(sel); if (r) wrapRange(r, saved.id, kind === "note" ? "tw-note" : "");
        return saved;
      });
    }
    var arr = localHls(); arr.push(rec); saveLocalHls(arr);
    state.highlights.push(rec);
    var r = rangeFromSelector(sel); if (r) wrapRange(r, rec.id, kind === "note" ? "tw-note" : "");
    return Promise.resolve(rec);
  }

  function removeHighlight(id) {
    document.querySelectorAll('mark[data-anno="' + cssId(id) + '"]').forEach(function (m) {
      var parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m); parent.normalize();
    });
    state.highlights = state.highlights.filter(function (h) { return h.id !== id; });
    if (String(id).slice(0, 4) === "loc-" || !authed()) {
      saveLocalHls(localHls().filter(function (h) { return h.id !== id; }));
    }
    if (authed() && String(id).slice(0, 4) !== "loc-") {
      api("/annotations/" + id, { method: "DELETE" }).catch(function () {});
    }
  }

  // ── floating selection toolbar (icons + hover tooltips, Medium-style) ─────────
  var ICON = {
    highlight: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l-4 4v3h3l4-4"/><path d="M13 7l4 4"/><path d="M15 5l4 4-7 7-4-4 7-7z"/></svg>',
    respond: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7A8.5 8.5 0 0 1 12.5 3 8.38 8.38 0 0 1 21 11.5z"/></svg>',
    share: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>',
    note: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
    ask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.2 9.3a2.8 2.8 0 0 1 5.4 1c0 1.9-2.6 2.3-2.6 3.9"/><circle cx="12" cy="17.2" r="0.6" fill="currentColor" stroke="none"/></svg>',
  };
  var toolbar = el("div", { class: "tw-toolbar" }, [
    el("button", { class: "tw-tb-btn", "data-act": "highlight", "data-tip": "Highlight", "aria-label": "Highlight", html: ICON.highlight }),
    el("button", { class: "tw-tb-btn", "data-act": "respond", "data-tip": "Respond", "aria-label": "Respond", html: ICON.respond }),
    el("button", { class: "tw-tb-btn", "data-act": "ask", "data-tip": "Ask the author", "aria-label": "Ask the author", html: ICON.ask }),
    el("button", { class: "tw-tb-btn", "data-act": "share", "data-tip": "Share", "aria-label": "Share", html: ICON.share }),
    el("button", { class: "tw-tb-btn tw-divide", "data-act": "note", "data-tip": "Private note", "aria-label": "Private note", html: ICON.note }),
  ]);
  document.body.appendChild(toolbar);
  var pendingSel = null; // {selector, rectForPopover}

  function hideToolbar() { toolbar.classList.remove("is-open"); }
  function showToolbarForSelection() {
    var s = window.getSelection();
    if (!s || s.isCollapsed || s.rangeCount === 0) return hideToolbar();
    var range = s.getRangeAt(0);
    if (!ROOT.contains(range.commonAncestorContainer)) return hideToolbar();
    var sel = selectorFromRange(range);
    if (!sel || !sel.exact.trim()) return hideToolbar();
    pendingSel = { selector: sel, rect: range.getBoundingClientRect() };
    var rect = pendingSel.rect;
    toolbar.classList.add("is-open");
    var tbRect = toolbar.getBoundingClientRect();
    var top = window.scrollY + rect.top - tbRect.height - 10;
    var left = window.scrollX + rect.left + rect.width / 2 - tbRect.width / 2;
    left = Math.max(8, Math.min(left, window.scrollX + document.documentElement.clientWidth - tbRect.width - 8));
    toolbar.style.top = top + "px";
    toolbar.style.left = left + "px";
    var arrow = window.scrollX + rect.left + rect.width / 2 - left;
    toolbar.style.setProperty("--tw-arrow", arrow + "px");
  }

  toolbar.addEventListener("mousedown", function (e) { e.preventDefault(); }); // keep selection
  toolbar.addEventListener("click", function (e) {
    var btn = e.target.closest(".tw-tb-btn"); if (!btn || !pendingSel) return;
    var act = btn.dataset.act, sel = pendingSel.selector, rect = pendingSel.rect;
    hideToolbar();
    if (act === "highlight") { addHighlight(sel, "highlight").then(function () { toast("Highlighted"); }); window.getSelection().removeAllRanges(); }
    else if (act === "note") openNoteComposer(sel, rect);
    else if (act === "respond") openRespondComposer(sel, rect);
    else if (act === "ask") openAskComposer(sel, rect);
    else if (act === "share") shareQuote(sel);
  });

  document.addEventListener("selectionchange", function () {
    clearTimeout(showToolbarForSelection._t);
    showToolbarForSelection._t = setTimeout(showToolbarForSelection, 120);
  });
  window.addEventListener("scroll", hideToolbar, { passive: true });

  // ── popovers ──────────────────────────────────────────────────────────────────
  var activePop = null;
  function closePop() { if (activePop) { activePop.remove(); activePop = null; } }
  document.addEventListener("mousedown", function (e) {
    if (activePop && !activePop.contains(e.target) && !e.target.closest("mark.tw-hl")) closePop();
  });
  function placePop(pop, rect) {
    document.body.appendChild(pop);
    if (window.innerWidth <= 640) return; // CSS pins it to bottom
    var pr = pop.getBoundingClientRect();
    var top = window.scrollY + (rect ? rect.bottom + 8 : 120);
    var left = window.scrollX + (rect ? rect.left : 40);
    left = Math.max(8, Math.min(left, window.scrollX + document.documentElement.clientWidth - pr.width - 8));
    pop.style.top = top + "px"; pop.style.left = left + "px";
  }

  function openNoteComposer(sel, rect, existing) {
    closePop();
    var ta = el("textarea", { placeholder: "A private note, just for you…" });
    if (existing) ta.value = existing.body || "";
    var pop = el("div", { class: "tw-pop" }, [
      el("p", { class: "tw-kicker", text: "Private note" }),
      ta,
      el("div", { class: "tw-row" }, [
        el("span", { class: "tw-spacer" }),
        el("button", { class: "tw-btn tw-ghost", text: "Cancel", onclick: closePop }),
        el("button", { class: "tw-btn", text: "Save", onclick: function () {
          var body = ta.value.trim(); if (!body) return;
          addHighlight(sel, "note", body).then(function () { closePop(); toast("Note saved"); });
          window.getSelection().removeAllRanges();
        } }),
      ]),
    ]);
    activePop = pop; placePop(pop, rect); ta.focus();
  }

  function openRespondComposer(sel, rect) {
    closePop();
    if (!authed()) return openAuthModal(rect);
    var ta = el("textarea", { placeholder: "Respond to this passage publicly…" });
    var pop = el("div", { class: "tw-pop" }, [
      el("p", { class: "tw-kicker", text: "Respond to passage" }),
      el("blockquote", { class: "tw-quote", text: "“" + sel.exact.slice(0, 160) + (sel.exact.length > 160 ? "…" : "") + "”" }),
      ta,
      el("div", { class: "tw-row" }, [
        el("span", { class: "tw-spacer" }),
        el("button", { class: "tw-btn tw-ghost", text: "Cancel", onclick: closePop }),
        el("button", { class: "tw-btn", text: "Respond", onclick: function () {
          var body = ta.value.trim(); if (!body) return;
          api("/posts/" + encodeURIComponent(SLUG) + "/annotations", {
            method: "POST", body: { kind: "response", body: body, anchor: sel },
          }).then(function (saved) {
            closePop();
            if (saved.status === "pending") toast("Submitted — pending review");
            else { state.responses.push(saved); var r = rangeFromSelector(sel); if (r) wrapRange(r, saved.id, "tw-response"); toast("Response posted"); }
          }).catch(function (e) { toast(e.message); });
          window.getSelection().removeAllRanges();
        } }),
      ]),
    ]);
    activePop = pop; placePop(pop, rect); ta.focus();
  }

  // Ask the author a question about a highlighted passage → AMA queue.
  function openAskComposer(sel, rect) {
    closePop();
    if (!authed()) return openAuthModal(rect);
    var ta = el("textarea", { placeholder: "Ask the author a question about this passage…" });
    var pop = el("div", { class: "tw-pop" }, [
      el("p", { class: "tw-kicker", text: "Ask the author" }),
      el("blockquote", { class: "tw-quote", text: "“" + sel.exact.slice(0, 160) + (sel.exact.length > 160 ? "…" : "") + "”" }),
      ta,
      el("p", { class: "tw-muted", text: "Goes straight to @iamkhayyam — the best questions get answered in Ask Me Anything." }),
      el("div", { class: "tw-row" }, [
        el("span", { class: "tw-spacer" }),
        el("button", { class: "tw-btn tw-ghost", text: "Cancel", onclick: closePop }),
        el("button", { class: "tw-btn", text: "Ask", onclick: function () {
          var body = ta.value.trim(); if (!body) return;
          api("/posts/" + encodeURIComponent(SLUG) + "/annotations", {
            method: "POST", body: { kind: "question", body: body, anchor: sel },
          }).then(function () { closePop(); toast("Question sent to the author"); })
            .catch(function (e) { toast(e.message); });
          window.getSelection().removeAllRanges();
        } }),
      ]),
    ]);
    activePop = pop; placePop(pop, rect); ta.focus();
  }

  // click an existing highlight/note/response mark
  ROOT.addEventListener("click", function (e) {
    var mark = e.target.closest("mark.tw-hl"); if (!mark) return;
    var id = mark.dataset.anno;
    var hl = state.highlights.find(function (h) { return h.id === id; });
    var resp = state.responses.find(function (r) { return r.id === id; });
    if (hl) openHighlightPop(hl, mark);
    else if (resp) openThreadPop(resp, mark);
  });

  function openHighlightPop(hl, mark) {
    closePop();
    var rect = mark.getBoundingClientRect();
    var kids = [];
    if (hl.kind === "note" && hl.body) kids.push(el("p", { class: "tw-note-body", text: hl.body }));
    kids.push(el("div", { class: "tw-row" }, [
      el("button", { class: "tw-link", text: hl.kind === "note" ? "Edit note" : "Add note",
        onclick: function () { openNoteComposer(hl.anchor, rect, hl.kind === "note" ? hl : null); if (hl.kind !== "note") removeHighlight(hl.id); } }),
      el("button", { class: "tw-link", text: "Respond", onclick: function () { openRespondComposer(hl.anchor, rect); } }),
      el("span", { class: "tw-spacer" }),
      el("button", { class: "tw-link", text: "Remove", onclick: function () { removeHighlight(hl.id); closePop(); } }),
    ]));
    var pop = el("div", { class: "tw-pop" }, kids);
    activePop = pop; placePop(pop, rect);
  }

  function openThreadPop(resp, mark) {
    closePop();
    var rect = mark.getBoundingClientRect();
    var replies = state.responses.filter(function (r) { return r.parent_id === resp.id; });
    var kids = [el("p", { class: "tw-kicker", text: "Response" }), renderItemCard(resp, true)];
    replies.forEach(function (r) { kids.push(renderItemCard(r, true)); });
    if (authed()) kids.push(replyBox(resp.id));
    else kids.push(el("p", { class: "tw-muted", html: 'Sign in to reply. <button class="tw-link">Sign in</button>' }));
    var pop = el("div", { class: "tw-pop" }, kids);
    var signin = pop.querySelector(".tw-link"); if (signin && !authed()) signin.onclick = function () { openAuthModal(rect); };
    activePop = pop; placePop(pop, rect);
  }

  function replyBox(parentId) {
    var ta = el("textarea", { placeholder: "Reply…" });
    return el("div", { class: "tw-composer", style: "margin-top:10px" }, [ta,
      el("div", { class: "tw-row" }, [el("span", { class: "tw-spacer" }),
        el("button", { class: "tw-btn", text: "Reply", onclick: function () {
          var body = ta.value.trim(); if (!body) return;
          var payload = { kind: "article_response", body: body, parent_id: parentId };
          api("/posts/" + encodeURIComponent(SLUG) + "/annotations", { method: "POST", body: payload })
            .then(function (saved) {
              ta.value = "";
              if (saved.status === "pending") toast("Reply pending review");
              else { state.responses.push(saved); state.articleResponses.push(saved); toast("Replied"); renderResponses(); closePop(); }
            }).catch(function (e) { toast(e.message); });
        } })]),
    ]);
  }

  // ── share ─────────────────────────────────────────────────────────────────────
  function shareQuote(sel) {
    var url = location.origin + location.pathname + "#q=" + encodeURIComponent(sel.exact.slice(0, 180));
    var quote = '“' + sel.exact.slice(0, 200) + '”';
    if (navigator.share) { navigator.share({ title: document.title, text: quote, url: url }).catch(function () {}); return; }
    navigator.clipboard.writeText(quote + "\n" + url).then(function () { toast("Quote link copied"); });
    window.open("https://twitter.com/intent/tweet?text=" + encodeURIComponent(quote) + "&url=" + encodeURIComponent(url), "_blank", "noopener,width=560,height=420");
  }

  // ── responses section (bottom of article) ─────────────────────────────────────
  var section = document.getElementById("tw-responses");
  function renderItemCard(item, compact) {
    var a = item.author || { display_name: "You", avatar_color: "#b4521f" };
    var av = el("div", { class: "tw-avatar", text: initials(a.display_name) });
    av.style.background = a.avatar_color || "#b4521f";
    var meta = el("div", { class: "tw-item-meta" }, [
      el("span", { class: "tw-item-name", text: a.display_name }),
      a.role === "admin" ? el("span", { class: "tw-badge", text: "Author" }) : null,
      item.status === "pending" ? el("span", { class: "tw-badge", text: "Pending" }) : null,
      el("span", { class: "tw-item-time", text: fmtTime(item.created_at) }),
    ]);
    var main = el("div", { class: "tw-item-main" }, [meta]);
    if (item.anchor && item.anchor.exact) main.appendChild(el("blockquote", { class: "tw-quote", text: "“" + item.anchor.exact.slice(0, 140) + "”" }));
    main.appendChild(el("div", { class: "tw-item-body", text: item.body }));
    if (!compact) {
      var actions = el("div", { class: "tw-item-actions" });
      if (authed()) actions.appendChild(el("button", { class: "tw-link", text: "Reply", onclick: function () {
        var box = replyBox(item.id); main.appendChild(box); box.querySelector("textarea").focus();
      } }));
      var mine = state.me && item.author && item.author.display_name === state.me.display_name;
      if (mine || (state.me && state.me.role === "admin"))
        actions.appendChild(el("button", { class: "tw-link", text: "Delete", onclick: function () {
          if (!confirm("Delete this response?")) return;
          api("/annotations/" + item.id, { method: "DELETE" }).then(function () {
            state.responses = state.responses.filter(function (r) { return r.id !== item.id; });
            state.articleResponses = state.articleResponses.filter(function (r) { return r.id !== item.id; });
            renderResponses();
          });
        } }));
      main.appendChild(actions);
    }
    return el("div", { class: "tw-item" + (item.parent_id ? " tw-reply" : "") }, [av, main]);
  }

  function renderResponses() {
    if (!section) return;
    section.innerHTML = "";
    var tops = state.articleResponses.filter(function (r) { return !r.parent_id; });
    var total = state.articleResponses.length;
    section.appendChild(el("div", { class: "tw-resp-head" }, [
      el("p", { class: "tw-kicker", text: "Responses" }),
      el("span", { class: "tw-resp-count", text: total + (total === 1 ? " response" : " responses") }),
    ]));
    // composer
    if (authed()) {
      var ta = el("textarea", { placeholder: "Share what you think…" });
      section.appendChild(el("div", { class: "tw-composer" }, [ta,
        el("div", { class: "tw-row" }, [
          el("span", { class: "tw-muted", text: state.me ? "as " + state.me.display_name : "" }),
          el("span", { class: "tw-spacer" }),
          el("button", { class: "tw-link", text: "Sign out", onclick: signOut }),
          el("button", { class: "tw-btn", text: "Respond", onclick: function () {
            var body = ta.value.trim(); if (!body) return;
            api("/posts/" + encodeURIComponent(SLUG) + "/annotations", { method: "POST", body: { kind: "article_response", body: body } })
              .then(function (saved) {
                ta.value = "";
                if (saved.status === "pending") toast("Submitted — pending review");
                else { state.articleResponses.push(saved); renderResponses(); toast("Posted"); }
              }).catch(function (e) { toast(e.message); });
          } }),
        ]),
      ]));
    } else {
      section.appendChild(el("div", { class: "tw-signedout" }, [
        el("p", { class: "tw-muted", text: "Join the conversation — sign in to respond." }),
        el("div", { class: "tw-row", style: "justify-content:center;margin-top:10px" }, [
          el("button", { class: "tw-btn", text: "Sign in to respond", onclick: function () { openAuthModal(); } }),
        ]),
      ]));
    }
    tops.forEach(function (r) {
      section.appendChild(renderItemCard(r, false));
      state.articleResponses.filter(function (x) { return x.parent_id === r.id; })
        .forEach(function (x) { section.appendChild(renderItemCard(x, false)); });
    });
  }

  // ── auth modal ────────────────────────────────────────────────────────────────
  function openAuthModal(rect) {
    closePop();
    var input = el("input", { type: "email", placeholder: "you@example.com" });
    var pop = el("div", { class: "tw-pop" }, [
      el("p", { class: "tw-kicker", text: "Sign in" }),
      el("p", { class: "tw-muted", text: "We'll email you a one-time sign-in link. No password." }),
      el("div", { style: "margin-top:10px" }, [input]),
      el("div", { class: "tw-row" }, [
        el("span", { class: "tw-spacer" }),
        el("button", { class: "tw-btn tw-ghost", text: "Cancel", onclick: closePop }),
        el("button", { class: "tw-btn", text: "Send link", onclick: function () {
          var email = input.value.trim();
          if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { input.focus(); return; }
          api("/auth/request", { method: "POST", body: { email: email, return: location.href } })
            .then(function () { pop.innerHTML = ""; pop.appendChild(el("p", { class: "tw-kicker", text: "Check your inbox" }));
              pop.appendChild(el("p", { class: "tw-muted", text: "We sent a sign-in link to " + email + "." })); })
            .catch(function (e) { toast(e.message); });
        } }),
      ]),
    ]);
    activePop = pop; placePop(pop, rect); input.focus();
  }

  function signOut() {
    api("/auth/logout", { method: "POST" }).catch(function () {});
    clearToken(); state.me = null; toast("Signed out");
    renderResponses();
    renderAskBox();
  }

  // ── boot ────────────────────────────────────────────────────────────────────
  function toast(msg) {
    var t = el("div", { class: "tw-toast", text: msg }); document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add("is-on"); });
    setTimeout(function () { t.classList.remove("is-on"); setTimeout(function () { t.remove(); }, 250); }, 2200);
  }

  // capture a magic-link token from the URL fragment, then clean the URL
  function captureTokenFromHash() {
    var m = location.hash.match(/tw_token=([^&]+)/);
    if (m) {
      setToken(decodeURIComponent(m[1]));
      history.replaceState(null, "", location.pathname + location.search +
        location.hash.replace(/[#&]?tw_token=[^&]+/, "").replace(/^&/, "#"));
      toast("Signed in");
      return true;
    }
    return false;
  }

  // offer to sync local (anon) highlights to the account on first sign-in
  function syncLocalToServer() {
    var local = localHls();
    if (!local.length) return Promise.resolve();
    return Promise.all(local.map(function (h) {
      return api("/posts/" + encodeURIComponent(SLUG) + "/annotations", {
        method: "POST", body: { kind: h.kind, body: h.body, anchor: h.anchor },
      }).catch(function () {});
    })).then(function () { saveLocalHls([]); });
  }

  // General "Ask Me Anything" composer — rendered into #tw-ask-box (the AMA post,
  // where it replaces the old Typeform embed). Sign-in gated.
  var askBox = document.getElementById("tw-ask-box");
  function renderAskBox() {
    if (!askBox) return;
    askBox.innerHTML = "";
    askBox.appendChild(el("p", { class: "tw-kicker", text: "Ask Me Anything" }));
    if (authed()) {
      var ta = el("textarea", { placeholder: "Ask @iamkhayyam anything…" });
      askBox.appendChild(el("div", { class: "tw-composer" }, [ta,
        el("div", { class: "tw-row" }, [
          el("span", { class: "tw-muted", text: state.me ? "as " + state.me.display_name : "" }),
          el("span", { class: "tw-spacer" }),
          el("button", { class: "tw-btn", text: "Ask", onclick: function () {
            var body = ta.value.trim(); if (!body) return;
            api("/posts/" + encodeURIComponent(SLUG) + "/annotations", { method: "POST", body: { kind: "question", body: body } })
              .then(function () { ta.value = ""; toast("Question sent — watch this space."); })
              .catch(function (e) { toast(e.message); });
          } }),
        ]),
      ]));
    } else {
      askBox.appendChild(el("p", { class: "tw-muted", text: "The most provocative reader question gets a full answer. Sign in to ask." }));
      askBox.appendChild(el("div", { class: "tw-row", style: "justify-content:center;margin-top:10px" }, [
        el("button", { class: "tw-btn", text: "Sign in to ask", onclick: function () { openAuthModal(); } }),
      ]));
    }
  }

  function load() {
    var p = Promise.resolve();
    if (authed()) p = api("/auth/me").then(function (r) { state.me = r.member; }).catch(function () { clearToken(); });
    return p.then(function () {
      return api("/posts/" + encodeURIComponent(SLUG) + "/annotations").catch(function () {
        return { highlights: [], responses: [], articleResponses: [], me: state.me };
      });
    }).then(function (data) {
      state.me = data.me || state.me;
      state.responses = data.responses || [];
      state.articleResponses = data.articleResponses || [];
      state.highlights = authed() ? (data.highlights || []) : localHls();
      renderAllHighlights();
      renderResponses();
      renderAskBox();
    });
  }

  var freshSignIn = captureTokenFromHash();
  (freshSignIn ? syncLocalToServer() : Promise.resolve()).then(load);
})();

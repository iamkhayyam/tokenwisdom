// Annotations: highlights, private notes, public responses (anchored + article-level).
// Moderation policy: trusted authors post live; new authors land in a pending queue.
const crypto = require("crypto");
const express = require("express");
const { q, one } = require("./db");
const { sendModerationNotice } = require("./email");
const auth = require("./auth");

const { optionalAuth, requireAuth, requireAdmin, signAction, verifyAction, publicMember } = auth;
const { now } = auth.helpers;

const API_BASE = process.env.API_BASE || `http://localhost:${process.env.PORT || 3000}`;
const ADMIN_EMAIL = process.env.ADMIN_EMAIL;
const MAX_BODY = 5000;

const KINDS = new Set(["highlight", "note", "response", "article_response"]);
const PRIVATE_KINDS = new Set(["highlight", "note"]);
const PUBLIC_KINDS = new Set(["response", "article_response"]);

const shape = (a) => ({
  id: a.id,
  post_slug: a.post_slug,
  kind: a.kind,
  body: a.body,
  privacy: a.privacy,
  parent_id: a.parent_id,
  anchor: typeof a.anchor === "string" ? safeJson(a.anchor) : a.anchor,
  status: a.status,
  created_at: a.created_at,
  updated_at: a.updated_at,
  author: a.display_name ? { display_name: a.display_name, avatar_color: a.avatar_color, role: a.role } : null,
});
const safeJson = (s) => { try { return JSON.parse(s); } catch { return null; } };

const router = express.Router();

// ── Read: caller's own annotations + everyone's visible public responses ────────
router.get("/posts/:slug/annotations", optionalAuth, async (req, res) => {
  try {
    const slug = req.params.slug;
    const me = req.member ? req.member.id : null;
    const rows = await q(
      `SELECT a.*, m.display_name, m.avatar_color, m.role
       FROM annotations a JOIN members m ON m.id = a.member_id
       WHERE a.post_slug = ?
         AND ( a.member_id = ?
            OR (a.privacy = 'public' AND a.kind IN ('response','article_response') AND a.status = 'visible') )
       ORDER BY a.created_at ASC`,
      [slug, me]
    );
    const all = rows.map(shape);
    res.json({
      slug,
      me: publicMember(req.member),
      highlights: all.filter((a) => a.kind === "highlight" || a.kind === "note"),
      responses: all.filter((a) => a.kind === "response"),
      articleResponses: all.filter((a) => a.kind === "article_response"),
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Create (highlight/note/response/article_response, incl. threaded replies) ────
router.post("/posts/:slug/annotations", optionalAuth, requireAuth, async (req, res) => {
  try {
    const slug = req.params.slug;
    const { kind, body = null, parent_id = null, anchor = null } = req.body || {};
    if (!KINDS.has(kind)) return res.status(400).json({ error: "Invalid kind" });

    const privacy = PRIVATE_KINDS.has(kind) ? "private" : "public";
    if (PUBLIC_KINDS.has(kind) && !String(body || "").trim())
      return res.status(400).json({ error: "Response text required" });
    if (body && String(body).length > MAX_BODY)
      return res.status(400).json({ error: "Too long" });
    if (kind !== "article_response" && !parent_id && !anchor && kind !== "highlight" && kind !== "note")
      return res.status(400).json({ error: "Anchor required" });

    if (parent_id) {
      const parent = await one("SELECT id, post_slug FROM annotations WHERE id = ?", [parent_id]);
      if (!parent || parent.post_slug !== slug) return res.status(400).json({ error: "Bad parent" });
    }

    // Moderation policy. Private items are always visible (only owner sees them).
    // Public items: trusted/admin → live; everyone else → pending queue.
    let status = "visible";
    if (privacy === "public") {
      const trusted = req.member.role === "admin" || req.member.trust === "trusted";
      status = trusted ? "visible" : "pending";
    }
    // Edge triage can downgrade (Cloudflare Worker sets this after spam scoring).
    const edgeOk = process.env.EDGE_SHARED_SECRET &&
      req.headers["x-edge-secret"] === process.env.EDGE_SHARED_SECRET;
    const suggested = edgeOk ? req.headers["x-suggested-status"] : null;
    if (suggested === "spam") status = "spam";
    else if (suggested === "pending" && status === "visible") status = "pending";

    const id = crypto.randomUUID();
    const ts = now();
    await q(
      `INSERT INTO annotations (id, post_slug, member_id, kind, body, privacy, parent_id, anchor, status, created_at, updated_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
      [id, slug, req.member.id, kind, body, privacy, parent_id,
       anchor ? JSON.stringify(anchor) : null, status, ts, ts]
    );

    if (privacy === "public" && status === "pending" && ADMIN_EMAIL) {
      notifyAdmin(id, slug, String(body)).catch((e) => console.error("notify:", e.message));
    }

    const row = await one(
      `SELECT a.*, m.display_name, m.avatar_color, m.role FROM annotations a
       JOIN members m ON m.id = a.member_id WHERE a.id = ?`, [id]
    );
    res.status(201).json(shape(row));
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Edit own body ───────────────────────────────────────────────────────────────
router.patch("/annotations/:id", optionalAuth, requireAuth, async (req, res) => {
  try {
    const a = await one("SELECT * FROM annotations WHERE id = ?", [req.params.id]);
    if (!a) return res.status(404).json({ error: "Not found" });
    if (a.member_id !== req.member.id) return res.status(403).json({ error: "Not yours" });
    const body = String(req.body.body || "");
    if (body.length > MAX_BODY) return res.status(400).json({ error: "Too long" });
    // Re-queue public edits from non-trusted authors.
    let status = a.status;
    if (a.privacy === "public" && req.member.role !== "admin" && req.member.trust !== "trusted")
      status = "pending";
    await q("UPDATE annotations SET body = ?, status = ?, updated_at = ? WHERE id = ?",
      [body, status, now(), a.id]);
    res.json({ ok: true, status });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Delete (owner or admin) ─────────────────────────────────────────────────────
router.delete("/annotations/:id", optionalAuth, requireAuth, async (req, res) => {
  try {
    const a = await one("SELECT member_id FROM annotations WHERE id = ?", [req.params.id]);
    if (!a) return res.status(404).json({ error: "Not found" });
    if (a.member_id !== req.member.id && req.member.role !== "admin")
      return res.status(403).json({ error: "Not allowed" });
    await q("DELETE FROM annotations WHERE id = ?", [req.params.id]);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Admin moderation ────────────────────────────────────────────────────────────
router.get("/admin/moderation", optionalAuth, requireAdmin, async (req, res) => {
  try {
    const status = ["pending", "visible", "hidden", "spam"].includes(req.query.status)
      ? req.query.status : "pending";
    const rows = await q(
      `SELECT a.*, m.display_name, m.avatar_color, m.role, m.email FROM annotations a
       JOIN members m ON m.id = a.member_id
       WHERE a.privacy = 'public' AND a.status = ? ORDER BY a.created_at DESC LIMIT 200`,
      [status]
    );
    res.json({ status, items: rows.map((r) => ({ ...shape(r), email: r.email })) });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

router.post("/admin/annotations/:id/:action", optionalAuth, requireAdmin, async (req, res) => {
  try {
    const result = await applyModeration(req.params.id, req.params.action);
    if (result.error) return res.status(result.code || 400).json({ error: result.error });
    res.json({ ok: true, status: result.status });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// One-click moderation from the notification email (HMAC-signed, no login needed).
router.get("/admin/action", async (req, res) => {
  try {
    const { id, action, token } = req.query;
    if (!verifyAction(id, action, token))
      return res.status(403).send(actionPage("Link expired or invalid."));
    const result = await applyModeration(id, action);
    if (result.error) return res.status(result.code || 400).send(actionPage(result.error));
    res.send(actionPage(`Response ${action === "approve" ? "approved and published" : action + "d"}.`));
  } catch (e) {
    res.status(500).send(actionPage(e.message));
  }
});

async function applyModeration(id, action) {
  const map = { approve: "visible", hide: "hidden", spam: "spam" };
  const status = map[action];
  if (!status) return { error: "Unknown action" };
  const a = await one("SELECT id, member_id FROM annotations WHERE id = ?", [id]);
  if (!a) return { error: "Not found", code: 404 };
  await q("UPDATE annotations SET status = ?, updated_at = ? WHERE id = ?", [status, now(), id]);
  // Earning trust: once an author has an approved response, let them post live.
  if (action === "approve") {
    await q("UPDATE members SET trust = 'trusted' WHERE id = ? AND trust = 'new'", [a.member_id]).catch(() => {});
  }
  return { status };
}

async function notifyAdmin(id, slug, body) {
  const exp = Date.now() + 7 * 86400000;
  const link = (action) =>
    `${API_BASE}/admin/action?id=${id}&action=${action}&token=${signAction(id, action, exp)}`;
  await sendModerationNotice({
    to: ADMIN_EMAIL, postSlug: slug, body: body.slice(0, 600),
    approveUrl: link("approve"), hideUrl: link("hide"),
  });
}

function actionPage(msg) {
  return `<!doctype html><meta charset=utf-8><title>Moderation — Token Wisdom</title>
  <body style="font-family:-apple-system,sans-serif;max-width:32rem;margin:4rem auto;color:#2b2722">
  <p style="font:600 12px/1 ui-monospace;letter-spacing:.14em;text-transform:uppercase;color:#b4521f">Token Wisdom · Moderation</p>
  <h1>${msg}</h1></body>`;
}

module.exports = { router };

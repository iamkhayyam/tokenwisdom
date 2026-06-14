// Magic-link auth + bearer sessions. Self-hosted, no third party but Resend (mail).
const crypto = require("crypto");
const express = require("express");
const { q, one } = require("./db");
const { sendMagicLink } = require("./email");

const MAGIC_TTL_MIN = Number(process.env.MAGIC_LINK_TTL || 15);
const SESSION_TTL_DAYS = Number(process.env.SESSION_TTL_DAYS || 60);
const ACTION_SECRET = process.env.ACTION_SECRET || process.env.EDGE_SHARED_SECRET || "dev-action-secret";
const API_BASE = process.env.API_BASE || `http://localhost:${process.env.PORT || 3000}`;
const SITE_ORIGIN = (process.env.SITE_ORIGIN || "http://localhost:8080").split(",")[0];

const AVATAR_COLORS = ["#b4521f", "#2b7a4b", "#3a6ea5", "#8a5a9e", "#b08418", "#1f7a7a"];

const now = () => new Date().toISOString().slice(0, 19).replace("T", " ");
const plusMin = (m) => new Date(Date.now() + m * 60000).toISOString().slice(0, 19).replace("T", " ");
const plusDays = (d) => new Date(Date.now() + d * 86400000).toISOString().slice(0, 19).replace("T", " ");
const sha = (s) => crypto.createHash("sha256").update(s).digest("hex");
const rawToken = () => crypto.randomBytes(32).toString("hex");

function colorFor(email) {
  const n = crypto.createHash("md5").update(email).digest()[0];
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

function nameFromEmail(email) {
  return email.split("@")[0].replace(/[._-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── HMAC action tokens for one-click email moderation links ─────────────────────
function signAction(id, action, exp) {
  const payload = `${id}:${action}:${exp}`;
  const sig = crypto.createHmac("sha256", ACTION_SECRET).update(payload).digest("hex").slice(0, 32);
  return `${exp}.${sig}`;
}
function verifyAction(id, action, token) {
  if (!token || !token.includes(".")) return false;
  const [exp, sig] = token.split(".");
  if (Number(exp) < Date.now()) return false;
  const expect = signAction(id, action, Number(exp)).split(".")[1];
  return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expect));
}

// ── Session resolution ──────────────────────────────────────────────────────────
async function memberForBearer(req) {
  const h = req.headers.authorization || "";
  const m = h.match(/^Bearer\s+(.+)$/i);
  if (!m) return null;
  const row = await one(
    `SELECT mem.* FROM sessions s JOIN members mem ON mem.id = s.member_id
     WHERE s.token_hash = ? AND s.expires_at > ?`,
    [sha(m[1]), now()]
  );
  if (!row || row.status === "blocked") return null;
  q("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", [now(), sha(m[1])]).catch(() => {});
  return row;
}

async function optionalAuth(req, _res, next) {
  try { req.member = await memberForBearer(req); } catch { req.member = null; }
  next();
}
function requireAuth(req, res, next) {
  if (!req.member) return res.status(401).json({ error: "Sign in required" });
  next();
}
function requireAdmin(req, res, next) {
  if (!req.member || req.member.role !== "admin") return res.status(403).json({ error: "Admin only" });
  next();
}

const publicMember = (m) =>
  m && { id: m.id, display_name: m.display_name, avatar_color: m.avatar_color, role: m.role, trust: m.trust };

// ── Routes ────────────────────────────────────────────────────────────────────
const router = express.Router();

// Request a magic link. Always responds 200 (no account enumeration).
router.post("/request", async (req, res) => {
  try {
    const email = String(req.body.email || "").trim().toLowerCase();
    const returnTo = String(req.body.return || SITE_ORIGIN);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
      return res.status(400).json({ error: "Valid email required" });

    let member = await one("SELECT * FROM members WHERE email = ?", [email]);
    if (!member) {
      const id = crypto.randomUUID();
      const name = String(req.body.name || "").trim() || nameFromEmail(email);
      await q(
        "INSERT INTO members (id, email, display_name, avatar_color, created_at) VALUES (?,?,?,?,?)",
        [id, email, name.slice(0, 120), colorFor(email), now()]
      );
      member = { id, email };
    } else if (member.status === "blocked") {
      return res.json({ ok: true }); // silently no-op
    }

    const token = rawToken();
    await q("INSERT INTO auth_tokens (token_hash, member_id, expires_at) VALUES (?,?,?)", [
      sha(token), member.id, plusMin(MAGIC_TTL_MIN),
    ]);
    const url = `${API_BASE}/auth/verify?token=${token}&return=${encodeURIComponent(returnTo)}`;
    await sendMagicLink({ to: email, url });
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// Consume a magic link → create a session → bounce back to the article with the
// bearer token in the URL fragment (fragments are not sent to servers).
router.get("/verify", async (req, res) => {
  try {
    const token = String(req.query.token || "");
    const returnTo = String(req.query.return || SITE_ORIGIN);
    const row = await one(
      "SELECT * FROM auth_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
      [sha(token), now()]
    );
    if (!row) return res.status(400).send(errorPage("This sign-in link is invalid or has expired."));

    await q("UPDATE auth_tokens SET used_at = ? WHERE token_hash = ?", [now(), sha(token)]);
    const member = await one("SELECT * FROM members WHERE id = ?", [row.member_id]);
    if (!member.verified_at) await q("UPDATE members SET verified_at = ? WHERE id = ?", [now(), member.id]);

    const session = rawToken();
    await q("INSERT INTO sessions (token_hash, member_id, created_at, expires_at) VALUES (?,?,?,?)", [
      sha(session), member.id, now(), plusDays(SESSION_TTL_DAYS),
    ]);

    const safeReturn = returnTo.startsWith(SITE_ORIGIN) || returnTo.startsWith("http://localhost")
      ? returnTo : SITE_ORIGIN;
    const sep = safeReturn.includes("#") ? "&" : "#";
    res.redirect(`${safeReturn}${sep}tw_token=${session}`);
  } catch (e) {
    res.status(500).send(errorPage(e.message));
  }
});

router.get("/me", optionalAuth, (req, res) => res.json({ member: publicMember(req.member) }));

router.post("/logout", async (req, res) => {
  const h = req.headers.authorization || "";
  const m = h.match(/^Bearer\s+(.+)$/i);
  if (m) await q("DELETE FROM sessions WHERE token_hash = ?", [sha(m[1])]).catch(() => {});
  res.json({ ok: true });
});

function errorPage(msg) {
  return `<!doctype html><meta charset=utf-8><title>Token Wisdom</title>
  <body style="font-family:-apple-system,sans-serif;max-width:32rem;margin:4rem auto;color:#2b2722">
  <p style="font:600 12px/1 ui-monospace;letter-spacing:.14em;text-transform:uppercase;color:#b4521f">Token Wisdom</p>
  <h1>Sign-in problem</h1><p>${msg}</p></body>`;
}

module.exports = {
  router, optionalAuth, requireAuth, requireAdmin,
  signAction, verifyAction, publicMember,
  helpers: { now, sha, colorFor },
};

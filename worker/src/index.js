/* Token Wisdom — community edge (Cloudflare Worker).
 *
 * Sits in front of the origin Express API. Two jobs:
 *   1. Rate-limit + spam-triage PUBLIC writes before they ever reach the origin,
 *      then forward them with X-Edge-Secret + X-Suggested-Status.
 *   2. Transparently proxy everything else (auth, reads, admin) to the origin.
 *
 * Bindings (wrangler.toml):
 *   ORIGIN            (var)    e.g. https://token-wisdom-api.up.railway.app
 *   EDGE_SHARED_SECRET (secret) shared with the origin (server checks it)
 *   RL               (KV)      rate-limit counters
 *   ALLOWED_ORIGIN   (var)     site origin for CORS, e.g. https://tokenwisdom.ai
 */

const BANNED = [
  "viagra", "casino", "porn", "crypto airdrop", "free money",
  "click here", "make money fast", "telegram.me", "t.me/", "bit.ly/",
];
const MAX_LINKS = 2;
const WINDOW_SEC = 600;     // 10-minute window
const MAX_POSTS = 5;        // per IP per window before throttling

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return cors(env, new Response(null, { status: 204 }));

    const isPublicWrite =
      request.method === "POST" && /^\/posts\/[^/]+\/annotations$/.test(url.pathname);

    if (isPublicWrite) return cors(env, await handleWrite(request, env, url));
    return cors(env, await proxy(request, env, url));
  },
};

async function handleWrite(request, env, url) {
  const ip = request.headers.get("CF-Connecting-IP") || "0.0.0.0";

  // ── rate limit (per IP, fixed window in KV) ───────────────────────────────────
  if (env.RL) {
    const key = `rl:${ip}`;
    const count = Number((await env.RL.get(key)) || 0) + 1;
    if (count > MAX_POSTS)
      return json(429, { error: "You're posting too fast — try again in a few minutes." });
    await env.RL.put(key, String(count), { expirationTtl: WINDOW_SEC });
  }

  // Body is consumed for triage, then re-sent to the origin.
  let body = {};
  try { body = await request.clone().json(); } catch (e) {}
  const text = String(body.body || "");
  const kind = body.kind || "";

  // Private highlights/notes skip triage entirely.
  const isPublic = kind === "response" || kind === "article_response";
  let suggested = null;
  if (isPublic) suggested = triage(text);

  const headers = new Headers(request.headers);
  headers.set("X-Edge-Secret", env.EDGE_SHARED_SECRET || "");
  if (suggested) headers.set("X-Suggested-Status", suggested);
  headers.delete("host");

  if (suggested === "spam") {
    // Still record it (origin stores as spam) so the admin queue can see patterns,
    // but tell the user it's received — don't reveal the spam classifier.
    headers.set("X-Suggested-Status", "spam");
  }

  return fetch(env.ORIGIN + url.pathname + url.search, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
}

// Cheap heuristics → suggested status ("spam" | "pending" | null=leave to origin).
function triage(text) {
  const lower = text.toLowerCase();
  const links = (text.match(/https?:\/\//g) || []).length;
  if (BANNED.some((w) => lower.includes(w))) return "spam";
  if (links > MAX_LINKS) return "spam";
  // shouting / gibberish → hold for review even if author is trusted
  const letters = text.replace(/[^a-z]/gi, "");
  const caps = text.replace(/[^A-Z]/g, "").length;
  if (letters.length > 20 && caps / letters.length > 0.6) return "pending";
  if (links >= 1) return "pending"; // any link from a fresh post → review
  return null;
}

async function proxy(request, env, url) {
  const headers = new Headers(request.headers);
  headers.delete("host");
  // Reads can be edge-cached briefly; everything else passes straight through.
  const init = { method: request.method, headers, body: request.body, redirect: "manual" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.clone().text();
  }
  return fetch(env.ORIGIN + url.pathname + url.search, init);
}

// ── helpers ───────────────────────────────────────────────────────────────────
function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function cors(env, res) {
  const r = new Response(res.body, res);
  r.headers.set("Access-Control-Allow-Origin", env.ALLOWED_ORIGIN || "*");
  r.headers.set("Vary", "Origin");
  r.headers.set("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
  r.headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
  return r;
}

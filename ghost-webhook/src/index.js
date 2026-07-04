// Relays Ghost's post.published webhook into a GitHub Actions rebuild.
// Ghost can't call GitHub's API directly (webhooks have no configurable auth
// header), so this Worker verifies Ghost's HMAC signature and re-dispatches
// as an authenticated repository_dispatch event.

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/ghost-webhook") {
      return new Response("Not found", { status: 404 });
    }

    const rawBody = await request.text();
    const sigHeader = request.headers.get("X-Ghost-Signature") || "";
    const match = /sha256=([a-f0-9]+),\s*t=(\d+)/.exec(sigHeader);
    if (!match) {
      return new Response("Missing signature", { status: 401 });
    }
    const [, sigHex, timestamp] = match;

    const valid = await verifySignature(env.GHOST_WEBHOOK_SECRET, rawBody + timestamp, sigHex);
    if (!valid) {
      return new Response("Invalid signature", { status: 401 });
    }

    // Respond to Ghost immediately; the GitHub call can run after.
    ctx.waitUntil(triggerRebuild(env));

    return new Response("ok", { status: 200 });
  },
};

async function verifySignature(secret, message, expectedHex) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sigBuf = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  const hex = [...new Uint8Array(sigBuf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return timingSafeEqual(hex, expectedHex);
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function triggerRebuild(env) {
  const resp = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "tw-ghost-webhook",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ event_type: "ghost-content-updated" }),
  });
  if (!resp.ok) {
    console.error("GitHub dispatch failed", resp.status, await resp.text());
  }
}

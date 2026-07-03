# Community Layer — Highlights, Notes & Responses

Self-hosted Medium-style reading community for Token Wisdom. No third party owns the
conversation: our Express API + MySQL, magic-link auth via Resend, optional Cloudflare
Worker edge. The static site stays static; all interactivity is a dependency-free client.

## Pieces

| Where | What |
|---|---|
| `api/schema.sql` | `members`, `auth_tokens`, `sessions`, `annotations` tables |
| `api/auth.js` | magic-link request/verify, bearer sessions, HMAC one-click moderation links |
| `api/annotations.js` | annotation CRUD + trust-based moderation + admin endpoints |
| `api/email.js` | Resend (magic link + admin notify); logs to console in dev |
| `assets/annotate.{js,css}` | client (toolbar, anchoring, highlights, responses) — **source of truth**; copied into `docs/assets/` by `generate_site.py` |
| `worker/` | Cloudflare Worker: rate-limit + spam triage on public writes |

`docs/` is wiped (`shutil.rmtree`) on every build, so client assets live in `assets/`
and are copied during generation. Post pages get the client injected via
`community_assets()` in `generate_site.py` (post renderers only).

## Ask Me Anything (highlight → question)

The selection toolbar's **Ask** action (and the composer that replaces the old Typeform
on the AMA post, rendered into `#tw-ask-box`) send a `question` annotation — private to
the author, sign-in required. Each question emails `ADMIN_EMAIL` (reply-to = the asker)
and lands in `GET /admin/questions`. The best ones get answered as `ask-me-anything` posts.

> **Deploy gotcha:** `question` is a new value in the `annotations.kind` ENUM. Existing
> databases need the idempotent `ALTER TABLE annotations MODIFY COLUMN kind …` (already in
> `schema.sql`) applied via `npm run migrate` **before** the feature works — the API does
> not auto-migrate on deploy.

## Model

- **Anonymous readers** highlight + write private notes → stored in `localStorage` only,
  never sent to us. On sign-in, local highlights sync up.
- **Signed-in members** (magic link) sync highlights/notes to the server and can post
  public responses (anchored to a passage, or at the bottom of the article).
- **Moderation:** new authors → responses land `pending`; once an admin approves one,
  the author becomes `trusted` and posts live thereafter. Admins approve from the
  `/admin/moderation` queue or a one-click link in the notification email.
- **Edge (Worker):** rate-limits by IP and runs cheap spam heuristics, forwarding a
  `X-Suggested-Status` the origin honors (only when `X-Edge-Secret` matches).

## API env vars (Railway)

```
DATABASE_URL          mysql://…           (already set for the read API)
SITE_ORIGIN           https://tokenwisdom.ai     # CORS allowlist (comma-separated ok)
API_BASE              https://token-wisdom-api.up.railway.app
RESEND_API_KEY        re_…                # omit in dev → links print to console
MAIL_FROM             "Token Wisdom <community@tokenwisdom.ai>"
ADMIN_EMAIL           you@tokenwisdom.ai  # gets moderation notifications
ACTION_SECRET         <random>            # signs one-click moderation links
EDGE_SHARED_SECRET    <random>            # must match the Worker secret
MAGIC_LINK_TTL        15                  # minutes (optional)
SESSION_TTL_DAYS      60                  # optional
```

Apply schema on deploy: `npm run migrate` (idempotent).
Promote your first admin once: `UPDATE members SET role='admin', trust='trusted' WHERE email='you@…';`

## Static build

```
TW_API_BASE="https://token-wisdom-edge.<acct>.workers.dev" python3 generate_site.py
```
`TW_API_BASE` is baked into post pages as `window.TW_API` (point it at the Worker in
prod, or the API directly if you skip the edge). Defaults to `http://localhost:3000`.

## Cloudflare Worker

```
cd worker
wrangler kv namespace create RL        # paste id into wrangler.toml
wrangler secret put EDGE_SHARED_SECRET # match the API's value
wrangler deploy
```
Set `ORIGIN` + `ALLOWED_ORIGIN` vars in `wrangler.toml`.

## Local dev

```
# MySQL
docker run -d --name tw-mysql -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=tokenwisdom -p 3307:3306 mysql:8

# API (dev mail = console)
cd api && npm install
DATABASE_URL="mysql://root:root@127.0.0.1:3307/tokenwisdom" SITE_ORIGIN="http://localhost:8765" \
  API_BASE="http://localhost:3000" ADMIN_EMAIL="you@example.com" ACTION_SECRET=dev EDGE_SHARED_SECRET=dev \
  node migrate.js && node server.js

# Site (point the client at the local API)
TW_API_BASE="http://localhost:3000" python3 generate_site.py
```

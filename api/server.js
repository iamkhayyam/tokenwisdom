const express = require("express");
const { q } = require("./db");
const authModule = require("./auth");
const annotations = require("./annotations");
const links = require("./links");

const app = express();
app.use(express.json());

// ── CORS (static site and API are different origins; bearer-token auth) ──────────
const ALLOWED = (process.env.SITE_ORIGIN || "http://localhost:8080")
  .split(",").map((s) => s.trim()).filter(Boolean);
app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && (ALLOWED.includes(origin) || origin.startsWith("http://localhost"))) {
    res.header("Access-Control-Allow-Origin", origin);
    res.header("Vary", "Origin");
  }
  res.header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
  res.header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Edge-Secret, X-Suggested-Status");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

// ── Health ────────────────────────────────────────────────────────────────────

app.get("/", (req, res) => res.json({ ok: true, service: "token-wisdom-api" }));

// ── Community: auth + annotations ───────────────────────────────────────────────
app.use("/auth", authModule.router);
app.use("/", annotations.router);
app.use("/", links.router);

// ── Terms ─────────────────────────────────────────────────────────────────────

app.get("/terms", async (req, res) => {
  try {
    const { category, color, search, limit = 50, offset = 0 } = req.query;
    let sql = "SELECT id, name, slug, category, color, definition, edition_count, first_date, latest_date FROM terms WHERE 1=1";
    const params = [];
    if (category) { sql += " AND category = ?"; params.push(category); }
    if (color)    { sql += " AND color = ?";    params.push(color); }
    if (search)   { sql += " AND (name LIKE ? OR definition LIKE ?)"; params.push(`%${search}%`, `%${search}%`); }
    const lim = parseInt(limit, 10) || 50;
    const off = parseInt(offset, 10) || 0;
    sql += ` ORDER BY name LIMIT ${lim} OFFSET ${off}`;
    const rows = await q(sql, params);
    res.json({ terms: rows, limit: lim, offset: off });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/terms/:slug", async (req, res) => {
  try {
    const [term] = await q("SELECT * FROM terms WHERE slug = ?", [req.params.slug]);
    if (!term) return res.status(404).json({ error: "Not found" });

    const [history, editions, timeline, related] = await Promise.all([
      q("SELECT text, edition, date, slug FROM term_definition_history WHERE term_id = ? ORDER BY edition", [term.id]),
      q("SELECT edition, week, date, slug, title, source FROM term_editions WHERE term_id = ? ORDER BY edition", [term.id]),
      q("SELECT period, count FROM term_timeline WHERE term_id = ? ORDER BY period", [term.id]),
      q("SELECT related_slug, related_name, related_color, shared_count FROM term_related WHERE term_id = ? ORDER BY shared_count DESC", [term.id]),
    ]);

    res.json({ ...term, definition_history: history, editions, timeline, related });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/terms/:slug/editions", async (req, res) => {
  try {
    const [term] = await q("SELECT id FROM terms WHERE slug = ?", [req.params.slug]);
    if (!term) return res.status(404).json({ error: "Not found" });
    const editions = await q(
      "SELECT edition, week, date, slug, title, source FROM term_editions WHERE term_id = ? ORDER BY edition",
      [term.id]
    );
    res.json({ editions });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Categories / Colors ───────────────────────────────────────────────────────

app.get("/categories", async (req, res) => {
  try {
    const rows = await q(
      "SELECT category, COUNT(*) as count FROM terms WHERE category IS NOT NULL GROUP BY category ORDER BY count DESC"
    );
    res.json({ categories: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Posts ─────────────────────────────────────────────────────────────────────

app.get("/posts", async (req, res) => {
  try {
    const { limit = 20, offset = 0, tag } = req.query;
    const lim = parseInt(limit, 10) || 20;
    const off = parseInt(offset, 10) || 0;
    let sql, params;
    if (tag) {
      sql = `SELECT p.id, p.title, p.slug, p.excerpt, p.feature_image, p.published_at, p.reading_time
             FROM posts p
             JOIN post_tags pt ON pt.post_id = p.id
             JOIN tags t ON t.id = pt.tag_id
             WHERE t.slug = ?
             ORDER BY p.published_at DESC LIMIT ${lim} OFFSET ${off}`;
      params = [tag];
    } else {
      sql = `SELECT id, title, slug, excerpt, feature_image, published_at, reading_time
             FROM posts ORDER BY published_at DESC LIMIT ${lim} OFFSET ${off}`;
      params = [];
    }
    const rows = await q(sql, params);
    res.json({ posts: rows, limit: lim, offset: off });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/posts/:slug", async (req, res) => {
  try {
    const [post] = await q("SELECT * FROM posts WHERE slug = ?", [req.params.slug]);
    if (!post) return res.status(404).json({ error: "Not found" });
    const tags = await q(
      `SELECT t.id, t.name, t.slug, t.accent_color FROM tags t
       JOIN post_tags pt ON pt.tag_id = t.id
       WHERE pt.post_id = ? ORDER BY pt.sort_order`,
      [post.id]
    );
    res.json({ ...post, tags });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Tags ──────────────────────────────────────────────────────────────────────

app.get("/tags", async (req, res) => {
  try {
    const rows = await q(
      `SELECT t.id, t.name, t.slug, t.description, t.accent_color, COUNT(pt.post_id) as post_count
       FROM tags t LEFT JOIN post_tags pt ON pt.tag_id = t.id
       GROUP BY t.id ORDER BY post_count DESC`
    );
    res.json({ tags: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Search ────────────────────────────────────────────────────────────────────

app.get("/search", async (req, res) => {
  try {
    const { q: query, limit = 10 } = req.query;
    if (!query) return res.status(400).json({ error: "q is required" });
    const lim = parseInt(limit, 10) || 10;
    const [terms, posts] = await Promise.all([
      q(
        `SELECT name, slug, category, color, definition FROM terms WHERE name LIKE ? OR definition LIKE ? LIMIT ${lim}`,
        [`%${query}%`, `%${query}%`]
      ),
      q(
        `SELECT title, slug, excerpt, published_at FROM posts WHERE title LIKE ? OR plaintext LIKE ? LIMIT ${lim}`,
        [`%${query}%`, `%${query}%`]
      ),
    ]);
    res.json({ query, terms, posts });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`token-wisdom-api listening on :${PORT}`));

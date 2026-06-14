#!/usr/bin/env node

const mysql = require("mysql2/promise");
const fs = require("fs");
const path = require("path");

const DATA_DIR = path.join(__dirname, "../data");

const DB_URL =
  process.env.DATABASE_URL ||
  process.env.MYSQL_PUBLIC_URL ||
  `mysql://${process.env.MYSQLUSER}:${process.env.MYSQLPASSWORD}@${process.env.MYSQLHOST}:${process.env.MYSQLPORT}/${process.env.MYSQLDATABASE}`;

function parseDate(str) {
  if (!str) return null;
  return str.slice(0, 10); // YYYY-MM-DD
}

function parseDateTime(str) {
  if (!str) return null;
  return new Date(str).toISOString().slice(0, 19).replace("T", " ");
}

async function bulkInsert(conn, table, cols, rows) {
  if (!rows.length) return;
  const chunkSize = Math.floor(65000 / cols.length);
  for (let i = 0; i < rows.length; i += chunkSize) {
    const chunk = rows.slice(i, i + chunkSize);
    const ph = chunk.map(() => `(${cols.map(() => "?").join(",")})`).join(",");
    await conn.execute(`INSERT INTO ${table} (${cols.join(",")}) VALUES ${ph}`, chunk.flat());
  }
}

async function run() {
  console.log("Connecting to MySQL…");
  const conn = await mysql.createConnection(DB_URL);

  console.log("Applying schema…");
  const schema = fs.readFileSync(path.join(__dirname, "schema.sql"), "utf8");
  for (const stmt of schema.split(";").map((s) => s.trim()).filter(Boolean)) {
    try {
      await conn.execute(stmt);
    } catch (e) {
      if (e.code === "ER_DUP_KEYNAME") continue; // index already exists
      throw e;
    }
  }

  // ── Tags ──────────────────────────────────────────────────────────────────
  console.log("Seeding tags…");
  const allTags = JSON.parse(fs.readFileSync(path.join(DATA_DIR, "all_tags.json"), "utf8"));
  for (const t of allTags) {
    await conn.execute(
      `INSERT INTO tags (id, name, slug, description, feature_image, accent_color, url)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description)`,
      [t.id, t.name, t.slug, t.description || null, t.feature_image || null, t.accent_color || null, t.url || null]
    );
  }
  console.log(`  → ${allTags.length} tags`);

  // ── Posts + post_tags ─────────────────────────────────────────────────────
  console.log("Seeding posts…");
  const allPosts = JSON.parse(fs.readFileSync(path.join(DATA_DIR, "all_posts.json"), "utf8"));
  for (const p of allPosts) {
    await conn.execute(
      `INSERT INTO posts
         (id, uuid, title, slug, html, plaintext, excerpt, custom_excerpt,
          feature_image, featured, visibility, reading_time,
          published_at, created_at, updated_at, url, meta_title, meta_description)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON DUPLICATE KEY UPDATE title=VALUES(title), html=VALUES(html), published_at=VALUES(published_at)`,
      [
        p.id, p.uuid, p.title, p.slug,
        p.html || null, p.plaintext || null, p.excerpt || null, p.custom_excerpt || null,
        p.feature_image || null, p.featured ? 1 : 0, p.visibility || "public",
        p.reading_time || null,
        parseDateTime(p.published_at), parseDateTime(p.created_at), parseDateTime(p.updated_at),
        p.url || null, p.meta_title || null, p.meta_description || null,
      ]
    );
    for (let i = 0; i < (p.tags || []).length; i++) {
      const tag = p.tags[i];
      await conn.execute(
        `INSERT IGNORE INTO post_tags (post_id, tag_id, sort_order) VALUES (?, ?, ?)`,
        [p.id, tag.id, i]
      );
    }
  }
  console.log(`  → ${allPosts.length} posts`);

  // ── Terms ─────────────────────────────────────────────────────────────────
  console.log("Seeding lexicon terms…");
  const lexicon = JSON.parse(fs.readFileSync(path.join(DATA_DIR, "lexicon.json"), "utf8"));
  const terms = lexicon.terms;

  // Insert all term rows in one bulk statement
  const termRows = terms.map(t => [
    t.name, t.slug, t.category || null, t.color || null,
    t.definition || null, t.edition_count || 0,
    t.first?.edition || null, parseDate(t.first?.date), t.first?.slug || null,
    t.latest?.edition || null, parseDate(t.latest?.date), t.latest?.slug || null,
  ]);
  const placeholders = termRows.map(() => "(?,?,?,?,?,?,?,?,?,?,?,?)").join(",");
  await conn.execute(
    `INSERT INTO terms
       (name, slug, category, color, definition, edition_count,
        first_edition, first_date, first_slug, latest_edition, latest_date, latest_slug)
     VALUES ${placeholders}
     ON DUPLICATE KEY UPDATE
       definition=VALUES(definition), edition_count=VALUES(edition_count),
       latest_edition=VALUES(latest_edition), latest_date=VALUES(latest_date)`,
    termRows.flat()
  );

  // Fetch slug→id map
  const [idRows] = await conn.execute("SELECT id, slug FROM terms");
  const slugToId = Object.fromEntries(idRows.map(r => [r.slug, r.id]));

  // Bulk-clear and bulk-insert child tables
  const histRows = [], edRows = [], tlRows = [], relRows = [];
  for (const term of terms) {
    const tid = slugToId[term.slug];
    for (const h of term.definition_history || [])
      histRows.push([tid, h.text, h.edition, parseDate(h.date), h.slug || null]);
    for (const e of term.editions || [])
      edRows.push([tid, e.edition, e.week || null, parseDate(e.date), e.slug || null, e.title || null, e.source || null]);
    for (const tl of term.timeline || [])
      tlRows.push([tid, tl.period, tl.count || 0]);
    for (const r of term.related || [])
      relRows.push([tid, r.slug, r.name || null, r.color || null, r.shared || 0]);
  }

  await conn.execute("DELETE FROM term_definition_history");
  await bulkInsert(conn, "term_definition_history", ["term_id","text","edition","date","slug"], histRows);

  await conn.execute("DELETE FROM term_editions");
  await bulkInsert(conn, "term_editions", ["term_id","edition","week","date","slug","title","source"], edRows);

  await conn.execute("DELETE FROM term_timeline");
  await bulkInsert(conn, "term_timeline", ["term_id","period","count"], tlRows);

  await conn.execute("DELETE FROM term_related");
  await bulkInsert(conn, "term_related", ["term_id","related_slug","related_name","related_color","shared_count"], relRows);
  console.log(`  → ${terms.length} terms`);

  await conn.end();
  console.log("Done.");
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});

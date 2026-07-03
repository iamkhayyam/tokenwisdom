// Weekly Reading Room CSV ingest. Replaces the manual "drop a file in
// data/links/, run build_links_db.py, commit" step with an admin-authenticated
// upload that commits straight to the same GitHub repo build_links_db.py reads
// from — the static build/deploy path (generate_site.py → docs/ → CF Pages)
// is untouched, this just removes the local-file part of it.
const express = require("express");
const multer = require("multer");
const { parse } = require("csv-parse/sync");
const { optionalAuth, requireAdmin } = require("./auth");

const GITHUB_API = "https://api.github.com";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const GITHUB_OWNER = process.env.GITHUB_OWNER || "iamkhayyam";
const GITHUB_REPO = process.env.GITHUB_REPO || "tokenwisdom";
const GITHUB_BRANCH = process.env.GITHUB_BRANCH || "master";
const LINKS_DIR = "data/links";

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 2 * 1024 * 1024 } });
const router = express.Router();

// ── GitHub Contents API helpers ──────────────────────────────────────────────
async function githubRequest(method, path, body) {
  const res = await fetch(`${GITHUB_API}${path}`, {
    method,
    headers: {
      Authorization: `token ${GITHUB_TOKEN}`,
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "token-wisdom-api",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${await res.text()}`);
  return res.status === 204 ? {} : res.json();
}

const getFile = (path) =>
  githubRequest("GET", `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${path}?ref=${GITHUB_BRANCH}`);

async function putFile(path, content, message) {
  const existing = await getFile(path);
  return githubRequest("PUT", `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${path}`, {
    message,
    content: Buffer.from(content).toString("base64"),
    branch: GITHUB_BRANCH,
    ...(existing?.sha ? { sha: existing.sha } : {}),
  });
}

async function listLinkCsvs() {
  const items = await githubRequest(
    "GET", `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${LINKS_DIR}?ref=${GITHUB_BRANCH}`
  );
  return (items || []).filter((f) => f.name.toLowerCase().endsWith(".csv"));
}

// ── Filename + row parsing — mirrors build_links_db.py exactly ──────────────
function parseStem(stem) {
  let m = stem.match(/^(\d{2})\.W\.?(\d{1,2})[.-](TNL|TWS)$/i);
  if (m) return { year: 2000 + Number(m[1]), week: Number(m[2]), section: m[3].toUpperCase() };
  m = stem.match(/^w[-.](\d{1,2})\.(TNL|TWS)$/i);
  if (m) return { year: 2026, week: Number(m[1]), section: m[2].toUpperCase() };
  return null;
}

function parseLinksCsv(text) {
  const records = parse(text, { columns: true, skip_empty_lines: true, trim: true, bom: true });
  const rows = [];
  for (const row of records) {
    const title = (row.title || "").trim();
    const url = (row.url || "").trim();
    if (!title || !url) continue;
    rows.push({
      id: (row.id || "").trim(),
      title,
      note: (row.note || "").trim(),
      excerpt: (row.excerpt || "").trim(),
      url,
      tags: (row.tags || "").split(",").map((t) => t.trim()).filter(Boolean),
      created: (row.created || "").trim(),
      cover: (row.cover || "").trim(),
      favorite: (row.favorite || "").trim().toLowerCase() === "true",
    });
  }
  return rows;
}

// Re-derives the full data/links.json (all weeks), same shape build_links_db.py
// writes, using every CSV currently in the repo plus the freshly uploaded one.
async function rebuildLinksJson(newFilename, newText) {
  const files = await listLinkCsvs();
  const buckets = new Map();
  const skipped = [];

  function ingest(filename, text) {
    const parsed = parseStem(filename.replace(/\.csv$/i, ""));
    if (!parsed) { skipped.push(filename); return; }
    const key = `${parsed.year}-${parsed.week}`;
    if (!buckets.has(key)) buckets.set(key, { year: parsed.year, week: parsed.week, tnl: [], tws: [] });
    const bucket = buckets.get(key);
    bucket[parsed.section === "TNL" ? "tnl" : "tws"].push(...parseLinksCsv(text));
  }

  for (const f of files) {
    if (f.name === newFilename) continue; // use the just-uploaded content, not a stale fetch
    const file = await getFile(`${LINKS_DIR}/${f.name}`);
    ingest(f.name, Buffer.from(file.content, "base64").toString("utf-8"));
  }
  ingest(newFilename, newText);

  const weeks = [...buckets.values()].sort((a, b) => a.year - b.year || a.week - b.week);
  const allLinks = [];
  for (const w of weeks) {
    for (const item of w.tnl) allLinks.push({ ...item, year: w.year, week: w.week, section: "tnl" });
    for (const item of w.tws) allLinks.push({ ...item, year: w.year, week: w.week, section: "tws" });
  }
  const latest = weeks[weeks.length - 1] || {};
  const db = {
    current_year: latest.year ?? null,
    current_week: latest.week ?? null,
    total_weeks: weeks.length,
    total_tnl: weeks.reduce((n, w) => n + w.tnl.length, 0),
    total_tws: weeks.reduce((n, w) => n + w.tws.length, 0),
    weeks,
    all_links: allLinks,
  };
  return { db, skipped };
}

// ── Routes ────────────────────────────────────────────────────────────────────

router.get("/admin/links", optionalAuth, requireAdmin, async (req, res) => {
  try {
    if (!GITHUB_TOKEN) return res.status(500).json({ error: "GITHUB_TOKEN not configured" });
    const files = await listLinkCsvs();
    res.json({
      files: files
        .map((f) => ({ name: f.name, ...(parseStem(f.name.replace(/\.csv$/i, "")) || {}) }))
        .sort((a, b) => (a.year || 0) - (b.year || 0) || (a.week || 0) - (b.week || 0)),
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

router.post("/admin/links/upload", optionalAuth, requireAdmin, upload.single("csv"), async (req, res) => {
  try {
    if (!GITHUB_TOKEN) return res.status(500).json({ error: "GITHUB_TOKEN not configured" });
    if (!req.file) return res.status(400).json({ error: "CSV file required (multipart field name: csv)" });

    const filename = String(req.body.filename || req.file.originalname || "").trim();
    if (!filename.toLowerCase().endsWith(".csv"))
      return res.status(400).json({ error: "Filename must end in .csv" });

    const parsed = parseStem(filename.replace(/\.csv$/i, ""));
    if (!parsed)
      return res.status(400).json({
        error: `Unrecognised filename "${filename}" — expected e.g. 26.W23.TNL.csv or 26.W23.TWS.csv`,
      });

    const text = req.file.buffer.toString("utf-8");
    const items = parseLinksCsv(text);
    if (!items.length)
      return res.status(400).json({ error: "CSV parsed to zero valid rows (need title + url columns)" });

    await putFile(`${LINKS_DIR}/${filename}`, text, `Upload ${filename} (${items.length} links) via admin upload`);
    const { db, skipped } = await rebuildLinksJson(filename, text);
    await putFile("data/links.json", JSON.stringify(db, null, 2), `Rebuild links.json after ${filename} upload`);

    res.json({
      ok: true,
      file: filename,
      year: parsed.year,
      week: parsed.week,
      section: parsed.section,
      items_parsed: items.length,
      total_weeks: db.total_weeks,
      total_tnl: db.total_tnl,
      total_tws: db.total_tws,
      skipped_files: skipped,
      note: "Committed to GitHub. Run generate_site.py (or your usual build) locally and push to rebuild the static Reading Room page.",
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

module.exports = { router, parseStem, parseLinksCsv };

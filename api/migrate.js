#!/usr/bin/env node
// Apply schema.sql (idempotent: CREATE TABLE IF NOT EXISTS + tolerant of existing
// indexes). Safe to run repeatedly on deploy.
const fs = require("fs");
const path = require("path");
const mysql = require("mysql2/promise");
const { DB_URL } = require("./db");

async function run() {
  const sql = fs.readFileSync(path.join(__dirname, "schema.sql"), "utf8");
  const conn = await mysql.createConnection({ uri: DB_URL, multipleStatements: true });
  // Strip line comments BEFORE splitting — a comment may itself contain a ';'.
  const stmts = sql
    .replace(/--.*$/gm, "")
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
  let applied = 0;
  for (const stmt of stmts) {
    try {
      await conn.query(stmt);
      applied++;
    } catch (e) {
      // Indexes/tables that already exist are fine; surface anything else.
      if (/already exists|Duplicate key name/i.test(e.message)) continue;
      console.error(`! ${e.message}\n  in: ${stmt.slice(0, 80)}…`);
    }
  }
  console.log(`Migration done (${applied}/${stmts.length} statements applied).`);
  await conn.end();
}

run().catch((e) => { console.error(e); process.exit(1); });

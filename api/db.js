// Shared MySQL pool + query helper. Single source of truth for DB access.
const mysql = require("mysql2/promise");

const DB_URL =
  process.env.DATABASE_URL ||
  process.env.MYSQL_PUBLIC_URL ||
  `mysql://${process.env.MYSQLUSER}:${process.env.MYSQLPASSWORD}@${process.env.MYSQLHOST}:${process.env.MYSQLPORT}/${process.env.MYSQLDATABASE}`;

let pool;
function db() {
  if (!pool) pool = mysql.createPool({ uri: DB_URL, namedPlaceholders: false });
  return pool;
}

async function q(sql, params = []) {
  const [rows] = await db().query(sql, params);
  return rows;
}

async function one(sql, params = []) {
  const rows = await q(sql, params);
  return rows[0] || null;
}

module.exports = { db, q, one, DB_URL };

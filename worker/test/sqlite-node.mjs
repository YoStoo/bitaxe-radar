// sql.js for Node tests (the Worker uses src/sqlite.js with the browser build).
import initSqlJs from "sql.js";
import { wrapSqlJs } from "../src/sqlwrap.js";
let SQL = null;
export async function openDbNode(bytes, sqlText) {
  if (!SQL) SQL = await initSqlJs();
  if (sqlText != null) { const db = new SQL.Database(); db.exec(sqlText); return wrapSqlJs(db); }
  return wrapSqlJs(new SQL.Database(bytes));
}
export async function sqlToBytes(sqlText) {
  if (!SQL) SQL = await initSqlJs();
  const db = new SQL.Database();
  db.exec(sqlText);
  return db.export();
}

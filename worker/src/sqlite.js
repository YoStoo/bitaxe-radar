// sql.js (SQLite compiled to WebAssembly) set up for Cloudflare Workers. Only the Worker entry imports this file,
// because Node can't import a .wasm file directly; tests use sql.js's Node build instead (test/sqlite-node.mjs).
//
// Bug we hit: the normal sql.js build checks "am I in Node?" by looking for process.versions.node. Workers now
// HAVE that (Node compatibility), so sql.js tried to read the .wasm with Node's fs module and crashed
// ("__dirname is not defined"). The "browser" build has no Node branch, so it works in a Worker.
import initSqlJs from "sql.js/dist/sql-wasm-browser.js";
import wasmModule from "sql.js/dist/sql-wasm-browser.wasm";
import { wrapSqlJs } from "./sqlwrap.js";

// Bug 2: the browser build then crashed with "Cannot read properties of undefined (reading 'href')". It sees a
// "web worker" (WorkerGlobalScope exists) and reads self.location.href to find its files. Browsers' workers have
// a location; Cloudflare Workers don't. We hand sql.js the .wasm ourselves, so any placeholder URL is fine.
if (!globalThis.location) globalThis.location = new URL("https://worker.invalid/");

let SQL = null;
export async function openDb(bytes, sqlText) {
  if (!SQL) {
    SQL = await initSqlJs({
      // Workers already give us the compiled WebAssembly module; hand it straight to sql.js.
      instantiateWasm(imports, done) { WebAssembly.instantiate(wasmModule, imports).then((inst) => done(inst)); return {}; },
    });
  }
  if (sqlText != null) { const db = new SQL.Database(); db.exec(sqlText); return wrapSqlJs(db); }
  return wrapSqlJs(new SQL.Database(bytes));
}

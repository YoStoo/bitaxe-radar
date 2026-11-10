// Run: node test/history.test.mjs
// The price-history tool end to end, with NO network: Python (collector/price_db.py) builds a small database,
// then the Worker's JS code queries it with sql.js. That also proves the two languages agree on the schema.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { priceHistory, validateHistoryInput, runHistoryTool, loadPricesDb, _resetPricesDb, daysBefore, HISTORY_TOOL, SQL_DAILY_CHEAPEST } from "../src/history.js";
import { ALL_TOOLS, runAgentLoop, handleAsk, _resetMemoryCounts } from "../src/ask.js";
import { openDbNode, sqlToBytes } from "./sqlite-node.mjs";

const COLLECTOR = fileURLToPath(new URL("../../collector", import.meta.url));

const LATEST = {
  generated_at: "2026-11-10T12:00:00Z",
  fx: { EUR_USD: 1.1 },
  models: {
    "bitaxe-gamma": { name: "Bitaxe Gamma (601/602)", chip: "BM1370", hashrate_ths: 1.2, watts: 18 },
    "nerdqaxe-pp": { name: "NerdQaxe++ (4.8 TH/s)", chip: "BM1370", hashrate_ths: 4.8, watts: 72 },
    "avalon-q": { name: "Canaan Avalon Q (90 TH/s)", maker: "Canaan", hashrate_ths: 90, watts: 1674 },
  },
  sellers: { shopa: { name: "Shop A", currency: "USD" }, shopb: { name: "Shop B", currency: "EUR" } },
  offers: [
    { id: "shopa:bitaxe-gamma", model: "bitaxe-gamma", seller: "shopa", price: 99, currency: "USD", in_stock: true, stale: false, checked_at: "2026-11-10T12:00:00Z" },
    { id: "shopb:bitaxe-gamma", model: "bitaxe-gamma", seller: "shopb", price: 100, currency: "EUR", in_stock: true, stale: false, checked_at: "2026-11-10T12:00:00Z" },
    { id: "shopa:nerdqaxe-pp", model: "nerdqaxe-pp", seller: "shopa", price: 400, currency: "USD", in_stock: false, stale: false, checked_at: "2026-11-10T12:00:00Z" },
  ],
};
// Gamma at Shop A: $120 (Oct 1) -> $67 (Oct 21, the low) -> $99 today. Shop B (EUR) is never cheapest.
const HISTORY = {
  "shopa:bitaxe-gamma": [
    { t: "2026-09-01T10:00:00Z", price: 150, currency: "USD", in_stock: true },
    { t: "2026-10-11T10:00:00Z", price: 120, currency: "USD", in_stock: true },
    { t: "2026-10-21T10:00:00Z", price: 67, currency: "USD", in_stock: true },
    { t: "2026-10-22T10:00:00Z", price: 50, currency: "USD", in_stock: false },   // out of stock: must NOT count as a low
    { t: "2026-11-01T10:00:00Z", price: 110, currency: "USD", in_stock: true },
  ],
  "shopb:bitaxe-gamma": [{ t: "2026-10-11T10:00:00Z", price: 130, currency: "EUR", in_stock: true }],
  "ghost:unknown-miner": [{ t: "2026-10-11T10:00:00Z", price: 1, currency: "USD", in_stock: true }],   // unknown shop/miner: skipped
};

// Python builds the dump exactly like the collector does, and prints it.
const py = `
import sys, json; sys.path.insert(0, ${JSON.stringify(COLLECTOR)})
import price_db as P
latest, history = json.loads(sys.argv[1]), json.loads(sys.argv[2])
con = P.connect(P.Path("/nonexistent.sql"))
P.upsert_catalog(con, latest); P.add_history(con, history, latest["fx"]); P.add_latest(con, latest)
sys.stdout.write(P.dump_text(con))`;
const dump = execFileSync("python3", ["-c", py, JSON.stringify(LATEST), JSON.stringify(HISTORY)]).toString();
const bytes = await sqlToBytes(dump);
const db = await openDbNode(bytes);

// 1. tool definition and input checks
assert.equal(HISTORY_TOOL.name, "get_price_history");
assert.ok(ALL_TOOLS.some((t) => t.name === "get_price_history"));
assert.deepEqual(HISTORY_TOOL.input_schema.required, ["miner"]);
assert.deepEqual(validateHistoryInput({ miner: " gamma " }).args, { miner: "gamma", days: 30 });
assert.match(validateHistoryInput({ miner: "x", days: 0 }).error, /days/);
assert.match(validateHistoryInput({ miner: "x", days: 1.5 }).error, /days/);
assert.match(validateHistoryInput({ miner: "x", drop: "table" }).error, /Unknown input/);
assert.match(validateHistoryInput({}).error, /miner/);
assert.equal(daysBefore("2026-11-10", 30), "2026-10-11");
assert.equal(daysBefore("2026-03-01", 1), "2026-02-28");
assert.ok(SQL_DAILY_CHEAPEST.includes("?"), "query uses placeholders");

// 2. the 30-day answer
let h = priceHistory(db, LATEST, { miner: "Bitaxe Gamma", days: 30 });
assert.equal(h.id, "bitaxe-gamma");
assert.equal(h.history_ends, "2026-11-10");
assert.deepEqual(h.start, { day: "2026-10-11", usd: 120, shop: "Shop A" });       // $120 beat Shop B's 130 EUR = $143
assert.deepEqual(h.latest, { day: "2026-11-10", usd: 99, shop: "Shop A" });
assert.equal(h.change_usd, -21);
assert.equal(h.change_pct, -17.5);
assert.equal(h.trend, "cheaper");
assert.deepEqual(h.lowest_in_window, { day: "2026-10-21", usd: 67, shop: "Shop A" });   // the $50 out-of-stock row is ignored
assert.deepEqual(h.highest_in_window, { day: "2026-10-11", usd: 120, shop: "Shop A" });
assert.deepEqual(h.all_time_low, { day: "2026-10-21", usd: 67, shop: "Shop A" });
assert.deepEqual(h.by_shop.map((s) => [s.shop, s.days_cheapest]), [["Shop A", 4], ["Shop B", 0]]);
assert.equal(h.by_shop[1].lowest_usd, 110);   // today's 100 EUR x 1.1
assert.equal(h.days_with_price, 4);

// 3. a longer window reaches the September price; all-time low is unchanged
h = priceHistory(db, LATEST, { miner: "bitaxe-gamma", days: 90 });
assert.deepEqual(h.start, { day: "2026-09-01", usd: 150, shop: "Shop A" });
assert.equal(h.change_usd, -51);

// 4. no in-stock history, unknown miner, ambiguous name
assert.match(priceHistory(db, LATEST, { miner: "nerdqaxe-pp", days: 30 }).note, /No in-stock price/);
assert.match(priceHistory(db, LATEST, { miner: "Antminer S21", days: 30 }).error, /No single miner/);

// 5. "SQL injection" attempt in the miner name: treated as a name, finds nothing, database unharmed
assert.match(priceHistory(db, LATEST, { miner: "x'; DROP TABLE price_snapshots; --", days: 30 }).error, /No single miner/);
assert.equal(db.all("SELECT COUNT(*) AS n FROM price_snapshots", [])[0].n, 9);   // 6 + 2 Gamma rows, 1 NerdQaxe row, ghost skipped

// 6. runHistoryTool: loads the db over fetch (cached), reports errors as is_error tool results
let fetches = 0;
globalThis.fetch = async (url) => {
  const u = new URL(url);
  if (u.pathname === "/prices.db") { fetches++; return new Response(bytes); }
  if (u.pathname === "/prices.sql") { fetches++; return new Response(dump); }
  if (u.pathname === "/missing.db") return new Response("nope", { status: 404 });
  throw new Error("unexpected fetch " + url);
};
_resetPricesDb();
const ctx = { env: { SITE_URL: "https://site.example" }, latest: LATEST, openDb: openDbNode };
let r = await runHistoryTool(ctx, { id: "tu1", name: "get_price_history", input: { miner: "gamma" } });
assert.equal(r.result.tool_use_id, "tu1");
assert.equal(r.result.is_error, undefined);
assert.equal(JSON.parse(r.result.content).trend, "cheaper");
assert.deepEqual(r.log, { name: "get_price_history", input: { miner: "gamma" }, ok: true });
await runHistoryTool(ctx, { id: "tu2", name: "get_price_history", input: { miner: "gamma", days: 7 } });
assert.equal(fetches, 1, "database cached between calls");
r = await runHistoryTool(ctx, { id: "tu3", name: "get_price_history", input: { miner: "gamma", days: 9999 } });
assert.equal(r.result.is_error, true);
_resetPricesDb();
r = await runHistoryTool({ ...ctx, env: { PRICES_DB_URL: "https://site.example/prices.sql" } }, { id: "tu3b", name: "get_price_history", input: { miner: "gamma" } });
assert.equal(JSON.parse(r.result.content).change_usd, -21, "SQL text copy gives the same answer as the .db file");
_resetPricesDb();
r = await runHistoryTool({ ...ctx, env: { PRICES_DB_URL: "https://site.example/missing.db" } }, { id: "tu4", name: "get_price_history", input: { miner: "gamma" } });
assert.equal(r.result.is_error, true);
assert.match(JSON.parse(r.result.content).error, /unavailable/);
r = await runHistoryTool({ ...ctx, openDb: null }, { id: "tu5", name: "get_price_history", input: { miner: "gamma" } });
assert.equal(r.result.is_error, true);
_resetPricesDb();
await assert.rejects(loadPricesDb({ PRICES_DB_URL: "https://site.example/missing.db" }, openDbNode), /404/);

// 7. through the agent loop: Claude asks for history, gets SQL results, then responds
const DATA_JS = "window.RADAR = " + JSON.stringify({ latest: LATEST, history: {} }) + ";";
const u = { input_tokens: 500, output_tokens: 40 };
let script = [], claudeBodies = [];
globalThis.fetch = async (url, init = {}) => {
  const p = new URL(url);
  if (p.pathname === "/data.js") return new Response(DATA_JS);
  if (p.pathname === "/prices.db") return new Response(bytes);
  if (p.host === "api.anthropic.com") { claudeBodies.push(JSON.parse(init.body)); return new Response(JSON.stringify(script.shift())); }
  throw new Error("unexpected fetch " + url);
};
_resetPricesDb(); _resetMemoryCounts();
script = [
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "tuh", name: "get_price_history", input: { miner: "bitaxe-gamma", days: 30 } }] },
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "tur", name: "respond", input: { working: "120 -> 99", answer: "Yes. The Bitaxe Gamma fell from $120 on Oct 11 to $99 today.", models_mentioned: ["bitaxe-gamma"], confidence: "high", in_data: true } }] },
];
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
const env = { ANTHROPIC_API_KEY: "test", SITE_URL: "https://site.example" };
const resp = await handleAsk(new Request("https://w.example/ask", { method: "POST", body: JSON.stringify({ question: "Has the Gamma gotten cheaper this month?" }) }), env, json, { openDb: openDbNode });
const body = await resp.json();
assert.equal(resp.status, 200);
assert.equal(body.ok, true);
assert.deepEqual(body.tools_used.map((t) => [t.name, t.ok]), [["get_price_history", true]]);
const sent = claudeBodies[1].messages.at(-1).content[0];
assert.equal(sent.type, "tool_result");
assert.equal(JSON.parse(sent.content).change_usd, -21);
assert.ok(claudeBodies[0].tools.some((t) => t.name === "get_price_history"));

// 8. without a database adapter (e.g. an old caller), the loop still answers; the tool reports an error
_resetMemoryCounts();
script = [
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "tuh2", name: "get_price_history", input: { miner: "bitaxe-gamma" } }] },
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "tur2", name: "respond", input: { working: "", answer: "History isn't available right now.", models_mentioned: [], confidence: "low", in_data: false } }] },
];
const loop = await runAgentLoop(env, { question: "x", systemPrompt: "r", latest: LATEST });
assert.deepEqual(loop.toolsUsed.map((t) => t.ok), [false]);
assert.equal(loop.answer.answer, "History isn't available right now.");

console.log("history tests: all passed");

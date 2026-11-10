// get_price_history: answers "has it gotten cheaper?" with a real SQL query.
//
// The data lives in a SQLite database (data/prices.sql in git -> site/prices.db on the website; see docs/SQL.md).
// The Worker downloads that file and runs SQL on it with sql.js (SQLite compiled to WebAssembly).
// Every query uses "?" placeholders ("parameters"): the miner id is passed separately from the SQL text,
// so nothing Claude or a visitor types can ever change the SQL itself (no "SQL injection").
//
// `db` here is anything with  all(sql, params) -> [row objects]. In the Worker that's sql.js (src/sqlite.js);
// in tests it's sql.js running in Node. Swapping to Cloudflare D1 later would only change that one adapter.

import { resolveMiner } from "./tools.js";

export const HISTORY_DEFAULT_DAYS = 30;
export const HISTORY_MAX_DAYS = 365;
const MAX_POINTS = 8;   // keep the tool result small: a few dated points, not every day

export const HISTORY_TOOL = {
  name: "get_price_history",
  description: "Price HISTORY for ONE miner from our SQL price database (one reading per shop per day since mid-October 2026). " +
    "Use for 'has it gotten cheaper', 'price this month / last N days', 'lowest price ever', 'is now a good time', " +
    "'which shop is usually cheapest'. Returns the cheapest in-stock USD price at the start and end of the window, " +
    "the change, the lowest and highest, the all-time low, and each shop's lowest. For TODAY's price use get_miner.",
  strict: true,
  input_schema: {
    type: "object",
    properties: {
      miner: { type: "string", description: "Miner id (e.g. bitaxe-gamma) or name (e.g. Bitaxe Gamma)." },
      days: { type: "integer", description: `How many days back to look, 1-${HISTORY_MAX_DAYS}. Default ${HISTORY_DEFAULT_DAYS} ("this month" = 30).` },
    },
    required: ["miner"],
    additionalProperties: false,
  },
};

export function validateHistoryInput(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return { error: "Input must be an object." };
  const extra = Object.keys(input).filter((k) => !(k in HISTORY_TOOL.input_schema.properties));
  if (extra.length) return { error: `Unknown input(s): ${extra.join(", ")}.` };
  if (typeof input.miner !== "string" || !input.miner.trim() || input.miner.length > 80) return { error: "miner must be a miner id or name." };
  const days = input.days == null ? HISTORY_DEFAULT_DAYS : input.days;
  if (!Number.isInteger(days) || days < 1 || days > HISTORY_MAX_DAYS) return { error: `days must be a whole number from 1 to ${HISTORY_MAX_DAYS}.` };
  return { args: { miner: input.miner.trim(), days } };
}

// ---------- the SQL (shown in docs/SQL.md too) ----------
// The cheapest in-stock price for each day, and the shop that had it.
// SQLite rule worth knowing: with MIN() in the SELECT, the other plain columns (shop) come from the SAME row
// that had the minimum. That's a SQLite feature; Postgres would need a window function for this.
export const SQL_DAILY_CHEAPEST = `
SELECT s.day, MIN(s.price_usd) AS usd, r.name AS shop
FROM price_snapshots s
JOIN offers o    ON o.id = s.offer_id
JOIN retailers r ON r.id = o.retailer_id
WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL AND s.day >= ?
GROUP BY s.day
ORDER BY s.day`;

export const SQL_ALL_TIME_LOW = `
SELECT s.day, s.price_usd AS usd, r.name AS shop
FROM price_snapshots s
JOIN offers o    ON o.id = s.offer_id
JOIN retailers r ON r.id = o.retailer_id
WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL
ORDER BY s.price_usd ASC, s.day ASC
LIMIT 1`;

// Each shop's lowest and highest in-stock price, and on how many days it was THE cheapest shop.
// The inner SELECT is a "correlated subquery": it runs once per row, finding that day's cheapest price.
export const SQL_BY_SHOP = `
SELECT r.name AS shop, MIN(s.price_usd) AS lowest_usd, MAX(s.price_usd) AS highest_usd, COUNT(*) AS days_in_stock,
  SUM(s.price_usd = (
    SELECT MIN(s2.price_usd) FROM price_snapshots s2 JOIN offers o2 ON o2.id = s2.offer_id
    WHERE o2.miner_id = o.miner_id AND s2.in_stock = 1 AND s2.day = s.day)) AS days_cheapest
FROM price_snapshots s
JOIN offers o    ON o.id = s.offer_id
JOIN retailers r ON r.id = o.retailer_id
WHERE o.miner_id = ? AND s.in_stock = 1 AND s.price_usd IS NOT NULL AND s.day >= ?
GROUP BY r.id
ORDER BY days_cheapest DESC, lowest_usd ASC`;

export const SQL_RANGE = `SELECT MIN(day) AS first_day, MAX(day) AS last_day FROM price_snapshots`;

const r2 = (x) => (typeof x === "number" && isFinite(x) ? Math.round(x * 100) / 100 : null);

// "2026-11-10" minus N days -> "2026-10-11". Pure date math in UTC (no time zones to trip on).
export function daysBefore(day, n) {
  const d = new Date(day + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

// Keep the first, last and lowest points plus evenly spaced ones in between (max MAX_POINTS).
function samplePoints(rows) {
  if (rows.length <= MAX_POINTS) return rows;
  const keep = new Set([0, rows.length - 1]);
  let lo = 0;
  rows.forEach((r, i) => { if (r.usd < rows[lo].usd) lo = i; });
  keep.add(lo);
  for (let k = 1; keep.size < MAX_POINTS && k < MAX_POINTS; k++) keep.add(Math.round((k * (rows.length - 1)) / (MAX_POINTS - 1)));
  return [...keep].sort((a, b) => a - b).map((i) => rows[i]);
}

export function priceHistory(db, latest, args) {
  const hit = resolveMiner(latest, args.miner);
  if (!hit.id) return { error: `No single miner matches "${args.miner}".`, did_you_mean: (hit.candidates || []).map((id) => ({ id, name: latest.models[id].name })) };
  const id = hit.id;
  const range = db.all(SQL_RANGE, [])[0] || {};
  if (!range.last_day) return { error: "The price history database is empty." };
  // "Today" = the newest day in the database (not the clock), so answers match the data we actually have.
  const since = daysBefore(range.last_day, args.days);
  const daily = db.all(SQL_DAILY_CHEAPEST, [id, since]).map((r) => ({ day: r.day, usd: r2(r.usd), shop: r.shop }));
  const base = { id, name: latest.models[id].name, window_days: args.days, history_starts: range.first_day, history_ends: range.last_day };
  if (!daily.length) return { ...base, note: "No in-stock price recorded for this miner in that window." };
  const first = daily[0], last = daily[daily.length - 1];
  const lowest = daily.reduce((a, b) => (b.usd < a.usd ? b : a));
  const highest = daily.reduce((a, b) => (b.usd > a.usd ? b : a));
  const change = r2(last.usd - first.usd);
  const low = db.all(SQL_ALL_TIME_LOW, [id])[0];
  return {
    ...base,
    window_start: since,
    start: first, latest: last,
    change_usd: change,
    change_pct: first.usd ? r2((100 * change) / first.usd) : null,
    trend: Math.abs(change) < 0.01 ? "flat" : change < 0 ? "cheaper" : "pricier",
    lowest_in_window: lowest, highest_in_window: highest,
    all_time_low: low ? { day: low.day, usd: r2(low.usd), shop: low.shop } : null,
    days_with_price: daily.length,
    by_shop: db.all(SQL_BY_SHOP, [id, since]).map((r) => ({ shop: r.shop, days_cheapest: r.days_cheapest, lowest_usd: r2(r.lowest_usd),
      highest_usd: r2(r.highest_usd), days_in_stock: r.days_in_stock })),
    points: samplePoints(daily),
    note: "Prices are the cheapest in-stock listing per day, approximate USD. 'latest' is the newest day in the history, which can lag the live price by a few hours.",
  };
}

// ---------- loading the database file (cached per Worker copy for 10 minutes) ----------
let cached = null;   // { url, at, db }
export async function loadPricesDb(env, openDb, now = Date.now()) {
  const url = env.PRICES_DB_URL || (env.SITE_URL || "https://bitaxeradar.com") + "/prices.db";
  if (cached && cached.url === url && now - cached.at < 10 * 60 * 1000) return cached.db;
  const r = await fetch(url, { cf: { cacheTtl: 600 } });
  if (!r.ok) throw new Error("prices.db HTTP " + r.status);
  // Two file kinds: a real SQLite file (.db, from the website), or the SQL text copy (.sql, e.g. straight from
  // GitHub for a test Worker). openDb(bytes) or openDb(null, sqlText) builds the same database either way.
  const db = url.endsWith(".sql") ? await openDb(null, await r.text()) : await openDb(new Uint8Array(await r.arrayBuffer()));
  cached = { url, at: now, db };
  return db;
}
export function _resetPricesDb() { cached = null; }   // for tests

// Run one get_price_history tool_use block -> { result, log }, same shape as runTool() in tools.js.
export async function runHistoryTool(ctx, block) {
  const v = validateHistoryInput(block.input);
  let out, isError = false;
  if (v.error) { out = { error: v.error }; isError = true; }
  else {
    try {
      if (!ctx.openDb) throw new Error("no database adapter");
      const db = await loadPricesDb(ctx.env || {}, ctx.openDb);
      out = priceHistory(db, ctx.latest, v.args);
      isError = !!out.error;
    } catch (e) {
      console.error("history tool failed", e && e.message);
      out = { error: "Price history is unavailable right now. Answer from today's prices (get_miner) and say history isn't available." };
      isError = true;
    }
  }
  return {
    result: { type: "tool_result", tool_use_id: block.id, content: JSON.stringify(out), ...(isError ? { is_error: true } : {}) },
    log: { name: block.name, input: block.input, ok: !isError },
  };
}

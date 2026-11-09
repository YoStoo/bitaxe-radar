// Tools Claude can call for "Ask Bitaxe Radar".
//
// A "tool" is a small function in OUR code that Claude may ask us to run. Claude never runs code itself:
// it replies "please run search_miners with these inputs" (a tool_use block), we run it here over the
// live data.js copy, and send the result back (a tool_result block). No new outside calls happen here.
//
// Each tool has three parts:
//   name         - what Claude calls it
//   description  - plain words telling Claude WHEN to use it (Claude picks tools from these)
//   input_schema - the "tool schema": the exact inputs allowed (JSON Schema)
// `strict: true` makes the API force Claude's inputs to match the schema's types. The API's strict mode
// can't check number ranges (min/max) or list lengths beyond 0/1, so validateToolInput() checks those here.

export const MAX_SEARCH_LIMIT = 10;
const SORTS = ["price", "price_per_th", "efficiency", "hashrate"];
const ORDERS = ["asc", "desc"];
// "Natural" direction for each sort, used when Claude doesn't say: cheapest, cheapest per TH, fewest J/TH, most TH/s.
const DEFAULT_ORDER = { price: "asc", price_per_th: "asc", efficiency: "asc", hashrate: "desc" };

export const TOOLS = [
  {
    name: "search_miners",
    description: "Find and rank miners from the live Bitaxe Radar price data. Use for cheapest / most expensive / " +
      "best value / most efficient / most powerful questions, budgets, and brand filters. Returns a short ranked list " +
      "with each miner's cheapest in-stock price. Prices are approximate USD.",
    strict: true,
    input_schema: {
      type: "object",
      properties: {
        sort_by: { type: "string", enum: SORTS, description: "price = cheapest in-stock price; price_per_th = USD per TH/s; efficiency = J/TH (lower uses less power per hash); hashrate = TH/s." },
        order: { type: "string", enum: ORDERS, description: "asc or desc. Default: price/price_per_th/efficiency asc (best first), hashrate desc (most first). Use price desc for 'most expensive'." },
        max_price: { type: "number", description: "Only miners whose cheapest in-stock price is at or under this many USD." },
        min_hashrate_th: { type: "number", description: "Only miners with at least this many TH/s." },
        brand: { type: "string", description: "Brand or family word, e.g. Bitaxe, NerdQaxe, Canaan, Heatbit." },
        in_stock_only: { type: "boolean", description: "Default true. Set false to include miners with no in-stock listing." },
        limit: { type: "integer", description: `How many results, 1-${MAX_SEARCH_LIMIT}. Default 5.` },
      },
      required: ["sort_by"],
      additionalProperties: false,
    },
  },
  {
    name: "get_miner",
    description: "Full details for ONE miner: specs, every shop listing with price and stock, and a short note. " +
      "Use when the visitor asks about a specific miner (price, where to buy, why it costs what it does).",
    strict: true,
    input_schema: {
      type: "object",
      properties: {
        miner: { type: "string", description: "Miner id (e.g. bitaxe-gamma) or name (e.g. Bitaxe Gamma, NerdQaxe++)." },
      },
      required: ["miner"],
      additionalProperties: false,
    },
  },
  {
    name: "compare_miners",
    description: "Side-by-side specs and cheapest in-stock price for 2 to 4 miners. Use for 'X vs Y' or 'compare' questions.",
    strict: true,
    input_schema: {
      type: "object",
      properties: {
        miners: { type: "array", items: { type: "string" }, description: "2 to 4 miner ids or names." },
      },
      required: ["miners"],
      additionalProperties: false,
    },
  },
];

// ---------- helpers over the live data ----------
const round = (x, d = 2) => (typeof x === "number" && isFinite(x) ? Number(x.toFixed(d)) : null);
const norm = (s) => String(s || "").toLowerCase().replace(/\([^)]*\)/g, " ").replace(/[^a-z0-9+]+/g, " ").trim();
const usableOffers = (latest, id) => (latest.offers || [])
  .filter((o) => o.model === id && o.in_stock && !o.stale && typeof o.price_usd_approx === "number")
  .sort((a, b) => a.price_usd_approx - b.price_usd_approx);
const shopName = (latest, s) => latest.sellers?.[s]?.name || s;

// One compact row per miner: what search and compare return.
export function minerRow(latest, id) {
  const m = latest.models[id];
  const usable = usableOffers(latest, id);
  const best = usable[0];
  const th = round(m.hashrate_ths);
  const price = best ? round(best.price_usd_approx) : null;
  return {
    id, name: m.name, brand: m.maker || m.name.split(" ")[0],
    th_s: th, watts: m.watts ?? null, j_per_th: th && m.watts ? round(m.watts / m.hashrate_ths, 1) : null,
    cheapest_usd: price, at_shop: best ? shopName(latest, best.seller) : null,
    usd_per_th: price != null && th ? round(price / th, 1) : null,
    in_stock_listings: usable.length,
  };
}

// Turn "Bitaxe Gamma", "gamma", "bitaxe-gamma" or "NerdQaxe++" into ONE model id (or a list of close matches).
export function resolveMiner(latest, query) {
  const ids = Object.keys(latest.models || {});
  const q = String(query || "").trim().toLowerCase();
  if (!q) return { candidates: [] };
  if (latest.models[q]) return { id: q };
  const nq = norm(q);
  const exact = ids.filter((id) => norm(latest.models[id].name) === nq || norm(id.replace(/-/g, " ")) === nq);
  if (exact.length === 1) return { id: exact[0] };
  // Every query word must appear in the name or id ("gamma" -> all Gamma models).
  const words = nq.split(" ").filter(Boolean);
  const hits = ids.filter((id) => {
    const hay = norm(latest.models[id].name) + " " + id.replace(/-/g, " ");
    return words.every((w) => hay.split(" ").includes(w));
  });
  if (hits.length === 1) return { id: hits[0] };
  // Prefer the shortest name among matches if one is a clean prefix ("Bitaxe Gamma" over "Bitaxe Gamma Duo").
  const base = hits.find((id) => norm(latest.models[id].name).split(" ").length === words.length);
  if (base) return { id: base };
  return { candidates: hits.slice(0, 6) };
}

// ---------- step 1: check Claude's inputs (never trust them, even with strict mode) ----------
// Returns { args } on success or { error } with a message Claude can read and fix.
export function validateToolInput(name, input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return { error: "Input must be an object." };
  const tool = TOOLS.find((t) => t.name === name);
  if (!tool) return { error: `Unknown tool "${name}". Available: ${TOOLS.map((t) => t.name).join(", ")}.` };
  const extra = Object.keys(input).filter((k) => !(k in tool.input_schema.properties));
  if (extra.length) return { error: `Unknown input(s): ${extra.join(", ")}.` };

  if (name === "search_miners") {
    const sort_by = String(input.sort_by || "").toLowerCase();   // enum casing isn't guaranteed by the API
    if (!SORTS.includes(sort_by)) return { error: `sort_by must be one of ${SORTS.join(", ")}.` };
    const order = input.order == null ? DEFAULT_ORDER[sort_by] : String(input.order).toLowerCase();
    if (!ORDERS.includes(order)) return { error: "order must be asc or desc." };
    for (const k of ["max_price", "min_hashrate_th"]) {
      if (input[k] != null && (typeof input[k] !== "number" || !isFinite(input[k]) || input[k] < 0)) return { error: `${k} must be a number 0 or more.` };
    }
    if (input.brand != null && (typeof input.brand !== "string" || input.brand.length > 40)) return { error: "brand must be a short text." };
    if (input.in_stock_only != null && typeof input.in_stock_only !== "boolean") return { error: "in_stock_only must be true or false." };
    const limit = input.limit == null ? 5 : input.limit;
    if (!Number.isInteger(limit) || limit < 1 || limit > MAX_SEARCH_LIMIT) return { error: `limit must be a whole number from 1 to ${MAX_SEARCH_LIMIT}.` };
    return { args: { sort_by, order, max_price: input.max_price ?? null, min_hashrate_th: input.min_hashrate_th ?? null,
      brand: input.brand?.trim() || null, in_stock_only: input.in_stock_only ?? true, limit } };
  }
  if (name === "get_miner") {
    if (typeof input.miner !== "string" || !input.miner.trim() || input.miner.length > 80) return { error: "miner must be a miner id or name." };
    return { args: { miner: input.miner.trim() } };
  }
  // compare_miners
  if (!Array.isArray(input.miners) || input.miners.length < 2 || input.miners.length > 4) return { error: "miners must list 2 to 4 miner ids or names." };
  if (input.miners.some((m) => typeof m !== "string" || !m.trim() || m.length > 80)) return { error: "Each miner must be an id or name." };
  return { args: { miners: input.miners.map((m) => m.trim()) } };
}

// ---------- step 2: the tools themselves ----------
function searchMiners(latest, a) {
  const sortKey = { price: "cheapest_usd", price_per_th: "usd_per_th", efficiency: "j_per_th", hashrate: "th_s" }[a.sort_by];
  const brand = a.brand ? norm(a.brand) : null;
  let rows = Object.keys(latest.models || {}).map((id) => minerRow(latest, id));
  if (a.in_stock_only) rows = rows.filter((r) => r.cheapest_usd != null);
  if (a.max_price != null) rows = rows.filter((r) => r.cheapest_usd != null && r.cheapest_usd <= a.max_price);
  if (a.min_hashrate_th != null) rows = rows.filter((r) => r.th_s != null && r.th_s >= a.min_hashrate_th);
  if (brand) rows = rows.filter((r) => norm(r.brand + " " + r.name + " " + r.id).includes(brand));
  const dir = a.order === "desc" ? -1 : 1;
  // Rows missing the sort value (no price, unknown watts) always go last, whatever the direction.
  rows.sort((x, y) => {
    const vx = x[sortKey], vy = y[sortKey];
    if (vx == null || vy == null) return (vx == null) - (vy == null);
    return (vx - vy) * dir;
  });
  return { data_updated: latest.generated_at, sorted_by: `${a.sort_by} ${a.order}`, total_matches: rows.length, results: rows.slice(0, a.limit) };
}

function getMiner(latest, a) {
  const hit = resolveMiner(latest, a.miner);
  if (!hit.id) return { error: `No single miner matches "${a.miner}".`, did_you_mean: (hit.candidates || []).map((id) => ({ id, name: latest.models[id].name })) };
  const id = hit.id, m = latest.models[id];
  const listings = (latest.offers || []).filter((o) => o.model === id)
    .sort((x, y) => (y.in_stock && !y.stale) - (x.in_stock && !x.stale) || (x.price_usd_approx ?? Infinity) - (y.price_usd_approx ?? Infinity))
    .map((o) => ({ shop: shopName(latest, o.seller), usd: round(o.price_usd_approx), in_stock: !!o.in_stock && !o.stale,
      config: o.config || null, ship_note: o.ship_note || null }));
  // No URLs on purpose: the site adds links itself, and URLs in tool results tempt Claude to paste them.
  return { data_updated: latest.generated_at, ...minerRow(latest, id), chip: m.chip || null, kind: m.kind || null,
    heat_watts: m.heat_watts ?? null, note: m.note || null, listings };
}

function compareMiners(latest, a) {
  const rows = [], unknown = [];
  for (const q of a.miners) {
    const hit = resolveMiner(latest, q);
    if (hit.id && !rows.some((r) => r.id === hit.id)) rows.push({ ...minerRow(latest, hit.id), chip: latest.models[hit.id].chip || null });
    else if (!hit.id) unknown.push(q);
  }
  if (rows.length < 2) return { error: "Need at least 2 known miners to compare.", not_found: unknown };
  return { data_updated: latest.generated_at, miners: rows, not_found: unknown };
}

const IMPL = { search_miners: searchMiners, get_miner: getMiner, compare_miners: compareMiners };

// ---------- step 3: run one tool_use block -> one tool_result block ----------
// is_error: true tells Claude "that call failed, here's why", so it can fix its inputs and try again.
export function runTool(latest, block) {
  const v = validateToolInput(block.name, block.input);
  let out, isError = false;
  if (v.error) { out = { error: v.error }; isError = true; }
  else {
    try { out = IMPL[block.name](latest, v.args); isError = !!out.error; }
    catch (e) { out = { error: "Tool failed." }; isError = true; console.error("tool failed", block.name, e && e.message); }
  }
  return {
    result: { type: "tool_result", tool_use_id: block.id, content: JSON.stringify(out), ...(isError ? { is_error: true } : {}) },
    log: { name: block.name, input: block.input, ok: !isError },
  };
}

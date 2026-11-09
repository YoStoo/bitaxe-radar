// Try "Ask Bitaxe Radar" against the REAL Claude API, using the live site data.
// It goes through the exact same code the Worker uses (handleAsk), so what you see here is what visitors get.
//
// Run (from worker/):
//   ANTHROPIC_API_KEY=sk-ant-... node scripts/try_ask.mjs "Cheapest Bitaxe" "+why is it so cheap?"
//   A question starting with "+" is a FOLLOW-UP: it's sent with the previous question + answer as history.
//   ASK_TOOLS=off node scripts/try_ask.mjs ...   -> the old "paste all data in" way, to compare cost.
// The key is read from the environment only. Never paste it into this file or commit it.
import { handleAsk, _resetMemoryCounts } from "../src/ask.js";

if (!process.env.ANTHROPIC_API_KEY) { console.error("Set ANTHROPIC_API_KEY first."); process.exit(1); }

// Wrap fetch so we can add up Claude's token receipts ("usage") for EVERY call a question makes.
const realFetch = globalThis.fetch;
let qUsage = null;
globalThis.fetch = async (url, init) => {
  const r = await realFetch(url, init);
  if (String(url).includes("api.anthropic.com")) {
    const u = (await r.clone().json().catch(() => ({}))).usage || {};
    qUsage.calls++; qUsage.in += u.input_tokens || 0; qUsage.out += u.output_tokens || 0;
  }
  return r;
};

// Haiku 5.5 price per million tokens (USD), for a rough cost estimate. Check anthropic.com/pricing if it changes.
const IN_PER_M = Number(process.env.PRICE_IN_PER_M || 0.10), OUT_PER_M = Number(process.env.PRICE_OUT_PER_M || 0.50);
const env = { ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY, SITE_URL: process.env.SITE_URL || "https://bitaxeradar.com",
  ASK_MODEL: process.env.ASK_MODEL, ASK_TOOLS: process.env.ASK_TOOLS, ASK_DAILY_LIMIT: "1000" };
const json = (obj, status) => new Response(JSON.stringify(obj), { status });

const questions = process.argv.slice(2);
if (!questions.length) questions.push("What's the cheapest Bitaxe in stock right now?");
let tin = 0, tout = 0, tcalls = 0, history = [];
const rows = [];
for (const raw of questions) {
  const followUp = raw.startsWith("+");
  const q = followUp ? raw.slice(1) : raw;
  if (!followUp) history = [];
  _resetMemoryCounts(); qUsage = { calls: 0, in: 0, out: 0 };
  const t0 = Date.now();
  const req = new Request("http://local/ask", { method: "POST", body: JSON.stringify({ question: q, history }) });
  const res = await handleAsk(req, env, json);
  const body = await res.json();
  const ms = Date.now() - t0;
  const cost = (qUsage.in * IN_PER_M + qUsage.out * OUT_PER_M) / 1e6;
  console.log(`\nQ: ${q}${followUp ? "  (follow-up)" : ""}\nHTTP ${res.status}  ${ms} ms  calls ${qUsage.calls}  tokens in ${qUsage.in} out ${qUsage.out}  ~$${cost.toFixed(6)}`);
  console.log(JSON.stringify(body, null, 2));
  rows.push({ q, status: res.status, ms, calls: qUsage.calls, in: qUsage.in, out: qUsage.out, cost, tools: (body.tools_used || []).map((t) => t.name + (t.ok ? "" : "(error)")).join(", ") || "-", answer: body.answer || body.error });
  if (body.ok) history = [...history, { role: "user", content: q }, { role: "assistant", content: body.answer }];
  tin += qUsage.in; tout += qUsage.out; tcalls += qUsage.calls;
}
const cost = (tin * IN_PER_M + tout * OUT_PER_M) / 1e6;
console.log(`\nTOTAL: ${tcalls} Claude calls, tokens in ${tin}, out ${tout}  ~ $${cost.toFixed(5)} (at $${IN_PER_M}/$${OUT_PER_M} per M tokens)`);
if (process.env.ROWS_JSON) (await import("node:fs")).writeFileSync(process.env.ROWS_JSON, JSON.stringify(rows, null, 2));

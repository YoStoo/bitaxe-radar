// Try "Ask Bitaxe Radar" against the REAL Claude API, using the live site data.
// It goes through the exact same code the Worker uses (handleAsk), so what you see here is what visitors get.
//
// Run (from worker/):
//   ANTHROPIC_API_KEY=sk-ant-... node scripts/try_ask.mjs "What's the cheapest Bitaxe in stock?" "Another question"
// The key is read from the environment only. Never paste it into this file or commit it.
import { handleAsk, _resetMemoryCounts } from "../src/ask.js";

if (!process.env.ANTHROPIC_API_KEY) { console.error("Set ANTHROPIC_API_KEY first."); process.exit(1); }

// Wrap fetch so we can print Claude's token receipt ("usage") without changing the Worker code.
const realFetch = globalThis.fetch;
let lastUsage = null;
globalThis.fetch = async (url, init) => {
  const r = await realFetch(url, init);
  if (String(url).includes("api.anthropic.com")) lastUsage = (await r.clone().json().catch(() => ({}))).usage || null;
  return r;
};

// Haiku 5.5 price per million tokens (USD, prompts under 100k tokens), for a rough cost estimate. Check anthropic.com/pricing if it changes.
const IN_PER_M = Number(process.env.PRICE_IN_PER_M || 0.10), OUT_PER_M = Number(process.env.PRICE_OUT_PER_M || 0.50);
const env = { ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY, SITE_URL: process.env.SITE_URL || "https://bitaxeradar.com",
  ASK_MODEL: process.env.ASK_MODEL, ASK_DAILY_LIMIT: "1000" };
const json = (obj, status) => new Response(JSON.stringify(obj), { status });

const questions = process.argv.slice(2);
if (!questions.length) questions.push("What's the cheapest Bitaxe in stock right now?");
let tin = 0, tout = 0;
for (const q of questions) {
  _resetMemoryCounts(); lastUsage = null;
  const req = new Request("http://local/ask", { method: "POST", body: JSON.stringify({ question: q }) });
  const res = await handleAsk(req, env, json);
  const body = await res.json();
  console.log(`\nQ: ${q}\nHTTP ${res.status}`);
  console.log(JSON.stringify(body, null, 2));
  if (lastUsage) { tin += lastUsage.input_tokens || 0; tout += lastUsage.output_tokens || 0;
    console.log(`tokens: in ${lastUsage.input_tokens}, out ${lastUsage.output_tokens}`); }
}
const cost = (tin * IN_PER_M + tout * OUT_PER_M) / 1e6;
console.log(`\nTOTAL tokens: in ${tin}, out ${tout}  ~ $${cost.toFixed(5)} (at $${IN_PER_M}/$${OUT_PER_M} per M tokens)`);

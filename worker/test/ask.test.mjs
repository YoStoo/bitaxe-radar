// Run: node test/ask.test.mjs   (no real API calls: fetch is replaced with a fake)
// "Mocking" = swapping the real internet call for a fake one we control, so tests are free, fast and repeatable.
import assert from "node:assert/strict";
import worker from "../src/index.js";
import { validateQuestion, validateHistory, buildContext, buildClaudeRequest, parseClaudeReply, handleAsk, takeDailySlot,
  _resetMemoryCounts, ANSWER_SCHEMA, SYSTEM_PROMPT, MAX_QUESTION_CHARS, DEFAULT_MODEL,
  MAX_HISTORY_TURNS, MAX_HISTORY_CONTENT, MAX_HISTORY_TOTAL } from "../src/ask.js";

// A tiny fake copy of the site's data (2 miners, 3 shop listings).
const LATEST = {
  generated_at: "2026-11-09T06:28:45Z",
  models: { "bitaxe-gamma": { name: "Bitaxe Gamma", chip: "BM1370", hashrate_ths: 1.2, watts: 18 },
            "nerdqaxe-pp": { name: "NerdQaxe++", chip: "BM1370", hashrate_ths: 4.8, watts: 72 } },
  sellers: { shopa: { name: "Shop A" }, shopb: { name: "Shop B" } },
  offers: [
    { model: "bitaxe-gamma", seller: "shopa", in_stock: true, stale: false, price_usd_approx: 129.99 },
    { model: "bitaxe-gamma", seller: "shopb", in_stock: true, stale: false, price_usd_approx: 99.5 },
    { model: "nerdqaxe-pp", seller: "shopa", in_stock: false, stale: false, price_usd_approx: 300 },
  ],
};
const DATA_JS = "window.RADAR = " + JSON.stringify({ latest: LATEST, history: {} }) + ";\n";
const claudeSays = (obj, extra = {}) => ({ content: [{ type: "text", text: JSON.stringify(obj) }], stop_reason: "end_turn", usage: { input_tokens: 900, output_tokens: 60 }, ...extra });
const GOOD = { working: "gamma rows: 99.5 < 129.99", answer: "The Bitaxe Gamma is $99.50 at Shop B as of the last update.", models_mentioned: ["bitaxe-gamma", "made-up-miner"], confidence: "High", in_data: true };

let claudeReply = claudeSays(GOOD), claudeStatus = 200, claudeCalls = [];
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url);
  if (u.pathname === "/data.js") return new Response(DATA_JS);
  if (u.host === "api.anthropic.com") {
    claudeCalls.push({ headers: init.headers, body: JSON.parse(init.body) });
    return new Response(JSON.stringify(claudeReply), { status: claudeStatus });
  }
  throw new Error("unexpected fetch " + url);
};

const env = { ANTHROPIC_API_KEY: "sk-test", SITE_URL: "https://bitaxeradar.com", ASK_DAILY_LIMIT: "3" };
const PROMPT = "Answer only from <data>.";
const json = (obj, status) => new Response(JSON.stringify(obj), { status });
const ask = (q, e = env, prompt = PROMPT, history) => handleAsk(new Request("https://w.example/ask", { method: "POST", body: JSON.stringify(history ? { question: q, history } : { question: q }) }), e, json, { systemPrompt: prompt });
const read = async (p) => { const r = await p; return { status: r.status, body: await r.json() }; };

// 1. question checks
assert.equal(validateQuestion("  cheapest   miner? ").question, "cheapest miner?");
assert.ok(validateQuestion("").error);
assert.ok(validateQuestion(42).error);
assert.ok(validateQuestion("x".repeat(MAX_QUESTION_CHARS + 1)).error);
assert.ok(validateQuestion("x".repeat(MAX_QUESTION_CHARS)).question);

// 2. context: cheapest in-stock offer wins, out-of-stock is labelled, J/TH is computed
const ctx = buildContext(LATEST);
assert.match(ctx, /bitaxe-gamma \| Bitaxe Gamma \| BM1370 \| 1.2 \| 18 \| 15 \| 99.5 \| Shop B \| 2 \| \/models\/bitaxe-gamma\//);
assert.match(ctx, /nerdqaxe-pp .*\| out of stock \| - \| 0 \|/);
assert.match(ctx, /Data updated: 2026-11-09/);
assert.ok(ctx.indexOf("bitaxe-gamma |") < ctx.indexOf("nerdqaxe-pp |"));   // cheapest in stock first, out of stock last

// 3. request shape: model, JSON schema, question inside <question> tags
const req = buildClaudeRequest("cheapest?", ctx, PROMPT);
assert.equal(req.model, DEFAULT_MODEL);
assert.equal(req.system, PROMPT);
assert.deepEqual(req.output_config.format, { type: "json_schema", schema: ANSWER_SCHEMA });
assert.match(req.messages[0].content, /<data>[\s\S]*<\/data>[\s\S]*<question>cheapest\?<\/question>/);

// 4. reply checks: unknown ids dropped, casing fixed, bad replies rejected
const ids = new Set(Object.keys(LATEST.models));
assert.deepEqual(parseClaudeReply(claudeSays(GOOD), ids).models_mentioned, ["bitaxe-gamma"]);
assert.equal(parseClaudeReply(claudeSays(GOOD), ids).confidence, "high");
assert.equal("working" in parseClaudeReply(claudeSays(GOOD), ids), false);   // scratch notes never reach visitors
assert.equal(parseClaudeReply(claudeSays(GOOD, { stop_reason: "max_tokens" }), ids), null);
assert.equal(parseClaudeReply(claudeSays(GOOD, { stop_reason: "refusal" }), ids), null);
assert.equal(parseClaudeReply({ content: [{ type: "text", text: "not json" }] }, ids), null);
assert.equal(parseClaudeReply(claudeSays({ ...GOOD, in_data: "yes" }), ids), null);
assert.equal(parseClaudeReply(claudeSays({ ...GOOD, confidence: "very" }), ids), null);

// 5. full route, happy path
_resetMemoryCounts();
let r = await read(ask("What's the cheapest Bitaxe Gamma?"));
assert.equal(r.status, 200);
assert.equal(r.body.ok, true);
assert.equal(r.body.in_data, true);
assert.deepEqual(r.body.models_mentioned, ["bitaxe-gamma"]);
assert.equal(r.body.data_updated, LATEST.generated_at);
assert.equal(claudeCalls.at(-1).headers["x-api-key"], "sk-test");
assert.ok(claudeCalls.at(-1).headers["anthropic-version"]);

// 6. "I don't know" answers pass through with in_data=false
claudeReply = claudeSays({ answer: "I don't know; the data doesn't cover shipping times.", models_mentioned: [], confidence: "low", in_data: false });
r = await read(ask("How fast does Shop A ship?"));
assert.equal(r.status, 200);
assert.equal(r.body.in_data, false);

// 7. daily cap (limit 3): third question is the last allowed, fourth is blocked without calling Claude
claudeReply = claudeSays(GOOD);
assert.equal((await read(ask("q3"))).status, 200);
const before = claudeCalls.length;
r = await read(ask("q4"));
assert.equal(r.status, 429);
assert.equal(claudeCalls.length, before);

// 8. KV-backed cap uses one key per day
_resetMemoryCounts();
const store = new Map();
const kvEnv = { ASK_DAILY_LIMIT: "1", ASK_KV: { get: async (k) => store.get(k) ?? null, put: async (k, v) => store.set(k, v) } };
assert.equal(await takeDailySlot(kvEnv, new Date("2026-11-09T12:00:00Z")), true);
assert.equal(await takeDailySlot(kvEnv, new Date("2026-11-09T13:00:00Z")), false);
assert.equal(store.get("asks:2026-11-09"), "1");

// 9. errors never leak details; bad input is a 400; not set up is a 503
_resetMemoryCounts();
claudeStatus = 500;
r = await read(ask("anything"));
assert.equal(r.status, 502);
assert.doesNotMatch(JSON.stringify(r.body), /sk-test|HTTP 500/);
claudeStatus = 200;
assert.equal((await read(ask(""))).status, 400);
assert.equal((await read(ask("hi", env, ""))).status, 503);                       // empty system prompt
assert.equal((await read(ask("hi", { ...env, ANTHROPIC_API_KEY: "" }))).status, 503);  // no key

// 10. through the real Worker router: /ask exists, foreign websites are blocked
const viaWorker = (origin) => worker.fetch(new Request("https://w.example/ask", { method: "POST", headers: { "Content-Type": "application/json", Origin: origin }, body: '{"question":"hi"}' }), env);
assert.equal((await viaWorker("https://evil.example")).status, 403);
_resetMemoryCounts();
claudeReply = claudeSays(GOOD); claudeCalls = [];
assert.equal((await viaWorker("https://bitaxeradar.com")).status, 200);   // real SYSTEM_PROMPT is set
assert.equal(claudeCalls.at(-1).body.system, SYSTEM_PROMPT);              // and it's what Claude receives
assert.match(SYSTEM_PROMPT, /Never guess a price/);
assert.match(SYSTEM_PROMPT, /in_data to false/);
assert.match(SYSTEM_PROMPT, /never put URLs or page paths/i);
assert.ok(SYSTEM_PROMPT.includes("/models/"), "prompt forbids raw /models/ paths");


// 11. history: validate, forward, drop malformed, trim oversize
assert.deepEqual(validateHistory(null), []);
assert.deepEqual(validateHistory("nope"), []);
assert.deepEqual(validateHistory([{ role: "assistant", content: "orphan" }]), []); // must start with user
assert.deepEqual(
  validateHistory([
    { role: "user", content: "cheapest?" },
    { role: "assistant", content: "Gamma at $99" },
    { role: "user", content: "why?" }, // trailing user dropped so new question can append
  ]),
  [{ role: "user", content: "cheapest?" }, { role: "assistant", content: "Gamma at $99" }]
);
assert.deepEqual(
  validateHistory([
    { role: "user", content: "a" },
    { role: "bot", content: "bad role" },
    { role: "assistant", content: "ok" },
    { role: "assistant", content: "dup role skipped" },
    { role: "user", content: "" },
    { role: "user", content: "next" },
  ]),
  [{ role: "user", content: "a" }, { role: "assistant", content: "ok" }]
);
const long = "y".repeat(MAX_HISTORY_CONTENT + 50);
assert.equal(validateHistory([{ role: "user", content: long }, { role: "assistant", content: "a" }])[0].content.length, MAX_HISTORY_CONTENT);
const many = [];
for (let i = 0; i < 10; i++) many.push({ role: i % 2 ? "assistant" : "user", content: "m" + i });
assert.ok(validateHistory(many).length <= MAX_HISTORY_TURNS);
assert.equal(validateHistory(many).length % 2, 0); // ends on assistant after trim rules

_resetMemoryCounts();
claudeReply = claudeSays(GOOD); claudeCalls = [];
const hist = [
  { role: "user", content: "Most expensive miner" },
  { role: "assistant", content: "The Avalon Q is about $1398." },
];
r = await read(ask("Why is it so expensive?", env, PROMPT, hist));
assert.equal(r.status, 200);
const sent = claudeCalls.at(-1).body.messages;
assert.equal(sent.length, 3); // 2 history + current
assert.equal(sent[0].role, "user");
assert.equal(sent[0].content, "Most expensive miner");
assert.equal(sent[1].role, "assistant");
assert.match(sent[2].content, /<question>Why is it so expensive\?<\/question>/);

// malformed history is ignored (still answers the new question)
_resetMemoryCounts();
claudeCalls = [];
r = await read(ask("hi", env, PROMPT, [{ role: "nope", content: 1 }, "x"]));
assert.equal(r.status, 200);
assert.equal(claudeCalls.at(-1).body.messages.length, 1); // only the new question

// oversize history trimmed before send
_resetMemoryCounts();
claudeCalls = [];
const fat = [];
for (let i = 0; i < 20; i++) fat.push({ role: i % 2 ? "assistant" : "user", content: "turn " + i + " " + "z".repeat(200) });
r = await read(ask("follow up?", env, PROMPT, fat));
assert.equal(r.status, 200);
assert.ok(claudeCalls.at(-1).body.messages.length - 1 <= MAX_HISTORY_TURNS);
const histChars = claudeCalls.at(-1).body.messages.slice(0, -1).reduce((n, m) => n + m.content.length, 0);
assert.ok(histChars <= MAX_HISTORY_TOTAL);

assert.match(SYSTEM_PROMPT, /Follow-ups/i);


console.log("ask tests: all passed");

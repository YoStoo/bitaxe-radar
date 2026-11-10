// Run: node test/tools.test.mjs   (no real API calls: Claude is replaced with a scripted fake)
// Each test scripts what the fake Claude says on each call, then checks what our agent loop did.
import assert from "node:assert/strict";
import { handleAsk, groundedInTools, runAgentLoop, buildToolRequest, contextModePrompt, RESPOND_TOOL, _resetMemoryCounts, MAX_TOOL_ROUNDS, SYSTEM_PROMPT, ANSWER_SCHEMA } from "../src/ask.js";
import { TOOLS, validateToolInput, runTool, resolveMiner, MAX_SEARCH_LIMIT } from "../src/tools.js";

const LATEST = {
  generated_at: "2026-11-09T06:28:45Z",
  models: {
    "bitaxe-gamma": { name: "Bitaxe Gamma (601/602)", chip: "BM1370", hashrate_ths: 1.2, watts: 18 },
    "bitaxe-gamma-duo": { name: "Bitaxe Gamma Duo (650)", chip: "BM1370", hashrate_ths: 2.4, watts: 36 },
    "nerdqaxe-pp": { name: "NerdQaxe++ (4.8 TH/s)", chip: "BM1370", hashrate_ths: 4.8, watts: 72 },
    "avalon-q": { name: "Canaan Avalon Q (90 TH/s)", maker: "Canaan", hashrate_ths: 90, watts: 1674, note: "Seller-stated 90 TH/s" },
  },
  sellers: { shopa: { name: "Shop A" }, shopb: { name: "Shop B" } },
  offers: [
    { model: "bitaxe-gamma", seller: "shopa", in_stock: true, stale: false, price_usd_approx: 129.99, url: "https://a.example/g" },
    { model: "bitaxe-gamma", seller: "shopb", in_stock: true, stale: false, price_usd_approx: 67 },
    { model: "bitaxe-gamma-duo", seller: "shopa", in_stock: true, stale: false, price_usd_approx: 199 },
    { model: "nerdqaxe-pp", seller: "shopa", in_stock: true, stale: false, price_usd_approx: 340 },
    { model: "nerdqaxe-pp", seller: "shopb", in_stock: false, stale: false, price_usd_approx: 300 },
    { model: "avalon-q", seller: "shopb", in_stock: true, stale: false, price_usd_approx: 1398 },
  ],
};
const DATA_JS = "window.RADAR = " + JSON.stringify({ latest: LATEST, history: {} }) + ";";
const u = { input_tokens: 500, output_tokens: 40 };
const toolUse = (...calls) => ({ stop_reason: "tool_use", usage: u, content: calls.map(([name, input], i) => ({ type: "tool_use", id: "tu_" + name + i + Math.random().toString(36).slice(2, 6), name, input })) });
// Final answer = a call to the "respond" tool whose input is the answer JSON.
const final = (obj) => ({ stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "tu_respond" + Math.random().toString(36).slice(2, 6), name: "respond", input: obj }] });
const textFinal = (obj) => ({ stop_reason: "end_turn", usage: u, content: [{ type: "text", text: JSON.stringify(obj) }] });
const ANSWER = { working: "gamma 67", answer: "The Bitaxe Gamma is the cheapest at $67 from Shop B.", models_mentioned: ["bitaxe-gamma"], confidence: "high", in_data: true };

// Scripted fake Claude: each call takes the next reply from `script`.
let script = [], calls = [];
globalThis.fetch = async (url, init = {}) => {
  const p = new URL(url);
  if (p.pathname === "/data.js") return new Response(DATA_JS);
  if (p.host === "api.anthropic.com") {
    calls.push(JSON.parse(init.body));
    const next = script.shift();
    if (!next) throw new Error("fake Claude ran out of replies");
    return new Response(JSON.stringify(next), { status: 200 });
  }
  throw new Error("unexpected fetch " + url);
};
const env = { ANTHROPIC_API_KEY: "sk-test", SITE_URL: "https://bitaxeradar.com", ASK_DAILY_LIMIT: "100" };
const json = (obj, status) => new Response(JSON.stringify(obj), { status });
const ask = async (q, history, e = env) => {
  const r = await handleAsk(new Request("https://w.example/ask", { method: "POST", body: JSON.stringify({ question: q, history }) }), e, json);
  return { status: r.status, body: await r.json() };
};
const reset = (s) => { _resetMemoryCounts(); script = s; calls = []; };

// ---- tool definitions: small, named, strict, closed schemas ----
assert.deepEqual(TOOLS.map((t) => t.name), ["search_miners", "get_miner", "compare_miners"]);
for (const t of TOOLS) {
  assert.equal(t.strict, true);
  assert.equal(t.input_schema.additionalProperties, false);
  assert.ok(t.description.length > 40, t.name + " needs a real description");
  assert.doesNotMatch(JSON.stringify(t.input_schema), /"(minimum|maximum|maxItems|minLength|maxLength)"/);   // unsupported in strict mode
}

// ---- input validation ----
assert.ok(validateToolInput("search_miners", { sort_by: "price", limit: 50 }).error);
assert.ok(validateToolInput("search_miners", { sort_by: "price", limit: 0 }).error);
assert.ok(validateToolInput("search_miners", { sort_by: "vibes" }).error);
assert.ok(validateToolInput("search_miners", { sort_by: "price", max_price: -5 }).error);
assert.ok(validateToolInput("search_miners", { sort_by: "price", hack: 1 }).error);
assert.equal(validateToolInput("search_miners", { sort_by: "Price" }).args.sort_by, "price");   // enum casing fixed
assert.equal(validateToolInput("search_miners", { sort_by: "hashrate" }).args.order, "desc");    // natural default
assert.equal(validateToolInput("search_miners", { sort_by: "price", limit: MAX_SEARCH_LIMIT }).args.limit, MAX_SEARCH_LIMIT);
assert.ok(validateToolInput("compare_miners", { miners: ["a"] }).error);
assert.ok(validateToolInput("compare_miners", { miners: ["a", "b", "c", "d", "e"] }).error);
assert.ok(validateToolInput("get_miner", { miner: "" }).error);
assert.ok(validateToolInput("get_miner", null).error);
assert.match(validateToolInput("delete_everything", {}).error, /Unknown tool/);

// ---- name matching ----
assert.equal(resolveMiner(LATEST, "Bitaxe Gamma").id, "bitaxe-gamma");
assert.equal(resolveMiner(LATEST, "the NerdQaxe++").id, undefined);   // extra words -> no guess
assert.equal(resolveMiner(LATEST, "NerdQaxe++").id, "nerdqaxe-pp");
assert.equal(resolveMiner(LATEST, "avalon-q").id, "avalon-q");
assert.equal(resolveMiner(LATEST, "gamma duo").id, "bitaxe-gamma-duo");

// ---- tools over the data ----
const run = (name, input) => { const r = runTool(LATEST, { id: "x", name, input }); return { ...r, out: JSON.parse(r.result.content) }; };
let t = run("search_miners", { sort_by: "price" });
assert.equal(t.out.results[0].id, "bitaxe-gamma");
assert.equal(t.out.results[0].cheapest_usd, 67);
assert.equal(t.out.results[0].at_shop, "Shop B");
t = run("search_miners", { sort_by: "price", order: "desc", limit: 1 });
assert.equal(t.out.results[0].id, "avalon-q");
t = run("search_miners", { sort_by: "price_per_th", max_price: 400 });
assert.deepEqual(t.out.results.map((r) => r.id), ["bitaxe-gamma", "nerdqaxe-pp", "bitaxe-gamma-duo"]);   // $55.8, $70.8, $82.9 per TH; Avalon over budget
t = run("search_miners", { sort_by: "price", brand: "canaan" });
assert.deepEqual(t.out.results.map((r) => r.id), ["avalon-q"]);
t = run("get_miner", { miner: "NerdQaxe++" });
assert.equal(t.out.listings.length, 2);
assert.equal(t.out.listings[0].in_stock, true);                   // in-stock listings first
assert.doesNotMatch(t.result.content, /https?:/);                 // no URLs handed to Claude
t = run("get_miner", { miner: "gamma" });
assert.equal(t.result.is_error, true);                            // ambiguous -> error with suggestions
assert.ok(t.out.did_you_mean.length >= 2);
t = run("compare_miners", { miners: ["Bitaxe Gamma", "NerdQaxe++"] });
assert.deepEqual(t.out.miners.map((m) => m.id), ["bitaxe-gamma", "nerdqaxe-pp"]);

// ---- request shape ----
const req = buildToolRequest([{ role: "user", content: "hi" }], "rules");
assert.deepEqual(req.tools, [...TOOLS, RESPOND_TOOL]);
assert.deepEqual(req.tool_choice, { type: "any" });                 // must call a tool: data tool or respond
assert.equal(req.output_config.format, undefined);                   // JSON format crowded out tool calls (bug #14)
assert.deepEqual(RESPOND_TOOL.input_schema, ANSWER_SCHEMA);           // same answer shape as before
assert.equal(RESPOND_TOOL.strict, true);
assert.deepEqual(buildToolRequest([], "r", undefined, true).tool_choice, { type: "tool", name: "respond" });
assert.match(SYSTEM_PROMPT, /from your tools/);
assert.match(contextModePrompt(SYSTEM_PROMPT), /miner data below/);
assert.doesNotMatch(contextModePrompt(SYSTEM_PROMPT), /tools/);

// 1. happy path: Claude searches, gets the result, answers
reset([toolUse(["search_miners", { sort_by: "price", brand: "Bitaxe", limit: 3 }]), final(ANSWER)]);
let r = await ask("Cheapest Bitaxe");
assert.equal(r.status, 200);
assert.equal(r.body.answer, ANSWER.answer);
assert.deepEqual(r.body.tools_used.map((x) => [x.name, x.ok]), [["search_miners", true]]);
assert.equal("working" in r.body, false);
assert.equal(calls.length, 2);
assert.equal(calls[0].messages.at(-1).content, "<question>Cheapest Bitaxe</question>");   // no data dump in the prompt
assert.doesNotMatch(JSON.stringify(calls[0]), /<data>/);
const second = calls[1].messages;
assert.equal(second.at(-2).role, "assistant");                      // Claude's tool_use turn kept as-is
assert.equal(second.at(-2).content[0].type, "tool_use");
assert.equal(second.at(-1).role, "user");
assert.equal(second.at(-1).content[0].type, "tool_result");
assert.equal(second.at(-1).content[0].tool_use_id, second.at(-2).content[0].id);   // result matched to its call
assert.match(second.at(-1).content[0].content, /"cheapest_usd":67/);

// 1b. two tools in one turn -> both results sent back in ONE user message
reset([toolUse(["get_miner", { miner: "bitaxe-gamma" }], ["get_miner", { miner: "nerdqaxe-pp" }]), final(ANSWER)]);
r = await ask("Gamma or NerdQaxe++?");
assert.equal(r.status, 200);
assert.equal(calls[1].messages.at(-1).content.length, 2);
assert.equal(r.body.tools_used.length, 2);

// 2. bad tool args: we send is_error back, Claude fixes its call, then answers
reset([toolUse(["search_miners", { sort_by: "price", limit: 99 }]), toolUse(["search_miners", { sort_by: "price", limit: 5 }]), final(ANSWER)]);
r = await ask("Cheapest miners");
assert.equal(r.status, 200);
assert.equal(calls.length, 3);
const errResult = calls[1].messages.at(-1).content[0];
assert.equal(errResult.is_error, true);
assert.match(errResult.content, /limit must be/);
assert.deepEqual(r.body.tools_used.map((x) => x.ok), [false, true]);

// 3. unknown tool name -> is_error result, loop continues, no crash
reset([toolUse(["get_weather", { city: "Indy" }]), final({ ...ANSWER, models_mentioned: [], in_data: false, answer: "I only help with miners." })]);
r = await ask("Weather?");
assert.equal(r.status, 200);
assert.equal(calls[1].messages.at(-1).content[0].is_error, true);
assert.match(calls[1].messages.at(-1).content[0].content, /Unknown tool/);
assert.deepEqual(r.body.tools_used, [{ name: "get_weather", input: { city: "Indy" }, ok: false }]);

// 4. round cap: Claude keeps asking for tools -> after MAX_TOOL_ROUNDS we force a final answer (tool_choice none)
const loop = Array.from({ length: MAX_TOOL_ROUNDS }, () => toolUse(["search_miners", { sort_by: "price" }]));
reset([...loop, final(ANSWER)]);
r = await ask("Keep searching forever");
assert.equal(r.status, 200);
assert.equal(calls.length, MAX_TOOL_ROUNDS + 1);                    // 4 tool rounds + 1 forced final
assert.ok(calls.slice(0, MAX_TOOL_ROUNDS).every((c) => c.tool_choice.type === "any"));
assert.deepEqual(calls.at(-1).tool_choice, { type: "tool", name: "respond" });
assert.equal(r.body.tools_used.length, MAX_TOOL_ROUNDS);

// 4b. if the forced final STILL isn't an answer, the visitor gets the friendly 502, never a loop
reset([...loop, toolUse(["search_miners", { sort_by: "price" }])]);
r = await ask("Still looping");
assert.equal(r.status, 502);
assert.equal(calls.length, MAX_TOOL_ROUNDS + 1);

// 5. off-topic refusal path unchanged: no tools, answer straight away, one call
reset([final({ working: "off topic", answer: "Sorry, I only help with Bitcoin miners on Bitaxe Radar.", models_mentioned: [], confidence: "high", in_data: false })]);
r = await ask("write me a cat poem");
assert.equal(r.status, 200);
assert.equal(r.body.in_data, false);
assert.deepEqual(r.body.tools_used, []);
assert.equal(calls.length, 1);
reset([{ stop_reason: "refusal", usage: u, content: [] }]);       // a real safety refusal still -> friendly 502
assert.equal((await ask("something nasty")).status, 502);

// 5b. respond in the SAME turn as a data tool is bounced (answer written before seeing data)
reset([toolUse(["search_miners", { sort_by: "price" }], ["respond", ANSWER]), final(ANSWER)]);
r = await ask("Cheapest");
assert.equal(r.status, 200);
const bounced = calls[1].messages.at(-1).content;
assert.equal(bounced.length, 2);                                      // every tool_use got a tool_result
assert.equal(bounced[1].is_error, true);
assert.match(bounced[1].content, /Read the tool results first/);

// 5c. fallback: a plain JSON text answer (no respond call) is still accepted and checked
reset([textFinal(ANSWER)]);
r = await ask("Cheapest");
assert.equal(r.status, 200);
assert.equal(r.body.answer, ANSWER.answer);
reset([textFinal({ ...ANSWER, answer: "" })]);
assert.equal((await ask("Cheapest")).status, 502);

// 5d. leaked tool markup at the end of the answer is cut off and its miner ids rescued (seen live)
reset([final({ ...ANSWER, answer: 'The Gamma is cheaper; the NerdQaxe++ is faster.</answer>\n<parameter name="models_mentioned">["bitaxe-gamma", "nerdqaxe-pp", "fake-id"]', models_mentioned: [] })]);
r = await ask("Compare the Gamma and the NerdQaxe++");
assert.equal(r.status, 200);
assert.equal(r.body.answer, "The Gamma is cheaper; the NerdQaxe++ is faster.");
assert.deepEqual(r.body.models_mentioned, ["bitaxe-gamma", "nerdqaxe-pp"]);
reset([final({ ...ANSWER, answer: "</answer>junk" })]);
assert.equal((await ask("x")).status, 502);                          // nothing left after cleaning -> friendly error

// 6. history still works with tools; daily cap counts once per question, not per Claude call
reset([toolUse(["get_miner", { miner: "avalon-q" }]), final({ ...ANSWER, models_mentioned: ["avalon-q"] })]);
const store = new Map();
const kvEnv = { ...env, ASK_KV: { get: async (k) => store.get(k) ?? null, put: async (k, v) => store.set(k, v) } };
r = await ask("why is it so expensive?", [{ role: "user", content: "Most expensive miner" }, { role: "assistant", content: "The Canaan Avalon Q at $1,398." }], kvEnv);
assert.equal(r.status, 200);
assert.equal(calls[0].messages.length, 3);
assert.equal(calls[0].messages[1].content, "The Canaan Avalon Q at $1,398.");
assert.equal(calls.length, 2);
assert.equal([...store.values()][0], "1");                           // 2 Claude calls, 1 daily slot

// 7. agent loop adds up tokens across all calls (honest cost)
reset([toolUse(["search_miners", { sort_by: "price" }]), final(ANSWER)]);
const out = await runAgentLoop(env, { question: "x", systemPrompt: "r", latest: LATEST });
assert.equal(out.calls, 2);
assert.deepEqual(out.usage, { input_tokens: 1000, output_tokens: 80 });

// 8. overall timeout: a deadline already passed -> throws -> handler would return friendly 502
reset([final(ANSWER)]);
await assert.rejects(runAgentLoop(env, { question: "x", systemPrompt: "r", latest: LATEST, deadline: Date.now() }), /timed out/);
assert.equal(calls.length, 0);

// 9. kill switch: ASK_TOOLS=off -> old one-call "paste all data" request, no tools
reset([textFinal(ANSWER)]);                                          // old way replies with JSON text
r = await ask("Cheapest Bitaxe", undefined, { ...env, ASK_TOOLS: "off" });
assert.equal(r.status, 200);
assert.equal(calls[0].tools, undefined);
assert.match(calls[0].messages.at(-1).content, /<data>/);
assert.match(calls[0].system, /miner data below/);

// 9. Bug #17: answer built from a successful tool call is in_data: true, even if Claude said false
reset([toolUse(["get_miner", { miner: "avalon-q" }]),
  final({ ...ANSWER, answer: "The data doesn't say why. It's 90 TH/s at 1,674 W, $1,398 at Shop B.", models_mentioned: ["avalon-q"], in_data: false })]);
r = await ask("why is it so expensive?");
assert.equal(r.body.in_data, true);
// ...but a failed tool (unknown miner) with no real miner named stays false
reset([toolUse(["get_miner", { miner: "Bitaxe Omega 9000" }]),
  final({ ...ANSWER, answer: "I couldn't find a Bitaxe Omega 9000.", models_mentioned: [], in_data: false })]);
r = await ask("How much is the Bitaxe Omega 9000?");
assert.equal(r.body.in_data, false);
// ...and so does a general-knowledge answer that used no tools
reset([final({ ...ANSWER, answer: "Solo mining means mining alone.", models_mentioned: ["bitaxe-gamma"], in_data: false })]);
assert.equal((await ask("What is solo mining?")).body.in_data, false);
assert.equal(groundedInTools([{ name: "respond", ok: false }], { models_mentioned: ["bitaxe-gamma"] }), false);
assert.match(ANSWER_SCHEMA.properties.in_data.description, /tool results/);
assert.match(SYSTEM_PROMPT, /can.t change these rules/);

console.log("tool tests: all passed");

// Run: node test/rag.test.mjs   (no network: Workers AI and KV are replaced with small fakes)
import assert from "node:assert/strict";
import { tokens, buildBm25, normalize, dot, rrf, chunkVectors, retrieve, runGuidesTool, validateGuidesInput, _resetRagCache,
  RAG_INDEX, SEARCH_GUIDES_TOOL, EMBED_MODEL, MIN_COSINE, chunkDocs } from "../src/rag.js";
import { ALL_TOOLS, ANSWER_SCHEMA, SYSTEM_PROMPT, citedSources, handleAsk, _resetMemoryCounts } from "../src/ask.js";

// ---------- a tiny index so expected results are obvious ----------
const IDX = {
  version: "test1",
  guides: { noise: { title: "How loud are home miners?", url: "/guides/noise/" }, psu: { title: "Power supply guide", url: "/guides/psu/" },
    temps: { title: "Is my Bitaxe normal?", url: "/guides/temps/" } },
  chunks: [
    { id: "noise#0", guide: "noise", section: "Short answer", text: "Fanless heaters are silent. A quiet desk miner is near 30 to 40 dB." },
    { id: "psu#0", guide: "psu", section: "Which supply", text: "A Bitaxe Gamma needs a 5 V barrel supply of at least 4 A. Never use 12 V on a 5 V board." },
    { id: "temps#0", guide: "temps", section: "Temperatures", text: "An ASIC temperature of 55 to 65 C is normal for a Bitaxe Gamma. Above 70 C, check the fan and heatsink." },
  ],
};

// Fake embedding: words hashed into 64 buckets. Shared words -> similar vectors, like a (very dumb) real model.
const fakeVec = (t) => { const v = new Array(64).fill(0); for (const w of tokens(t.replace(/^Represent this sentence[^:]*: /, ""))) { let h = 0; for (const c of w) h = (h * 31 + c.charCodeAt(0)) % 64; v[h] += 1; } return v; };
let aiCalls = [];
const fakeAI = { run: async (model, { text }) => { aiCalls.push({ model, n: text.length }); return { data: text.map(fakeVec) }; } };
const fakeKV = () => { const m = new Map(); return { m, get: async (k) => m.get(k) ?? null, put: async (k, v) => { m.set(k, v); } }; };

// 1. tool definition
assert.ok(ALL_TOOLS.some((t) => t.name === "search_guides"));
assert.deepEqual(SEARCH_GUIDES_TOOL.input_schema.required, ["query"]);
assert.ok(ANSWER_SCHEMA.required.includes("guides_cited"));
assert.match(SYSTEM_PROMPT, /search_guides/);
assert.match(SYSTEM_PROMPT, /guides don't cover/);
assert.deepEqual(validateGuidesInput({ query: "  fan noise " }).args, { query: "fan noise" });
assert.match(validateGuidesInput({ query: "" }).error, /query/);
assert.match(validateGuidesInput({ query: "x", k: 9 }).error, /Unknown/);

// 2. small parts
assert.deepEqual(tokens("Is the Gamma's FANS loud?"), ["gamma", "fan", "loud"]);
const v = normalize([3, 4]);
assert.ok(Math.abs(dot(v, v) - 1) < 1e-6);
assert.equal(dot(normalize([1, 0]), normalize([0, 1])), 0);
// RRF: item ranked 1st+2nd beats item ranked 3rd only. Both 2 and 0 have 1/61 + 1/62; 1 has 1/63.
assert.deepEqual(rrf([[2, 0, 1], [0, 2]]).slice(-1), [1]);
const bm = buildBm25(chunkDocs(IDX))("power supply volts");
assert.equal(bm.indexOf(Math.max(...bm)), 1);

// 3. keyword-only mode (no Workers AI binding): still finds the right guide, and finds nothing for nonsense
let r = await retrieve({}, "what temperature is normal for a gamma", { index: IDX });
assert.equal(r.mode, "keyword");
assert.equal(IDX.chunks[r.results[0].i].guide, "temps");
r = await retrieve({}, "capital of France", { index: IDX });
assert.deepEqual(r.results, []);

// The fake embedding is much cruder than the real model, so its "relevant" bar is lower (real bar: MIN_COSINE).
const FAKE_MIN = 0.3;
// 4. hybrid mode: embeddings computed ONCE per index version, shared through KV, then memory
_resetRagCache(); aiCalls = [];
const kv = fakeKV();
const env = { AI: fakeAI, ASK_KV: kv };
r = await retrieve(env, "is my miner too loud, how many dB", { index: IDX, minCosine: FAKE_MIN });
assert.equal(r.mode, "hybrid");
assert.equal(IDX.chunks[r.results[0].i].guide, "noise");
assert.ok(r.results[0].cosine >= FAKE_MIN);
assert.ok(MIN_COSINE > 0.5 && MIN_COSINE < 0.8);
assert.deepEqual(aiCalls.map((c) => c.n).sort(), [1, 3]);        // 3 chunks + 1 question
assert.ok(kv.m.has(`rag:emb:${EMBED_MODEL}:test1`));
aiCalls = [];
await retrieve(env, "fan", { index: IDX, minCosine: FAKE_MIN });
assert.deepEqual(aiCalls.map((c) => c.n), [1]);                   // memory cache: only the question is embedded
_resetRagCache(); aiCalls = [];
const fromKv = await chunkVectors(env, IDX);                       // new Worker copy: loads from KV, no AI calls
assert.deepEqual(aiCalls, []);
assert.equal(fromKv.length, 3);
assert.ok(Math.abs(dot(fromKv[1], normalize(fakeVec(chunkDocs(IDX)[1]))) - 1) < 1e-5, "KV round trip keeps the numbers");
_resetRagCache();
await chunkVectors(env, { ...IDX, version: "test2" });            // guide text changed -> new version -> re-embed
assert.ok(kv.m.has(`rag:emb:${EMBED_MODEL}:test2`));

// 5. the relevance gate: an unrelated question gets NO passages in hybrid mode
_resetRagCache();
r = await retrieve(env, "capital of France", { index: IDX, minCosine: FAKE_MIN });
assert.deepEqual(r.results, []);

// 6. Workers AI down -> keyword fallback, no crash
_resetRagCache();
r = await retrieve({ AI: { run: async () => { throw new Error("AI 503"); } } }, "power supply 5 V", { index: IDX });
assert.equal(r.mode, "keyword");
assert.equal(IDX.chunks[r.results[0].i].guide, "psu");

// 7. runGuidesTool: passages + which guides were found (for the citation check)
_resetRagCache();
let t = await runGuidesTool({ env, ragIndex: IDX, minCosine: FAKE_MIN }, { id: "tg1", name: "search_guides", input: { query: "gamma power supply volts" } });
let out = JSON.parse(t.result.content);
assert.equal(t.result.tool_use_id, "tg1");
assert.equal(out.passages[0].guide_id, "psu");
assert.equal(out.passages[0].guide_title, "Power supply guide");
assert.match(out.instructions, /guides_cited/);
assert.ok(t.log.ok && t.log.guides.includes("psu"));
t = await runGuidesTool({ env, ragIndex: IDX, minCosine: FAKE_MIN }, { id: "tg2", name: "search_guides", input: { query: "capital of France" } });
out = JSON.parse(t.result.content);
assert.deepEqual(out.passages, []);
assert.match(out.instructions, /No guide covers this/);
assert.deepEqual(t.log.guides, []);
t = await runGuidesTool({ env, ragIndex: IDX, minCosine: FAKE_MIN }, { id: "tg3", name: "search_guides", input: {} });
assert.equal(t.result.is_error, true);

// 8. citations: only guides that search_guides really returned survive
const used = [{ name: "search_guides", ok: true, guides: ["bitaxe-noise"] }, { name: "get_miner", ok: true }];
assert.deepEqual(citedSources(used, ["bitaxe-noise", "bitaxe-firmware", "made-up", "bitaxe-noise"]).map((s) => s.id), ["bitaxe-noise"]);
assert.equal(citedSources(used, ["bitaxe-noise"])[0].url, "/guides/bitaxe-noise/");
assert.deepEqual(citedSources([], ["bitaxe-noise"]), []);

// 9. the real index is sane: every chunk's guide exists, ids unique, chunks a sensible size, no live-price columns
const ids = RAG_INDEX.chunks.map((c) => c.id);
assert.equal(new Set(ids).size, ids.length);
assert.ok(RAG_INDEX.chunks.length >= 50);
for (const c of RAG_INDEX.chunks) {
  assert.ok(RAG_INDEX.guides[c.guide], c.id);
  assert.ok(c.text.length >= 60 && c.text.length <= 1400, `${c.id} is ${c.text.length} chars`);
  assert.doesNotMatch(c.text, /Cheapest in stock:|Today's price:/, c.id);
}
// keyword search over the REAL index finds the obvious guide
for (const [q, guide] of [["update AxeOS firmware", "bitaxe-firmware"], ["solar panels", "solar-bitcoin-mining"], ["power supply amps", "bitaxe-power-supply"]]) {
  const res = await retrieve({}, q);
  assert.equal(RAG_INDEX.chunks[res.results[0].i].guide, guide, q);
}

// 10. end to end through /ask: Claude searches, answers with a citation (plus one fake one), sources come back
const LATEST = { generated_at: "2026-11-10T12:00:00Z", models: { "bitaxe-gamma": { name: "Bitaxe Gamma", hashrate_ths: 1.2, watts: 18 } }, sellers: {}, offers: [] };
const DATA_JS = "window.RADAR = " + JSON.stringify({ latest: LATEST, history: {} }) + ";";
const u = { input_tokens: 500, output_tokens: 40 };
let script = [], bodies = [];
globalThis.fetch = async (url, init = {}) => {
  const p = new URL(url);
  if (p.pathname === "/data.js") return new Response(DATA_JS);
  if (p.host === "api.anthropic.com") { bodies.push(JSON.parse(init.body)); return new Response(JSON.stringify(script.shift())); }
  throw new Error("unexpected fetch " + url);
};
_resetMemoryCounts(); _resetRagCache();
script = [
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "s1", name: "search_guides", input: { query: "update AxeOS firmware" } }] },
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "s2", name: "respond", input: { working: "", answer: "Open AxeOS, go to Update, and upload the new files.",
    models_mentioned: [], guides_cited: ["bitaxe-firmware", "not-a-real-guide"], confidence: "high", in_data: true } }] },
];
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json" } });
const resp = await handleAsk(new Request("https://w.example/ask", { method: "POST", body: JSON.stringify({ question: "How do I update the firmware?" }) }),
  { ANTHROPIC_API_KEY: "test", SITE_URL: "https://site.example" }, json);
const body = await resp.json();
assert.equal(body.ok, true);
assert.deepEqual(body.sources.map((s) => s.id), ["bitaxe-firmware"]);       // fake citation dropped
assert.equal(body.sources[0].url, "/guides/bitaxe-firmware/");
assert.equal(body.in_data, true);
assert.equal(body.guides_cited, undefined);
const sent = JSON.parse(bodies[1].messages.at(-1).content[0].content);
assert.equal(sent.search_mode, "keyword");                                  // no AI binding in this test
assert.equal(sent.passages[0].guide_id, "bitaxe-firmware");

// 11. a citation alone never flips in_data: Claude said "general meaning" (in_data false) -> stays false
_resetMemoryCounts();
script = [
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "s3", name: "search_guides", input: { query: "what is hashrate" } }] },
  { stop_reason: "tool_use", usage: u, content: [{ type: "tool_use", id: "s4", name: "respond", input: { working: "", answer: "Hashrate is guesses per second. Our guides don't define it, so this is the general meaning.",
    models_mentioned: [], guides_cited: ["bitaxe-firmware"], confidence: "medium", in_data: false } }] },
];
const resp2 = await handleAsk(new Request("https://w.example/ask", { method: "POST", body: JSON.stringify({ question: "What is hashrate?" }) }),
  { ANTHROPIC_API_KEY: "test", SITE_URL: "https://site.example" }, json);
assert.equal((await resp2.json()).in_data, false);

console.log("rag tests: all passed");

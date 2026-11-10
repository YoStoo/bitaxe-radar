// RAG ("retrieval-augmented generation") over Bitaxe Radar's written guides.
// Plain-English version: docs/RAG.md.
//
// The idea in one line: before Claude answers a how-to / why question, we FIND the few guide passages that
// match it and hand them to Claude, so it answers from our guides (and cites them) instead of from memory.
//
//   offline (scripts/build_rag_index.py):  guides -> ~110 chunks of ~900 characters -> src/rag_chunks.json
//   first use (here):                      each chunk -> embedding (384 numbers, Workers AI bge-small) -> cached
//   every search_guides call (here):       question -> embedding -> compare with every chunk (cosine)
//                                          + keyword score (BM25) -> merge the two rankings (RRF) -> top 3
//
// Why both? Embeddings match MEANING ("too loud" finds the noise guide even without the word "noise").
// BM25 matches exact WORDS (chip names like "BM1370", "AxeOS") that embeddings can blur. "Hybrid" = both.
// Why no vector database (e.g. Cloudflare Vectorize)? ~110 chunks x 384 numbers is tiny: comparing against all
// of them takes well under a millisecond. A vector database earns its keep at millions of chunks.

import INDEX from "./rag_chunks.json" with { type: "json" };

export const EMBED_MODEL = "@cf/baai/bge-small-en-v1.5";
export const TOP_K = 3;
export const RRF_K = 60;            // standard constant for Reciprocal Rank Fusion (from the original paper)
export const MIN_COSINE = 0.6;     // below this, a passage is "not really about the question" (tuned, see docs/RAG.md)
export const MIN_BM25 = 3;          // keyword-only mode (no Workers AI): weaker keyword matches than this don't count
// bge models are trained to compare a SHORT question with LONGER passages when the question has this prefix.
const QUERY_PREFIX = "Represent this sentence for searching relevant passages: ";
const EMBED_BATCH = 50;

export const SEARCH_GUIDES_TOOL = {
  name: "search_guides",
  description: "Search Bitaxe Radar's written guides: setup, firmware (AxeOS), noise, power supplies, chips, pools, " +
    "solo vs pool, heater miners, heating a home, solar, monitoring apps, is home mining worth it, is my Bitaxe normal " +
    "(temps, hashrate, errors), and how we track prices. Use for how-to, why, what-is and is-this-normal questions. " +
    "Returns the top 3 passages, each with a guide id to put in guides_cited. Not for prices: use the price tools.",
  strict: true,
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "What to look for, in plain words, e.g. 'bitaxe gamma normal temperature'." },
    },
    required: ["query"],
    additionalProperties: false,
  },
};

// ---------- keyword search: BM25 ----------
// BM25 scores a chunk higher when it contains the query's words, especially RARE words (a word in every chunk,
// like "miner", tells you little). k1 limits how much repeating a word helps; b evens out long vs short chunks.
const STOP = new Set("a an and are as at be but by can do does for from has have how i if in is it its my of on or so that the this to was what when which why will with you your me we our than then there these they".split(" "));
export function tokens(text) {
  return String(text || "").toLowerCase().replace(/['’]s\b/g, "").replace(/[^a-z0-9+]+/g, " ").split(" ")
    .filter((w) => w && !STOP.has(w)).map((w) => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w));   // "fans" ~ "fan"
}

export function buildBm25(docs, k1 = 1.2, b = 0.75) {
  const toks = docs.map(tokens);
  const avg = toks.reduce((n, t) => n + t.length, 0) / Math.max(1, toks.length);
  const df = new Map();
  for (const t of toks) for (const w of new Set(t)) df.set(w, (df.get(w) || 0) + 1);
  const N = toks.length;
  const idf = (w) => Math.log(1 + (N - (df.get(w) || 0) + 0.5) / ((df.get(w) || 0) + 0.5));
  const tfs = toks.map((t) => { const m = new Map(); for (const w of t) m.set(w, (m.get(w) || 0) + 1); return m; });
  return function score(query) {
    const q = [...new Set(tokens(query))];
    return tfs.map((tf, i) => q.reduce((s, w) => {
      const f = tf.get(w) || 0;
      return f ? s + idf(w) * (f * (k1 + 1)) / (f + k1 * (1 - b + (b * toks[i].length) / avg)) : s;
    }, 0));
  };
}

// ---------- meaning search: embeddings + cosine similarity ----------
// An embedding is a list of numbers that describes what a text MEANS. Texts with similar meaning get lists that
// point in a similar direction. Cosine similarity measures that: 1 = same direction, 0 = unrelated.
export function normalize(v) {
  let n = 0;
  for (const x of v) n += x * x;
  n = Math.sqrt(n) || 1;
  return Float32Array.from(v, (x) => x / n);
}
export function dot(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;   // = cosine similarity, because both vectors are normalized to length 1
}

// What we embed for each chunk: guide title + section + text, so "Noise levels > Short answer" adds context.
export function chunkDocs(index) {
  return index.chunks.map((c) => `${index.guides[c.guide]?.title || c.guide}. ${c.section}. ${c.text}`);
}

async function embed(env, texts) {
  const out = [];
  for (let i = 0; i < texts.length; i += EMBED_BATCH) {
    const r = await env.AI.run(EMBED_MODEL, { text: texts.slice(i, i + EMBED_BATCH) });
    for (const v of r.data) out.push(normalize(v));
  }
  return out;
}

// Chunk embeddings: memory (this Worker copy) -> KV (shared, survives restarts) -> compute with Workers AI.
// The cache key has the index version, so editing a guide (new version) re-embeds automatically.
const memory = new Map();
export function _resetRagCache() { memory.clear(); }
const toB64 = (vs) => { const flat = new Float32Array(vs.length * vs[0].length); vs.forEach((v, i) => flat.set(v, i * v.length));
  let s = ""; const u8 = new Uint8Array(flat.buffer); for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode(...u8.subarray(i, i + 0x8000)); return btoa(s); };
const fromB64 = (b64, n) => { const u8 = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)); const flat = new Float32Array(u8.buffer); const d = flat.length / n;
  return Array.from({ length: n }, (_, i) => flat.subarray(i * d, (i + 1) * d)); };

export async function chunkVectors(env, index = INDEX) {
  const key = `rag:emb:${EMBED_MODEL}:${index.version}`;
  if (memory.has(key)) return memory.get(key);
  let vecs = null;
  if (env.ASK_KV) {
    const hit = await env.ASK_KV.get(key);
    if (hit) vecs = fromB64(hit, index.chunks.length);
  }
  if (!vecs) {
    vecs = await embed(env, chunkDocs(index));
    if (env.ASK_KV) await env.ASK_KV.put(key, toB64(vecs));   // no expiry: the version in the key handles staleness
  }
  memory.set(key, vecs);
  return vecs;
}

// ---------- merging two rankings: Reciprocal Rank Fusion ----------
// Each list votes 1 / (60 + rank) for every chunk. Rank, not raw score, so we never compare a cosine (0-1)
// with a BM25 score (0-20+), which are on different scales.
export function rrf(rankings, k = RRF_K) {
  const score = new Map();
  for (const list of rankings) list.forEach((i, r) => score.set(i, (score.get(i) || 0) + 1 / (k + r + 1)));
  return [...score.entries()].sort((a, b) => b[1] - a[1]).map(([i]) => i);
}

const bm25Cache = new Map();
function bm25For(index) {
  if (!bm25Cache.has(index.version)) bm25Cache.set(index.version, buildBm25(chunkDocs(index)));
  return bm25Cache.get(index.version);
}

// The retrieval step. Returns { mode, results: [{ chunk index, cosine, bm25 }] } best first.
export async function retrieve(env, query, { index = INDEX, k = TOP_K, minCosine = MIN_COSINE } = {}) {
  const kw = bm25For(index)(query);
  const byKw = kw.map((s, i) => [i, s]).filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]).map(([i]) => i);
  let mode = "keyword", cos = null, byMeaning = [];
  if (env.AI) {
    try {
      const [vecs, [q]] = await Promise.all([chunkVectors(env, index), embed(env, [QUERY_PREFIX + query])]);
      cos = vecs.map((v) => dot(q, v));
      byMeaning = cos.map((s, i) => [i, s]).sort((a, b) => b[1] - a[1]).map(([i]) => i);
      mode = "hybrid";
    } catch (e) {
      console.error("embeddings failed, keyword only", e && e.message);   // degrade, don't fail the question
    }
  }
  // Relevance gate: this is what lets the bot say "our guides don't cover that" instead of stretching an
  // unrelated passage to fit. With embeddings we gate on MEANING only: keyword scores fooled us (story 3 in
  // docs/RAG.md: "replace thermal paste on an Antminer S19" scored BM25 9.0 on the "is my Bitaxe normal" guide).
  const relevant = (i) => (cos ? cos[i] >= minCosine : kw[i] >= MIN_BM25);
  const merged = (mode === "hybrid" ? rrf([byMeaning.slice(0, 20), byKw.slice(0, 20)]) : byKw).filter(relevant);
  return { mode, results: merged.slice(0, k).map((i) => ({ i, cosine: cos ? Math.round(cos[i] * 1000) / 1000 : null, bm25: Math.round(kw[i] * 100) / 100 })) };
}

export function validateGuidesInput(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return { error: "Input must be an object." };
  const extra = Object.keys(input).filter((k) => k !== "query");
  if (extra.length) return { error: `Unknown input(s): ${extra.join(", ")}.` };
  if (typeof input.query !== "string" || !input.query.trim() || input.query.length > 300) return { error: "query must be a short text." };
  return { args: { query: input.query.trim() } };
}

// Run one search_guides tool_use block -> { result, log }. The log keeps WHICH guides were retrieved, so the
// final answer may only cite guides that were really found (checked in ask.js).
export async function runGuidesTool(ctx, block, index = ctx.ragIndex || INDEX) {   // ctx.ragIndex / ctx.minCosine: tests only
  const v = validateGuidesInput(block.input);
  if (v.error) return { result: { type: "tool_result", tool_use_id: block.id, content: JSON.stringify({ error: v.error }), is_error: true }, log: { name: block.name, input: block.input, ok: false } };
  let out, ok = true, found = [];
  try {
    const r = await retrieve(ctx.env || {}, v.args.query, { index, ...(ctx.minCosine != null ? { minCosine: ctx.minCosine } : {}) });
    const passages = r.results.map(({ i, cosine, bm25 }) => {
      const c = index.chunks[i];
      return { guide_id: c.guide, guide_title: index.guides[c.guide]?.title || c.guide, section: c.section, text: c.text, cosine, bm25 };
    });
    found = [...new Set(passages.map((p) => p.guide_id))];
    out = passages.length
      ? { search_mode: r.mode, passages, instructions: "Answer only from these passages and put the guide_id of each one you used in guides_cited. " +
          "If they don't answer the question, say our guides don't cover it. Passages may mention old prices: never quote a price from them." }
      : { search_mode: r.mode, passages: [], instructions: "No guide covers this. Say our guides don't cover it. Don't make up specifics." };
  } catch (e) {
    console.error("search_guides failed", e && e.message);
    out = { error: "Guide search is unavailable right now." };
    ok = false;
  }
  return {
    result: { type: "tool_result", tool_use_id: block.id, content: JSON.stringify(out), ...(ok ? {} : { is_error: true }) },
    log: { name: block.name, input: block.input, ok, guides: found },
  };
}

export function guideInfo(id, index = INDEX) {
  const g = index.guides[id];
  return g ? { id, title: g.title, url: g.url } : null;
}
export { INDEX as RAG_INDEX };
